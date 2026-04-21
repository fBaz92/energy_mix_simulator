"""Integration tests for the dataset ingest layer.

Covers the cache policy laid out in ``ingest.py``:

- cold start with a working upstream → fetch + cache + return fresh.
- fresh cache → serve without hitting the network.
- stale cache + working upstream → refresh + cache.
- stale cache + broken upstream → serve cache with ``is_stale=true``.
- cold start + broken upstream → raise :class:`DatasetUnavailable`.
- force_refresh bypasses the TTL check.

The tests use a temporary SQLite file (via ``monkeypatch`` on
``webapp.backend.db.DB_PATH``) so they never touch the real webapp
database, and replace ``httpx.AsyncClient`` with a fake client so they
never touch the network.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

# Fixture CSV — the same deaths-per-TWh slice used in test_dataset_parsers.py
_DEATHS_CSV = b"""\
Entity,Year,Deaths per terawatt-hour of energy production
Biomass,2021,4.63
Coal,2021,24.62
Gas,2021,2.821
Hydropower,2021,1.3
Nuclear,2021,0.03
Solar,2021,0.02
Wind,2021,0.04
"""


# ---------------------------------------------------------------------------
# Test infrastructure: isolated DB + fake httpx client
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Redirect the backend's SQLite DB to an empty file per test.

    Patches ``webapp.backend.db.DB_PATH`` and runs ``init_db()`` so the
    ``external_datasets`` table exists. The tmp_path fixture gives each
    test a fresh file that pytest cleans up.
    """
    import webapp.backend.db as db_module

    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    monkeypatch.setattr(db_module, "_DB_DIR", tmp_path)

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        db_module.init_db())
    return test_db


class _FakeResponse:
    """Minimal stand-in for ``httpx.Response`` used by the ingest module.

    We only need ``status_code``, ``content``, ``headers``, and
    ``raise_for_status``.
    """

    def __init__(self, status_code: int, content: bytes = b"",
                 etag: str | None = None):
        self.status_code = status_code
        self.content = content
        self.headers = {"etag": etag} if etag else {}

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=None,  # type: ignore[arg-type]
                response=None,  # type: ignore[arg-type]
            )


class _FakeAsyncClient:
    """Programmable stand-in for ``httpx.AsyncClient``.

    Instances are configured with a response (or exception) to return
    from ``.get(url)``. Supports async-context-manager protocol so the
    existing ``async with httpx.AsyncClient(...)`` call in
    ``_fetch_upstream`` works without modification.
    """

    def __init__(self, response_factory):
        self._factory = response_factory
        self.calls: list[str] = []

    def __call__(self, *args, **kwargs):
        # httpx.AsyncClient(...) returns a client; we are the client.
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str):
        self.calls.append(url)
        return self._factory()


@pytest.fixture
def fake_http_ok(monkeypatch):
    """Install a fake httpx returning a 200 with the deaths CSV."""
    import webapp.backend.datasets.ingest as ingest_module

    client = _FakeAsyncClient(
        lambda: _FakeResponse(200, _DEATHS_CSV, etag='W/"abc123"'))
    monkeypatch.setattr(ingest_module.httpx, "AsyncClient", client)
    return client


