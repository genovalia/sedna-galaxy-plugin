"""Contract tests for the public APIs the Galaxy plugin relies on.

Read-only, no token. The daily workflow (.github/workflows/contract-tests.yml) runs them
against production. A failure means an API the plugin reads has changed or is down.

Environment (optional):
  SEDNA_URL             root of the Sedna API   (default: production)
  METADATA_URL          root of the metadata-api (default: production)
  CONTRACT_DATASET_ID   dataset used for the per-dataset checks (default: alcant1)
"""

import os
import sys
from pathlib import Path

import pytest
import requests

# sedna_options.py sits at the repo root, next to the tool
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sedna_options  # noqa: E402

SEDNA_ROOT = os.environ.get("SEDNA_URL", "https://catalog-backend.apps.genovalia.ulaval.ca").rstrip("/")
METADATA_ROOT = os.environ.get("METADATA_URL", "https://metadata-api.apps.genovalia.ulaval.ca").rstrip("/")
SEDNA = SEDNA_ROOT + "/v1"
METADATA = METADATA_ROOT + "/v1"
DATASET = os.environ.get("CONTRACT_DATASET_ID", "alcant1")
TIMEOUT = 30


def get_json(url, **params):
    r = requests.get(url, params=params or None, timeout=TIMEOUT)
    assert r.status_code == 200, f"GET {url} -> {r.status_code}: {r.text[:200]}"
    return r.json()


@pytest.fixture(scope="module")
def catalog():
    return get_json(f"{SEDNA}/datasets/catalog")


@pytest.fixture(scope="module")
def genomic_data():
    return get_json(f"{SEDNA}/datasets/{DATASET}/genomic-data")


# --- Sedna: what the form and sedna_fetch.py read ---------------------------------------

def test_catalog_has_the_fields_the_dropdown_uses(catalog):
    assert isinstance(catalog, list) and catalog
    for d in catalog:
        assert isinstance(d["dataset_id"], str) and d["dataset_id"]
        assert isinstance(d["sample_size"], int)
        assert isinstance(d["variant_count"], int)
    ids = [d["dataset_id"] for d in catalog]
    assert len(ids) == len(set(ids)), "duplicate dataset_id in the catalog"


def test_dataset_samples_is_a_non_empty_list_of_rows():
    rows = get_json(f"{SEDNA}/datasets/{DATASET}/dataset-samples")
    assert isinstance(rows, list) and rows
    assert all(isinstance(r, dict) for r in rows)


def test_genomic_data_has_the_fields_the_tool_reads(genomic_data):
    assert isinstance(genomic_data, list) and genomic_data
    for g in genomic_data:
        assert isinstance(g["id"], int)
        # read with .get() by the form and sedna_fetch.py: the keys must exist, values may be null
        assert "name" in g and "assembly" in g


def test_public_vcf_is_served_as_gzip(genomic_data):
    gid = genomic_data[0]["id"]
    r = requests.get(f"{SEDNA}/datasets/{DATASET}/genomic-data/{gid}/vcf", stream=True, timeout=TIMEOUT)
    try:
        assert r.status_code == 200, f"public VCF -> {r.status_code}: {r.text[:200]}"
        head = next(r.iter_content(2), b"")
        assert head == b"\x1f\x8b", "public VCF does not start with the gzip magic bytes"
    finally:
        r.close()


def test_generate_vcf_refuses_anonymous_calls(genomic_data):
    # Only the authentication part is checked: no token, so no task is created.
    gid = genomic_data[0]["id"]
    r = requests.post(
        f"{SEDNA}/datasets/{DATASET}/genomic-data/{gid}/generate-vcf",
        json={"dataset_sample_ids": [], "dataset_all_samples": True},
        timeout=TIMEOUT,
    )
    assert r.status_code == 401, f"generate-vcf without token -> {r.status_code}"


# --- metadata-api: titles and descriptions shown in the dropdown ------------------------

def _all_metadata_datasets():
    page, rows = 1, []
    while True:
        body = get_json(f"{METADATA}/datasets", page=page, page_size=100)
        rows += body["content"]
        if not body["content"] or page * 100 >= body["total"]:
            return rows, body["total"]
        page += 1


def test_metadata_datasets_have_title_and_description():
    rows, total = _all_metadata_datasets()
    assert len(rows) == total, f"pagination returned {len(rows)} of {total} datasets"
    for d in rows:
        assert isinstance(d["id"], str) and d["id"]
        assert isinstance(d.get("title"), str) and d["title"].strip(), f"{d['id']}: no title"
        assert isinstance(d.get("description"), str) and d["description"].strip(), f"{d['id']}: no description"


def test_every_catalog_dataset_has_metadata(catalog):
    rows, _ = _all_metadata_datasets()
    meta_ids = {d["id"] for d in rows}
    missing = [d["dataset_id"] for d in catalog if d["dataset_id"] not in meta_ids]
    assert not missing, f"datasets in the catalog but not in metadata-api: {missing}"


# --- the plugin itself, against production ----------------------------------------------

def test_dropdown_lists_public_datasets_without_error():
    options = sedna_options.list_datasets(SEDNA_ROOT, "")
    assert options, "no options"
    # an error is returned as an option with an empty value
    assert all(value for _, value, _ in options), options[0]
    assert all("échantillons" in label for label, _, _ in options), options[0]
