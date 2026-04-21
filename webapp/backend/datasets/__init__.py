"""External dataset integration (Our World in Data + curated static JSON).

This subpackage powers the "Data Analysis" section of the webapp:

- :mod:`sources` — per-dataset metadata (URL, parser, TTL, attribution).
- :mod:`parsers` — pure functions that turn OWID CSV bytes into the
  typed row dicts the frontend consumes.
- :mod:`ingest` — async httpx fetcher with SQLite caching, ETag
  validation, and stale-cache fallback on network failure.
- :mod:`static_data` — loader for hand-curated JSON files under
  ``webapp/backend/data/`` (accidents, nuclear_waste, lifecycle_carbon,
  land_use, fossil_pollution_deaths).

The overall data flow::

    GET /api/datasets/{slug}
        -> datasets.ingest.get_dataset(slug)
            -> (cache hit and fresh) return parsed_json
            -> (cache miss or stale) sources.SPECS[slug].fetch()
                -> httpx GET + parsers.SPECS[slug].parse()
                -> cache write
                -> return parsed_json

Static (curated) datasets bypass ingest entirely and are read from disk
on every request. Their payloads are small (<50 KB each).
"""

from webapp.backend.datasets.sources import (
    DATASET_SPECS,
    STATIC_DATASET_SPECS,
    DatasetSpec,
    StaticDatasetSpec,
)

__all__ = [
    "DATASET_SPECS",
    "STATIC_DATASET_SPECS",
    "DatasetSpec",
    "StaticDatasetSpec",
]
