"""Tests for the Parquet time-series I/O module.

Covers the roundtrip contract that the webapp lazy-load endpoint
depends on: after :func:`write_timeseries_parquet` serialises a list of
``DispatchResult`` objects, the reader must return the same arrays for
any combination of run index and series names.

These tests deliberately use a tiny scenario (2 runs, default Italian
mix) to keep them inside the fast test tier — full Parquet I/O takes
<1 s end-to-end.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from energy_sim.config import GAS_SCENARIOS, ITALIAN_MIX, STORAGE_UNITS
from energy_sim.simulation import run_monte_carlo
from webapp.backend.timeseries_io import (
    list_timeseries_columns,
    read_timeseries_metadata,
    read_timeseries_parquet,
    timeseries_n_runs,
    write_timeseries_parquet,
)


@pytest.fixture(scope="module")
def parquet_with_storage():
    """Run a mini-MC and persist its per-run dispatches to a Parquet file.

    Module-scoped so the expensive MC runs only once per test session.
    Uses storage to exercise the ``storage_*`` column family.
    """
    captured: list = []
    run_monte_carlo(
        ITALIAN_MIX,
        GAS_SCENARIOS["base"],
        n_runs=2,
        seed=42,
        storage_cfg=STORAGE_UNITS,
        dispatch_callback=lambda _i, r: captured.append(r),
    )
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "ts.parquet"
        info = write_timeseries_parquet(str(path), captured)
        yield path, info, captured


class TestWriterMetadata:
    """Exercise the informational return value of the writer."""

    def test_write_info_shape(self, parquet_with_storage):
        """``info`` must report the number of runs, timesteps and non-zero
        byte count so callers can log storage usage.
        """
        _, info, captured = parquet_with_storage
        assert info["n_runs"] == len(captured) == 2
        assert info["n_t"] == 35040
        assert info["bytes_on_disk"] > 0
        assert len(info["series"]) >= 5  # at minimum the scalar family

    def test_row_group_per_run(self, parquet_with_storage):
        """One row group per run enables predicate pushdown on ``run_idx``."""
        path, _, _ = parquet_with_storage
        assert timeseries_n_runs(str(path)) == 2


class TestColumnFamily:
    """Verify that every expected column family is present for a
    scenario that enables storage and the default Italian mix.
    """

    def test_scalar_series_present(self, parquet_with_storage):
        """The four per-timestep scalar arrays must be stored verbatim."""
        path, _, _ = parquet_with_storage
        cols = set(list_timeseries_columns(str(path)))
        assert {"marginal_price", "curtailment", "h_system",
                "unserved", "price_setter_idx"} <= cols

    def test_per_generator_columns(self, parquet_with_storage):
        """Each generator in the mix must contribute a ``power_*`` column."""
        path, _, captured = parquet_with_storage
        cols = set(list_timeseries_columns(str(path)))
        for name in captured[0].gen_names:
            safe = "".join(ch if ch.isalnum() or ch in "_-" else "_"
                           for ch in name)
            assert f"power_{safe}" in cols

    def test_storage_columns(self, parquet_with_storage):
        """Each storage unit contributes ``storage_power_*`` and
        ``storage_soc_*`` pairs.
        """
        path, _, captured = parquet_with_storage
        cols = set(list_timeseries_columns(str(path)))
        for name in captured[0].storage_names:
            safe = "".join(ch if ch.isalnum() or ch in "_-" else "_"
                           for ch in name)
            assert f"storage_power_{safe}" in cols
            assert f"storage_soc_{safe}" in cols


class TestRoundtrip:
    """The reader must faithfully reproduce the arrays originally written
    by the writer. The time-axis is reassembled via ``qh_idx`` sort so
    the contract holds even if Parquet internally reorders rows.
    """

    def test_marginal_price_roundtrip(self, parquet_with_storage):
        """Roundtrip on a scalar series — the usual sanity check."""
        path, _, captured = parquet_with_storage
        out = read_timeseries_parquet(
            str(path), run_idx=1, series_names=["marginal_price"])
        expected = captured[1].marginal_price.astype(np.float32)
        np.testing.assert_allclose(out["marginal_price"], expected, rtol=0)

    def test_price_setter_roundtrip(self, parquet_with_storage):
        """``price_setter_idx`` is int16 with sentinel ``-1`` — the reader
        must not coerce it into a float that loses the sentinel.
        """
        path, _, captured = parquet_with_storage
        out = read_timeseries_parquet(
            str(path), run_idx=0, series_names=["price_setter_idx"])
        expected = captured[0].price_setter_idx.astype(np.int16)
        got = np.asarray(out["price_setter_idx"], dtype=np.int16)
        np.testing.assert_array_equal(got, expected)

    def test_per_generator_roundtrip(self, parquet_with_storage):
        """A generator power column must match the per-row dispatched
        power for that unit.
        """
        path, _, captured = parquet_with_storage
        gen_names = list(captured[0].gen_names)
        gas_idx = gen_names.index("gas")
        out = read_timeseries_parquet(
            str(path), run_idx=0, series_names=["power_gas"])
        expected = captured[0].power[gas_idx].astype(np.float32)
        np.testing.assert_allclose(out["power_gas"], expected, rtol=0)

    def test_unknown_series_silently_skipped(self, parquet_with_storage):
        """The contract explicitly says unknown series names are silently
        skipped — this is critical for frontend code that requests the
        union of optional series without introspecting the schema first.
        """
        path, _, _ = parquet_with_storage
        out = read_timeseries_parquet(
            str(path), run_idx=0,
            series_names=["marginal_price", "does_not_exist"])
        assert set(out.keys()) == {"marginal_price"}

    def test_out_of_range_run_raises(self, parquet_with_storage):
        """Reading a run beyond the stored range must raise ``ValueError``
        — the endpoint layer turns this into an HTTP 400.
        """
        path, _, _ = parquet_with_storage
        with pytest.raises(ValueError):
            read_timeseries_parquet(
                str(path), run_idx=99, series_names=["marginal_price"])

    def test_missing_file_raises(self, tmp_path):
        """A missing Parquet file must raise ``FileNotFoundError`` so the
        endpoint layer can return HTTP 404.
        """
        with pytest.raises(FileNotFoundError):
            read_timeseries_parquet(
                str(tmp_path / "nope.parquet"),
                run_idx=0, series_names=["marginal_price"])


class TestMetadata:
    """The Parquet schema carries JSON-encoded dispatch metadata so the
    reader can reconstruct the ``price_setter_idx`` → technology-label
    mapping without ever opening the file body.
    """

    def test_metadata_present(self, parquet_with_storage):
        """Metadata must contain the four expected keys, each a list."""
        path, _, _ = parquet_with_storage
        meta = read_timeseries_metadata(str(path))
        assert set(meta.keys()) == {
            "gen_names", "gen_types", "storage_names",
            "interconnection_names",
        }
        for v in meta.values():
            assert isinstance(v, list)

    def test_gen_names_match_writer_input(self, parquet_with_storage):
        """``gen_names`` must mirror the ``DispatchResult`` ordering used
        by ``price_setter_idx`` to index into the unit array.
        """
        path, _, captured = parquet_with_storage
        meta = read_timeseries_metadata(str(path))
        assert meta["gen_names"] == list(captured[0].gen_names)

    def test_gen_types_same_length_as_names(self, parquet_with_storage):
        """Types must pair 1:1 with names so the frontend can collapse
        imports regardless of user-chosen link labels.
        """
        path, _, _ = parquet_with_storage
        meta = read_timeseries_metadata(str(path))
        assert len(meta["gen_types"]) == len(meta["gen_names"])


class TestWriterValidation:
    """Input validation on the writer prevents silent corruption."""

    def test_empty_list_raises(self, tmp_path):
        """Writing with an empty dispatch list is an application bug."""
        with pytest.raises(ValueError):
            write_timeseries_parquet(
                str(tmp_path / "empty.parquet"), [])
