"""Dynamic options for the sedna_fetch form: the dataset picker.

Galaxy evaluates the dynamic_options expression with the form's parameter values
by name (token), so the function takes it as an argument. With a token: the datasets
the user can read, with their names (GET /v1/datasets). Without: the public catalogue
(GET /v1/datasets/catalog). The descriptions come from the public metadata-api v2
(GET /v2/datasets), which needs no token.
"""
import time

import requests

SEDNA_URL = "https://catalog-backend.apps.genovalia.ulaval.ca"  # hardcoded: kept in sync by tests/test_contracts.py
TIMEOUT = 5  # the form waits for these calls: keep short
CACHE_TTL = 60  # Galaxy evaluates each select several times while building the form
METADATA_URL = "https://metadata.genovalia.ulaval.ca"  # public: dataset titles (metadata-api v2)
TITLE_LANGS = ("en", "fr")  # preferred language, in order, for the dropdown label
TITLE_MAX = 120  # the title is shown in the dropdown label
_cache = {}


def _cached(key, fetch):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    result = fetch()
    _cache[key] = (time.time(), result)
    return result


def _clean(value):
    return (value or "").strip()


def _error(message):
    return [(message, "", False)]


def _short(text):
    text = " ".join((text or "").split())
    return text if len(text) <= TITLE_MAX else text[: TITLE_MAX - 1].rstrip() + "…"


def _title_text(title):
    """v2's title is a langString ({"en": ..., "fr": ...}); pick one for the label."""
    if not isinstance(title, dict):
        return title or ""
    for lang in TITLE_LANGS:
        if title.get(lang):
            return title[lang]
    return next((v for v in title.values() if v), "")


def _titles():
    return _cached(("titles",), _fetch_titles)


def _fetch_titles():
    # Optional extra: on failure the dropdown falls back to the identifiers.
    found, page = {}, 1
    try:
        while True:
            r = requests.get(f"{METADATA_URL}/v2/datasets", params={"page": page, "page_size": 100}, timeout=TIMEOUT)
            r.raise_for_status()
            body = r.json()
            found.update({d["identifier"]: _short(_title_text(d.get("title"))) for d in body["content"]})
            if not body["content"] or page * 100 >= body["total"]:
                return found
            page += 1
    except Exception:
        return found


def list_datasets(token):
    token = _clean(token)
    return _cached(("datasets", token), lambda: _fetch_datasets(token))


def _fetch_datasets(token):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    path = "/v1/datasets" if token else "/v1/datasets/catalog"
    try:
        r = requests.get(SEDNA_URL + path, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        return _error(f"List unavailable: {e}")
    titles = _titles()
    if token:
        options = [
            (
                f"{titles.get(d['dataset_id']) or d.get('name') or d['dataset_id']} ({d.get('species') or 'unknown species'})",
                d["dataset_id"],
                False,
            )
            for d in rows
        ]
    else:
        options = [
            (
                f"{titles.get(d['dataset_id']) or d['dataset_id']}"
                f" ({d.get('sample_size', 0):,} samples, {d.get('variant_count', 0):,} variants)",
                d["dataset_id"],
                False,
            )
            for d in rows
        ]
    return sorted(options, key=lambda o: o[0].lower()) or _error("No accessible dataset")
