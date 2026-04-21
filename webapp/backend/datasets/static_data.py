"""Loader for curated JSON datasets committed under ``webapp/backend/data/``.

These files are authored content (accidents list, nuclear waste
scheda, IPCC lifecycle values, van Zalk land-use figures,
Vohra/Lelieveld fossil-fuel pollution estimates) — they live in git
and go through code review, not through the cache table.

The loader is tiny on purpose: one read + JSON decode per request. The
files are ≤50 KB each and the OS page cache handles it. No in-memory
caching layer, so edits to the JSON take effect on the next request
without a server restart.
"""

from __future__ import annotations

import json
from pathlib import Path

from webapp.backend.datasets.sources import (
    STATIC_DATASET_SPECS,
    StaticDatasetSpec,
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def get_static_dataset_path(slug: str) -> Path:
    """Return the absolute path to the JSON file for a static dataset.

    Exposed separately so tests can assert the filenames without
    importing the loader.

    Args:
        slug: A key of :data:`STATIC_DATASET_SPECS`.

    Returns:
        Absolute ``Path`` to the JSON file (may not yet exist during
        development).

    Raises:
        KeyError: If ``slug`` is not a known static dataset.
    """
    spec: StaticDatasetSpec = STATIC_DATASET_SPECS[slug]
    return _DATA_DIR / spec.filename


def get_static_dataset(slug: str) -> dict:
    """Load and return the JSON payload for a curated dataset.

    Args:
        slug: A key of :data:`STATIC_DATASET_SPECS`.

    Returns:
        Parsed JSON as a Python dict or list, wrapped under a ``rows``
        key so the response shape matches the remote-dataset envelope.
        Top-level JSON objects are passed through as-is under
        ``payload`` to let more complex schemas (nuclear_waste scheda)
        carry multiple sections without forcing a list.

    Raises:
        KeyError: If ``slug`` is not a known static dataset.
        FileNotFoundError: If the JSON file has not been created yet.
        json.JSONDecodeError: If the JSON is malformed.
    """
    path = get_static_dataset_path(slug)
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    # List → wrap in {"rows": [...]}; dict → expose under "payload"
    # so heterogeneous schemas (the nuclear_waste scheda has top-level
    # keys for sections, not a row list) don't get flattened.
    if isinstance(payload, list):
        return {"rows": payload}
    return {"payload": payload}
