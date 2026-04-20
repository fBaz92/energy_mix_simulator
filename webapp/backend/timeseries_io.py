"""Parquet serialisation of per-run quarter-hour dispatch time-series.

Serialising the full 15-minute Monte Carlo output as JSON is infeasible:
for a typical mix with ~5 generators, 1 battery and 2 interconnections,
100 runs of 35 040 quarter-hours produce ~140 MB of float data per
simulation, which would balloon past 500 MB once encoded as JSON.

This module writes the data to a single **Parquet file per simulation**
using a *wide* schema — one row per ``(run_idx, qh_idx)`` pair, one
column per time-series. Dynamic columns cope with the variable set of
generator / storage / interconnection names produced by each scenario.
Storage overhead with snappy compression is ~15-30 MB per simulation.

Row groups are sized to exactly one run (``row_group_size = n_t``) so
that the lazy read endpoint ``GET /api/simulations/{id}/timeseries``
can use predicate pushdown (``filters=[('run_idx', '=', X)]``) and only
decode the requested run's row group.

The shared helpers :func:`write_timeseries_parquet` and
:func:`read_timeseries_parquet` are the sole I/O surface — the FastAPI
route adapts them, and the background worker :mod:`webapp.backend.tasks`
invokes the writer once the Monte Carlo runner finishes.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from energy_sim.dispatch import DispatchResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Scalar fields that live as a single column each.
_SCALAR_SERIES = (
    "marginal_price",
    "curtailment",
    "h_system",
    "unserved",
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_TS_DIR = Path(__file__).resolve().parent.parent / "data" / "timeseries"


def timeseries_dir() -> Path:
    """Return the absolute directory that holds Parquet time-series files.

    Creates the directory on first access so callers do not have to
    guard against the missing-directory case.

    Returns:
        Path to ``webapp/data/timeseries``.
    """
    _TS_DIR.mkdir(parents=True, exist_ok=True)
    return _TS_DIR


def parquet_path_for(simulation_id: int) -> Path:
    """Return the canonical Parquet path for a given simulation id.

    Args:
        simulation_id: Primary key of the simulation row.

    Returns:
        Path ``webapp/data/timeseries/{simulation_id}.parquet``.
    """
    return timeseries_dir() / f"{simulation_id}.parquet"


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def _sanitize_column(name: str) -> str:
    """Make a series name safe to use as a Parquet column.

    Replaces whitespace and characters that can interfere with shell
    piping / URL encoding with ``_``. Generator and interconnection
    names already follow an ``ascii_snake_case`` convention in
    ``config.py``, but user-supplied names (e.g. imported CSV scenarios)
    may not — so the sanitisation is deliberately lenient.

    Args:
        name: Raw series name.

    Returns:
        Sanitised column identifier.
    """
    out = []
    for ch in name:
        if ch.isalnum() or ch in ("_", "-"):
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)


def write_timeseries_parquet(
    path: str | Path,
    dispatch_results: list[DispatchResult],
) -> dict:
    """Serialise one Parquet file with all MC runs of one simulation.

    The file is written with snappy compression and row groups of size
    ``n_t`` (one row group per run) so that the lazy reader can decode a
    single run without touching the others.

    Args:
        path: Destination path of the Parquet file. The parent
            directory must already exist.
        dispatch_results: Ordered list of per-run ``DispatchResult``
            objects returned by :func:`~energy_sim.dispatch.dispatch_year`.
            Every run must share the same ``gen_names``, ``storage_names``,
            ``interconnection_names`` and ``n_t`` — a contract enforced
            by the Monte Carlo runner.

    Returns:
        Dict with ``n_runs``, ``n_t``, ``series`` (list of column names
        excluding the index columns) and ``bytes_on_disk``. Useful for
        logging and test assertions.

    Raises:
        ValueError: If ``dispatch_results`` is empty or if per-run
            shapes are inconsistent.
    """
    if not dispatch_results:
        raise ValueError(
            "write_timeseries_parquet: dispatch_results is empty")
    n_runs = len(dispatch_results)
    first = dispatch_results[0]
    n_t = int(first.marginal_price.shape[0])
    gen_names = list(first.gen_names)
    storage_names = list(first.storage_names)
    ic_names = list(first.interconnection_names)

    # Shape consistency: a mismatch usually means the caller mixed
    # dispatches from different scenarios, which would corrupt the
    # wide-format layout silently.
    for r in dispatch_results[1:]:
        if (int(r.marginal_price.shape[0]) != n_t
                or list(r.gen_names) != gen_names
                or list(r.storage_names) != storage_names
                or list(r.interconnection_names) != ic_names):
            raise ValueError(
                "write_timeseries_parquet: inconsistent shapes or names "
                "across dispatch_results")

    # --- Build arrays ----------------------------------------------------
    arrays: dict[str, np.ndarray] = {}
    arrays["run_idx"] = np.repeat(
        np.arange(n_runs, dtype=np.int16), n_t)
    arrays["qh_idx"] = np.tile(
        np.arange(n_t, dtype=np.int32), n_runs)

    for field in _SCALAR_SERIES:
        arrays[field] = np.concatenate(
            [getattr(r, field).astype(np.float32)
             for r in dispatch_results])

    # price_setter_idx is already int16 from dispatch.
    arrays["price_setter_idx"] = np.concatenate(
        [r.price_setter_idx.astype(np.int16) for r in dispatch_results])

    for i, name in enumerate(gen_names):
        col = f"power_{_sanitize_column(name)}"
        arrays[col] = np.concatenate(
            [r.power[i].astype(np.float32) for r in dispatch_results])

    for i, name in enumerate(storage_names):
        p_col = f"storage_power_{_sanitize_column(name)}"
        s_col = f"storage_soc_{_sanitize_column(name)}"
        arrays[p_col] = np.concatenate(
            [r.storage_power_pu[i].astype(np.float32)
             for r in dispatch_results])
        arrays[s_col] = np.concatenate(
            [r.storage_soc[i].astype(np.float32)
             for r in dispatch_results])

    for i, name in enumerate(ic_names):
        n_col = f"net_import_{_sanitize_column(name)}"
        f_col = f"foreign_price_{_sanitize_column(name)}"
        arrays[n_col] = np.concatenate(
            [r.net_import_pu[i].astype(np.float32)
             for r in dispatch_results])
        arrays[f_col] = np.concatenate(
            [r.foreign_prices[i].astype(np.float32)
             for r in dispatch_results])

    # Store the dispatch metadata (gen names, gen types, storage/IC
    # names) as schema-level key/value pairs so the reader can
    # reconstruct the index → technology-label mapping used by the
    # price-setter duration-curve chart. JSON keeps the format simple
    # and extensible. All values are UTF-8 encoded.
    gen_types = list(first.gen_types) if first.gen_types else list(gen_names)
    schema_metadata = {
        b"gen_names": json.dumps(gen_names).encode("utf-8"),
        b"gen_types": json.dumps(gen_types).encode("utf-8"),
        b"storage_names": json.dumps(storage_names).encode("utf-8"),
        b"interconnection_names": json.dumps(ic_names).encode("utf-8"),
    }
    table = pa.table(arrays).replace_schema_metadata(schema_metadata)

    # One row group per run enables predicate pushdown on ``run_idx``.
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, p, compression="snappy", row_group_size=n_t)

    series = [c for c in arrays if c not in ("run_idx", "qh_idx")]
    return {
        "n_runs": n_runs,
        "n_t": n_t,
        "series": series,
        "bytes_on_disk": p.stat().st_size,
    }


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def read_timeseries_parquet(
    path: str | Path,
    run_idx: int,
    series_names: list[str],
) -> dict[str, list[float]]:
    """Read selected series for a single run from a Parquet file.

    Reads exactly the columns requested plus ``run_idx`` / ``qh_idx``
    for filtering and alignment. Row-group pushdown restricts decoding
    to the target run's 35 040-row block, so the operation is O(n_t)
    regardless of the number of runs in the file.

    Args:
        path: Parquet file path produced by
            :func:`write_timeseries_parquet`.
        run_idx: Zero-based MC run index.
        series_names: Column names to return (e.g.
            ``["marginal_price", "power_gas", "price_setter_idx"]``).
            Unknown names are silently skipped: callers frequently ask
            for optional columns (``storage_*`` in a no-storage scenario)
            and a strict error would force them to introspect the
            schema first.

    Returns:
        Dict ``{series_name: [values...]}`` with ``n_t`` floats per
        series. Returns an empty dict only if ``series_names`` is
        empty; an empty output for a non-empty request means none of
        the requested columns exist in the file.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If ``run_idx`` is outside the stored range.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Parquet file not found: {p}")

    schema = pq.read_schema(p)
    known = set(schema.names)
    wanted = [s for s in series_names if s in known]
    # Always fetch the two index columns to enable sorting and runtime
    # validation of ``run_idx``.
    cols = ["run_idx", "qh_idx"] + wanted
    # Deduplicate while preserving order (caller could pass ``run_idx``
    # by accident).
    seen: set[str] = set()
    cols = [c for c in cols if not (c in seen or seen.add(c))]

    table = pq.read_table(
        p,
        columns=cols,
        filters=[("run_idx", "=", int(run_idx))],
    )
    if table.num_rows == 0:
        raise ValueError(
            f"run_idx={run_idx} has no rows in {p.name}")

    # Sort by qh_idx so the returned arrays are time-ordered regardless
    # of the row-group layout.
    sort_idx = np.argsort(table.column("qh_idx").to_numpy())
    out: dict[str, list[float]] = {}
    for col in wanted:
        values = table.column(col).to_numpy()[sort_idx]
        out[col] = values.tolist()
    return out