@pytest.fixture
def fake_http_broken(monkeypatch):
    """Install a fake httpx that raises on every GET (simulates offline)."""
    import webapp.backend.datasets.ingest as ingest_module

    def _raise():
        raise httpx.ConnectError("simulated offline")

    client = _FakeAsyncClient(_raise)
    monkeypatch.setattr(ingest_module.httpx, "AsyncClient", client)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIngestCachePolicy:
    """End-to-end exercise of the cache policy implemented in ingest.py."""

    @pytest.mark.asyncio
    async def test_cold_start_fetch_and_cache(self, isolated_db,
                                               fake_http_ok):
        """First call with empty cache must fetch upstream, parse,
        store the row, and return the parsed payload with is_stale=False."""
        from webapp.backend.datasets.ingest import get_dataset

        result = await get_dataset("deaths_per_twh")

        assert result["is_stale"] is False
        assert len(result["rows"]) == 7
        assert fake_http_ok.calls  # upstream was hit

        # Cache row now exists and contains the parsed payload.
        from webapp.backend.db import get_external_dataset
        row = await get_external_dataset("deaths_per_twh")
        assert row is not None
        assert row["is_stale"] == 0
        parsed = json.loads(row["parsed_json"])
        assert len(parsed) == 7

    @pytest.mark.asyncio
    async def test_fresh_cache_no_network(self, isolated_db, fake_http_ok):
        """A second call within TTL must NOT hit the network."""
        from webapp.backend.datasets.ingest import get_dataset

        # Prime the cache.
        await get_dataset("deaths_per_twh")
        calls_after_first = len(fake_http_ok.calls)

        # Second call → served from cache.
        result = await get_dataset("deaths_per_twh")
        assert result["is_stale"] is False
        assert len(fake_http_ok.calls) == calls_after_first

    @pytest.mark.asyncio
    async def test_stale_fallback_on_network_failure(
            self, isolated_db, tmp_path, monkeypatch):
        """If the cache exists but refresh fails, serve the stale copy
        with is_stale=True instead of raising."""
        from webapp.backend.datasets.ingest import get_dataset
        import webapp.backend.datasets.ingest as ingest_module

        # Prime cache with a working client.
        ok_client = _FakeAsyncClient(
            lambda: _FakeResponse(200, _DEATHS_CSV))
        monkeypatch.setattr(ingest_module.httpx, "AsyncClient", ok_client)
        await get_dataset("deaths_per_twh")

        # Now flip the client to broken AND age the cache past TTL.
        def _raise():
            raise httpx.ConnectError("simulated offline")
        broken = _FakeAsyncClient(_raise)
        monkeypatch.setattr(ingest_module.httpx, "AsyncClient", broken)

        # Jump forward in time — replace ingest._now.
        future = datetime.now(timezone.utc) + timedelta(days=30)
        monkeypatch.setattr(ingest_module, "_now", lambda: future)

        result = await get_dataset("deaths_per_twh")
        assert result["is_stale"] is True
        assert len(result["rows"]) == 7

    @pytest.mark.asyncio
    async def test_cold_start_with_broken_upstream_raises(
            self, isolated_db, fake_http_broken):
        """No cache + upstream failure must raise DatasetUnavailable so
        the router can translate it to a 503."""
        from webapp.backend.datasets.ingest import (
            DatasetUnavailable,
            get_dataset,
        )

        with pytest.raises(DatasetUnavailable):
            await get_dataset("deaths_per_twh")

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_ttl(self, isolated_db,
                                               fake_http_ok):
        """``force_refresh=True`` must hit the upstream even when the
        cache is fresh — that's what POST /refresh relies on."""
        from webapp.backend.datasets.ingest import get_dataset

        await get_dataset("deaths_per_twh")
        calls_before = len(fake_http_ok.calls)

        await get_dataset("deaths_per_twh", force_refresh=True)
        assert len(fake_http_ok.calls) == calls_before + 1

    @pytest.mark.asyncio
    async def test_304_not_modified_preserves_payload(
            self, isolated_db, monkeypatch):
        """When upstream returns 304, we keep the cached payload and
        bump fetched_at without re-parsing."""
        from webapp.backend.datasets.ingest import get_dataset
        import webapp.backend.datasets.ingest as ingest_module

        # First fetch: 200 with ETag.
        ok = _FakeAsyncClient(
            lambda: _FakeResponse(200, _DEATHS_CSV, etag='W/"v1"'))
        monkeypatch.setattr(ingest_module.httpx, "AsyncClient", ok)
        await get_dataset("deaths_per_twh")

        # Second fetch (force_refresh): 304 → no body, payload preserved.
        not_modified = _FakeAsyncClient(lambda: _FakeResponse(304))
        monkeypatch.setattr(ingest_module.httpx, "AsyncClient", not_modified)
        result = await get_dataset("deaths_per_twh", force_refresh=True)

        assert result["is_stale"] is False
        assert len(result["rows"]) == 7  # unchanged

    @pytest.mark.asyncio
    async def test_unknown_slug_raises(self, isolated_db, fake_http_ok):
        """A slug that isn't in DATASET_SPECS must raise KeyError —
        the router converts this to an HTTP 404."""
        from webapp.backend.datasets.ingest import get_dataset

        with pytest.raises(KeyError):
            await get_dataset("no_such_slug")
