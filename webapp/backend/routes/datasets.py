"""External & curated dataset endpoints ("Data Analysis" section).

Serves the data that powers the ``/data-analysis`` page in the
frontend: mortality and carbon intensity figures pulled from Our World
in Data plus hand-curated JSON files (accidents list, nuclear waste
scheda, IPCC lifecycle values, van Zalk land-use figures,
Vohra/Lelieveld fossil-fuel pollution estimates).

Endpoints
---------

    GET  /api/datasets                         List all datasets (remote + static)
    GET  /api/datasets/{slug}                  Return full payload for one dataset
    POST /api/datasets/{slug}/refresh          Force upstream re-fetch (remote only)

The single-slug endpoint dispatches to :mod:`datasets.ingest` for
remote datasets and :mod:`datasets.static_data` for curated ones.
Static slugs never hit the network; remote slugs use the SQLite cache
with a stale-tolerant fallback (see ingest module for details).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from webapp.backend.datasets.ingest import (
    DatasetUnavailable,
    get_dataset,
)
from webapp.backend.datasets.sources import (
    DATASET_SPECS,
    STATIC_DATASET_SPECS,
)
from webapp.backend.datasets.static_data import get_static_dataset
from webapp.backend.db import list_external_datasets
from webapp.backend.models import (
    DatasetIndexEntry,
    DatasetMeta,
    DatasetResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


# Process start-time fallback for ``fetched_at`` on static datasets —
# they have no "last fetched" concept but the frontend still needs a
# timestamp to render the attribution footer.
from datetime import datetime, timezone
_PROCESS_START_ISO = datetime.now(timezone.utc).isoformat()


@router.get("", response_model=list[DatasetIndexEntry])
async def list_datasets() -> list[DatasetIndexEntry]:
    """Catalog of available datasets (remote and static).

    Remote datasets include the cache freshness fields; static ones
    report ``fetched_at=None`` since they ship with the repo.

    Returns:
        List of :class:`DatasetIndexEntry` ordered by slug.
    """
    cached = {row["slug"]: row for row in await list_external_datasets()}

    entries: list[DatasetIndexEntry] = []
    for slug, spec in DATASET_SPECS.items():
        cache_row = cached.get(slug)
        entries.append(DatasetIndexEntry(
            slug=slug,
            title=spec.title,
            kind="remote",
            source_url=spec.source_url,
            fetched_at=cache_row["fetched_at"] if cache_row else None,
            is_stale=bool(cache_row and cache_row["is_stale"]),
        ))
    for slug, static_spec in STATIC_DATASET_SPECS.items():
        entries.append(DatasetIndexEntry(
            slug=slug,
            title=static_spec.title,
            kind="static",
            source_url="",
            fetched_at=_PROCESS_START_ISO,
            is_stale=False,
        ))
    entries.sort(key=lambda e: e.slug)
    return entries


@router.get("/{slug}", response_model=DatasetResponse)
async def get_dataset_by_slug(slug: str) -> DatasetResponse:
    """Return the full payload for a dataset.

    Dispatches based on the slug namespace:
    - ``DATASET_SPECS`` → :func:`datasets.ingest.get_dataset` (lazy fetch)
    - ``STATIC_DATASET_SPECS`` → :func:`datasets.static_data.get_static_dataset`

    Args:
        slug: Path parameter.

    Returns:
        :class:`DatasetResponse` with meta + rows (or payload for
        schemas that aren't flat row lists).

    Raises:
        HTTPException 404: Unknown slug, or static JSON file missing.
        HTTPException 503: Remote dataset cold-start and upstream is
            unreachable (no cached fallback to serve).
    """
    if slug in DATASET_SPECS:
        return await _serve_remote(slug)
    if slug in STATIC_DATASET_SPECS:
        return _serve_static(slug)
    raise HTTPException(status_code=404, detail=f"Unknown dataset '{slug}'")


@router.post("/{slug}/refresh", response_model=DatasetResponse)
async def refresh_dataset(slug: str) -> DatasetResponse:
    """Force an upstream re-fetch for a remote dataset.

    Bypasses the TTL check. Static datasets reject this call — there is
    no upstream to refresh from.

    Args:
        slug: Path parameter.

    Returns:
        Freshly fetched :class:`DatasetResponse`.

    Raises:
        HTTPException 404: Unknown slug.
        HTTPException 400: Slug refers to a static dataset.
        HTTPException 502: Upstream fetch failed and no cache was
            available to fall back on (bubbled from
            :class:`DatasetUnavailable`).
    """
    if slug in STATIC_DATASET_SPECS:
        raise HTTPException(
            status_code=400,
            detail=f"Dataset '{slug}' is static; nothing to refresh")
    if slug not in DATASET_SPECS:
        raise HTTPException(status_code=404, detail=f"Unknown dataset '{slug}'")
    return await _serve_remote(slug, force_refresh=True,
                                map_unavailable_to=502)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _serve_remote(
    slug: str,
    force_refresh: bool = False,
    map_unavailable_to: int = 503,
) -> DatasetResponse:
    """Fetch (or re-use cache) + wrap a remote dataset into a response.

    Args:
        slug: Remote dataset slug.
        force_refresh: Passed through to :func:`get_dataset`.
        map_unavailable_to: HTTP status to raise when the dataset is
            unavailable (503 for passive reads, 502 for explicit
            ``/refresh`` requests — the upstream is the 'bad gateway'
            in that case).

    Returns:
        :class:`DatasetResponse` with rows and meta.

    Raises:
        HTTPException: Mapped from :class:`DatasetUnavailable`.
    """
    spec = DATASET_SPECS[slug]
    try:
        result = await get_dataset(slug, force_refresh=force_refresh)
    except DatasetUnavailable as exc:
        raise HTTPException(
            status_code=map_unavailable_to, detail=str(exc)) from exc

    meta = DatasetMeta(
        slug=slug,
        title=spec.title,
        source_url=spec.source_url,
        license=spec.license,
        attribution=spec.attribution,
        fetched_at=result["fetched_at"],
        is_stale=result["is_stale"],
        notes=spec.notes,
        kind="remote",
    )
    return DatasetResponse(meta=meta, rows=result["rows"], payload=None)


def _serve_static(slug: str) -> DatasetResponse:
    """Load and wrap a curated static dataset.

    Args:
        slug: Static dataset slug.

    Returns:
        :class:`DatasetResponse`.

    Raises:
        HTTPException 404: If the JSON file is missing (likely the
            slug is registered but the file hasn't been curated yet).
    """
    spec = STATIC_DATASET_SPECS[slug]
    try:
        payload = get_static_dataset(slug)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Static dataset file missing: {spec.filename}",
        ) from exc

    meta = DatasetMeta(
        slug=slug,
        title=spec.title,
        source_url="",
        license="Curated (see attribution)",
        attribution=spec.attribution,
        fetched_at=_PROCESS_START_ISO,
        is_stale=False,
        notes=spec.notes,
        kind="static",
    )
    return DatasetResponse(
        meta=meta,
        rows=payload.get("rows"),
        payload=payload.get("payload"),
    )
