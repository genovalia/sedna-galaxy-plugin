#!/usr/bin/env python3
"""Galaxy tool: fetch a Sedna dataset (samples TSV + VCF.gz) into a Galaxy history."""
import argparse
import csv
import sys
import time

import requests

TIMEOUT = 60


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--token", default="")  # empty: public datasets only
    p.add_argument("--dataset-id", required=True)
    p.add_argument("--genomic-data-id", type=int)
    p.add_argument("--samples-out", required=True)
    p.add_argument("--vcf-out", required=True)
    p.add_argument("--max-wait", type=int, default=3600)  # seconds
    a = p.parse_args()

    base = a.url.rstrip("/") + "/v1"
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

    # which VCF of the dataset
    gds = get(f"/datasets/{a.dataset_id}/genomic-data").json()
    if a.genomic_data_id is None:
        if len(gds) != 1:
            sys.exit("Dataset has %d VCFs, give --genomic-data-id among: %s"
                     % (len(gds), [(g["id"], g.get("name"), g.get("assembly")) for g in gds]))
        a.genomic_data_id = gds[0]["id"]

    if not a.token:  # public dataset: the cached full VCF, no task
        with get(f"/datasets/{a.dataset_id}/genomic-data/{a.genomic_data_id}/vcf", stream=True) as d, \
                open(a.vcf_out, "wb") as f:
            for chunk in d.iter_content(1 << 20):
                f.write(chunk)
        return

    # VCF generation is a Celery task: start, poll, download
    r = s.post(f"{base}/datasets/{a.dataset_id}/genomic-data/{a.genomic_data_id}/generate-vcf",
               json={"dataset_sample_ids": [], "dataset_all_samples": True}, timeout=TIMEOUT)
    if r.status_code != 202:
        sys.exit(f"generate-vcf -> {r.status_code}: {r.text[:300]}")
    task_id = r.json()["task_id"]

    deadline = time.time() + a.max_wait
    while True:
        st = get(f"/tasks/{task_id}").json()["status"]
        if st == "SUCCESS":
            break
        if st in ("FAILURE", "CANCELED"):
            sys.exit(f"VCF task {task_id} ended with {st}")
        if time.time() > deadline:
            sys.exit(f"VCF task {task_id} still {st} after {a.max_wait}s")
        time.sleep(5)

    with get(f"/tasks/{task_id}/download", stream=True) as d, open(a.vcf_out, "wb") as f:
        for chunk in d.iter_content(1 << 20):
            f.write(chunk)


if __name__ == "__main__":
    main()
