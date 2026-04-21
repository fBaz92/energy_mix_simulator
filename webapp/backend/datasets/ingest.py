"""Async fetcher + SQLite cache for remote OWID datasets.

Exports a single async entry point, :func:`get_dataset`, that returns a
frontend-ready payload for a given slug. The function encapsulates the
full cache policy:

1. If the row exists and is fresh (``age < ttl``) → serve from cache.
2. If the row is missing or stale → attempt an upstream fetch.
3. On fetch success → update the cache row, serve fresh payload.
4. On fetch failure with a cached row → serve cache with
   ``is_stale=true`` so the UI can badge it.
5. On fetch failure with no cache → raise :class:`DatasetUnavailable`;
   the router translates that to HTTP 503.

The cache stores the upstream CSV (gzipped for audit) and the parsed
JSON side-by-side. Keeping the parsed shape avoids re-parsing on every
read and lets us evolve the parser without invalidating the cache —
the next forced refresh regenerates both.

ETag support is best-effort: if OWID echoes the ``ETag`` header the
next fetch sends ``If-None-Match`` and a 304 short-circuits the body
download. Not all datasets send a stable ETag, so we also honour TTL.
"""

from __future__ import annotations

import gzip
import json
import logging
from datetime import datetime, timezone

import httpx

from webapp.backend.datasets.parsers import get_parser
from webapp.backend.datasets.sources import DATASET_SPECS, DatasetSpec
from webapp.backend.db import (
    get_external_dataset,
    mark_external_dataset_stale,
    upsert_external_dataset,
)

logger = logging.getLogger(__name__)

_USER_AGENT = "energy-mix-simulator/0.1 (educational; +github)"
_HTTP_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


class DatasetUnavailable(Exception):
    """Raised when a dataset has no cache and the upstream fetch failed.

    The router maps this to HTTP 503 ``Service Unavailable`` with the
    underlying error as the detail message.
    """


def _now() -> datetime:
    """Return current UTC time (injectable for tests via monkeypatch).

    Returns:
        Timezone-aware ``datetime`` in UTC.
    """
    return datetime.now(timezone.utc)


def _is_fresh(row: dict, ttl_hours: int) -> bool:
    """Check whether a cached row is still within its TTL.

    Args:
        row: A dict returned by :func:`get_external_dataset`.
        ttl_hours: Effective TTL — taken from the spec rather than the
            row so configuration changes take effect without forced
            refresh.

    Returns:
        ``True`` if the row is younger than ``ttl_hours`` AND not
        flagged stale from a previous failed refresh.
    """
    if row.get("is_stale"):
        return False
    try:
        fetched = datetime.fromisoformat(row["fetched_at"])
    except (KeyError, ValueError):
        return False
    age_h = (_now() - fetched).total_seconds() / 3600.0
    return age_h < ttl_hours


async def _fetch_upstream(
    spec: DatasetSpec,
    prior_etag: str | None,
) -> tuple[bytes, str | None] | None:
    """Perform a single conditional GET against the upstream URL.

    Args:
        spec: The target dataset spec.
        prior_etag: ETag from the existing cache row, or ``None``.

    Returns:
        ``(raw_bytes, etag)`` on 200, or ``None`` on 304 (content is
        unchanged, keep the existing cache). Raises on other errors.

    Raises:
        httpx.HTTPError: Network or HTTP-level failure (timeout, 4xx,
            5xx). The caller decides whether to fall back to a stale
            cache or propagate.
    """
    headers = {"User-Agent": _USER_AGENT, "Accept": "text/csv,*/*"}
    if prior_etag:
        headers["If-None-Match"] = prior_etag

    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = await client.get(spec.source_url)

    if response.status_code == 304:
        return None
    response.raise_for_status()
    return response.content, response.headers.get("etag")


async def _refresh(spec: DatasetSpec, prior_row: dict | None) -> dict:
    """Fetch + parse + cache a single dataset.

    Args:
        spec: The target dataset spec.
        prior_row: Existing cache row, or ``None`` on cold start. Used
            to send a conditional GET and to recover its parsed payload
            on 304 responses.

    Returns:
        Dict with keys ``rows`` (parsed payload) and ``fetched_at``,
        ``is_stale=False``, matching the shape served by
        :func:`get_dataset`.

    Raises:
        httpx.HTTPError: Propagated on upstream failure. The caller
            translates this into a stale-fallback response.
    """
    prior_etag = prior_row.get("etag") if prior_row else None
    result = await _fetch_upstream(spec, prior_etag)

    if result is None:
        # 304 Not Modified — bump fetched_at to restart the TTL but
        # keep the cached payload.
        assert prior_row is not None
        await upsert_external_dataset(
            slug=spec.slug,
            source_url=spec.source_url,
            raw_csv=prior_row["raw_csv"],
            parsed_json=prior_row["parsed_json"],
            etag=prior_etag,
            refresh_ttl_hours=spec.refresh_ttl_hours,
        )
        return {
            "rows": json.loads(prior_row["parsed_json"]),
            "fetched_at": _now().isoformat(),
            "is_stale": False,
        }

    raw_bytes, etag = result
    parser = get_parser(spec.parser_name)
    rows = parser(raw_bytes)
    parsed_json = json.dumps(rows, ensure_ascii=False)

    await upsert_external_dataset(
        slug=spec.slug,
        source_url=spec.source_url,
        raw_csv=gzip.compress(raw_bytes),
        parsed_json=parsed_json,
        etag=etag,
        refresh_ttl_hours=spec.refresh_ttl_hours,
    )
    logger.info(
        "Dataset %s refreshed (%d rows, %d bytes raw)",
        spec.slug, len(rows), len(raw_bytes),
    )
    return {
        "rows": rows,
        "fetched_at": _now().isoformat(),
        "is_stale": False,
    }


async def get_dataset(slug: str, force_refresh: bool = False) -> dict:
    """Return the frontend-ready payload for a remote dataset.

    See module docstring for the full cache policy.

    Args:
        slug: A key of :data:`DATASET_SPECS`.
        force_refresh: Skip the freshness check and always attempt an
            upstream fetch. Used by the ``POST /refresh`` endpoint.

    Returns:
        Dict with ``rows`` (list of parsed row dicts), ``fetched_at``
        (ISO UTC of the serve time, not the original fetch), and
        ``is_stale`` (``True`` when the served data came from a cache
        whose last refresh failed).

    Raises:
        KeyError: If ``slug`` is not a remote dataset (check
            ``STATIC_DATASET_SPECS`` instead).
        DatasetUnavailable: If there is no cache and the upstream
            fetch failed. Wraps the original exception's message.
    """
    spec = DATASET_SPECS[slug]  # KeyError propagates with a clear msg
    row = await get_external_dataset(slug)

    if not force_refresh and row and _is_fresh(row, spec.refresh_ttl_hours):
        return {
            "rows": json.loads(row["parsed_json"]),
            "fetched_at": row["fetched_at"],
            "is_stale": False,
        }

    try:
        return await _refresh(spec, row)
    except httpx.HTTPError as exc:
        logger.warning(
            "Dataset %s refresh failed: %s", slug, exc,
        )
        if row is not None:
            # Serve the last good payload with an "is_stale" flag so the
            # UI can warn the user.
            await mark_external_dataset_stale(slug, str(exc))
            return {
                "rows": json.loads(row["parsed_json"]),
                "fetched_at": row["fetched_at"],
                "is_stale": True,
            }
        raise DatasetUnavailable(
            f"Could not fetch '{slug}' and no cached copy exists: {exc}"
        ) from exc
