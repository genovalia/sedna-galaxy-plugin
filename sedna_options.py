"""Dynamic options for the sedna_fetch form: dataset and VCF pickers.

Galaxy evaluates the dynamic_options expressions with the form's parameter values
by name (url, token, dataset_id), so the functions take them as arguments.
With a token: the datasets the user can read, with their names (GET /v1/datasets).
Without: the public catalogue (GET /v1/datasets/catalog). The descriptions come
from the public metadata-api (GET /v1/datasets), which needs no token.
"""
import time

import requests

TIMEOUT = 5  # the form waits for these calls: keep short
CACHE_TTL = 60  # Galaxy evaluates each select several times while building the form
METADATA_URL = "https://metadata-api.apps.genovalia.ulaval.ca"  # public: dataset titles
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


def _titles():
    return _cached(("titles",), _fetch_titles)


def _fetch_titles():
    # Optional extra: on failure the dropdown falls back to the identifiers.
    found, page = {}, 1
    try:
        while True:
            r = requests.get(f"{METADATA_URL}/v1/datasets", params={"page": page, "page_size": 100}, timeout=TIMEOUT)
            r.raise_for_status()
            body = r.json()
            found.update({d["id"]: _short(d.get("title")) for d in body["content"]})
            if not body["content"] or page * 100 >= body["total"]:
                return found
            page += 1
    except Exception:
        return found


def list_datasets(url, token):
    base = _clean(url).rstrip("/")
    token = _clean(token)
    if not base:
        return _error("Renseigner l'URL de l'API Sedna")
    return _cached(("datasets", base, token), lambda: _fetch_datasets(base, token))


def _fetch_datasets(base, token):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    path = "/v1/datasets" if token else "/v1/datasets/catalog"
    try:
        r = requests.get(base + path, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        return _error(f"Liste indisponible : {e}")
    titles = _titles()
    if token:
        options = [
            (
                f"{titles.get(d['dataset_id']) or d.get('name') or d['dataset_id']} ({d.get('species') or 'espèce ?'})",
                d["dataset_id"],
                False,
            )
            for d in rows
        ]
    else:
        options = [
            (
                f"{titles.get(d['dataset_id']) or d['dataset_id']}"
                f" ({d.get('sample_size', 0):,} échantillons, {d.get('variant_count', 0):,} variants)",
                d["dataset_id"],
                False,
            )
            for d in rows
        ]
    return sorted(options, key=lambda o: o[0].lower()) or _error("Aucun jeu de données accessible")


def list_vcfs(url, token, dataset_id):
    base = _clean(url).rstrip("/")
    token = _clean(token)
    dataset_id = _clean(dataset_id)
    if not base or not dataset_id:
        return []
    return _cached(("vcfs", base, token, dataset_id), lambda: _fetch_vcfs(base, token, dataset_id))


def _fetch_vcfs(base, token, dataset_id):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = requests.get(f"{base}/v1/datasets/{dataset_id}/genomic-data", headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        return _error(f"VCF indisponibles : {e}")
    # No choice is fine when the dataset has a single VCF: sedna_fetch picks it.
    return [(f"{g.get('name') or g['id']} ({g.get('assembly') or '?'})", str(g["id"]), False) for g in rows]