def list_timeseries_columns(path: str | Path) -> list[str]:
    """Return the set of series columns stored in a Parquet file.

    Useful for the ``GET /timeseries/columns`` introspection endpoint
    so the frontend can render only the charts whose data is present.

    Args:
        path: Parquet file path.

    Returns:
        Column names excluding the index columns ``run_idx`` / ``qh_idx``.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Parquet file not found: {p}")
    schema = pq.read_schema(p)
    return [n for n in schema.names if n not in ("run_idx", "qh_idx")]


def read_timeseries_metadata(path: str | Path) -> dict:
    """Return the dispatch metadata stored alongside the Parquet payload.

    The writer embeds ``gen_names``, ``gen_types``, ``storage_names``
    and ``interconnection_names`` as schema-level key/value pairs so
    the reader can reconstruct the mapping from ``price_setter_idx``
    to technology labels without touching the file body.

    Args:
        path: Parquet file path.

    Returns:
        Dict with keys ``gen_names``, ``gen_types``, ``storage_names``,
        ``interconnection_names`` — each a ``list[str]``. Missing keys
        (files written before the metadata was added) return empty
        lists for forward compatibility.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Parquet file not found: {p}")
    schema = pq.read_schema(p)
    kv = schema.metadata or {}

    def _decode(key: bytes) -> list[str]:
        raw = kv.get(key)
        if not raw:
            return []
        try:
            return list(json.loads(raw.decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            return []

    return {
        "gen_names": _decode(b"gen_names"),
        "gen_types": _decode(b"gen_types"),
        "storage_names": _decode(b"storage_names"),
        "interconnection_names": _decode(b"interconnection_names"),
    }


def timeseries_n_runs(path: str | Path) -> int:
    """Return the number of distinct MC runs stored in a Parquet file.

    Reads only the schema's row-group metadata, which is O(1) in the
    file size.

    Args:
        path: Parquet file path.

    Returns:
        Number of row groups, which equals the number of runs under
        our one-row-group-per-run convention.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Parquet file not found: {p}")
    meta = pq.read_metadata(p)
    return meta.num_row_groups
