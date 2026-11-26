#!/usr/bin/env python3
"""Galaxy tool: fetch a Sedna dataset (samples TSV + all its VCFs) into a Galaxy history."""
import argparse
import csv
import gzip
import os
import re
import shutil
import sys
import tempfile
import time

import requests

SEDNA_URL = "https://catalog-backend.apps.genovalia.ulaval.ca"  # hardcoded: kept in sync by tests/test_contracts.py
TIMEOUT = 60


def filename_of(response):
    """The name the server gives the download (Content-Disposition), '' when it gives none."""
    match = re.search(r'filename="?([^";]+)"?', response.headers.get("Content-Disposition", ""))
    return match.group(1) if match else ""


def save_vcf(response, out_path):
    """Writes the downloaded VCF to out_path as plain text.

    A download named .gz is decompressed, so Galaxy gets the plain VCF. Without a name, the gzip magic bytes decide.
    """
    fd, raw_path = tempfile.mkstemp(suffix=".download")
    try:
        with os.fdopen(fd, "wb") as raw:
            for chunk in response.iter_content(1 << 20):
                raw.write(chunk)
        name = filename_of(response)
        with open(raw_path, "rb") as raw:
            gzipped = name.endswith(".gz") if name else raw.read(2) == b"\x1f\x8b"
        if gzipped:
            with gzip.open(raw_path, "rb") as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
        else:
            shutil.copyfile(raw_path, out_path)
    finally:
        os.remove(raw_path)


def vcf_filename(genomic_data):
    """A filesystem-safe, unique name for this genomic-data entry's VCF, used by Galaxy's <discover_datasets>."""
    label = genomic_data.get("name") or genomic_data.get("assembly")
    if not label:
        return f"{genomic_data['id']}.vcf"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("_") or str(genomic_data["id"])
    return f"{safe}_{genomic_data['id']}.vcf"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--token", default="")  # empty: public datasets only
    p.add_argument("--dataset-id", required=True)
    p.add_argument("--samples-out", required=True)
    p.add_argument("--vcf-dir", required=True)  # directory; one file per VCF, discovered by the tool's <collection>
    p.add_argument("--max-wait", type=int, default=3600)  # seconds, per VCF
    a = p.parse_args()

    base = SEDNA_URL.rstrip("/") + "/v1"
    s = requests.Session()
    if a.token:
        s.headers["Authorization"] = f"Bearer {a.token}"

    def get(path, **kw):
        r = s.get(f"{base}{path}", timeout=TIMEOUT, **kw)
        if not r.ok:
            sys.exit(f"GET {path} -> {r.status_code}: {r.text[:300]}")
        return r

    # samples -> TSV
    samples = get(f"/datasets/{a.dataset_id}/dataset-samples").json()
    cols = sorted({k for row in samples for k in row})
    with open(a.samples_out, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(cols)
        for row in samples:
            w.writerow(["" if row.get(c) is None else row.get(c) for c in cols])

    # every VCF of the dataset
    gds = get(f"/datasets/{a.dataset_id}/genomic-data").json()
    if not gds:
        sys.exit(f"Dataset {a.dataset_id} has no VCF")

    os.makedirs(a.vcf_dir, exist_ok=True)
    for g in gds:
        out_path = os.path.join(a.vcf_dir, vcf_filename(g))

        if not a.token:  # public dataset: the cached full VCF, no task
            with get(f"/datasets/{a.dataset_id}/genomic-data/{g['id']}/vcf", stream=True) as d:
                save_vcf(d, out_path)
            continue

        # VCF generation is a Celery task: start, poll, download
        r = s.post(f"{base}/datasets/{a.dataset_id}/genomic-data/{g['id']}/generate-vcf", timeout=TIMEOUT)
        if r.status_code != 202:
            sys.exit(f"generate-vcf (genomic-data {g['id']}) -> {r.status_code}: {r.text[:300]}")
        task_id = r.json()["task_id"]

        deadline = time.time() + a.max_wait
        while True:
            st = get(f"/tasks/{task_id}").json()["status"]
            if st == "SUCCESS":
                break
            if st in ("FAILURE", "CANCELED"):
                sys.exit(f"VCF task {task_id} (genomic-data {g['id']}) ended with {st}")
            if time.time() > deadline:
                sys.exit(f"VCF task {task_id} (genomic-data {g['id']}) still {st} after {a.max_wait}s")
            time.sleep(5)

        with get(f"/tasks/{task_id}/download", stream=True) as d:
            save_vcf(d, out_path)


if __name__ == "__main__":
    main()
