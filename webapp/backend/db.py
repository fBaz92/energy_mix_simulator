"""SQLite database setup and async helpers.

Manages three tables:
- ``scenarios``: saved scenario configurations (JSON blob).
- ``simulations``: simulation runs with status and summary stats.
- ``simulation_results``: heavy result JSON (1-5 MB), stored separately
  to keep list queries fast.

Uses ``aiosqlite`` for async access compatible with FastAPI's event loop.
The database file is stored at ``webapp/data/energy_sim.db`` (auto-created).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

# Database file location (sibling to the webapp package)
_DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = _DB_DIR / "energy_sim.db"

# Schema definition
_SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simulations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    n_runs INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    avg_price_mean REAL,
    avg_price_std REAL,
    total_emissions_mean_mt REAL,
    carbon_intensity_mean REAL,
    mean_inertia REAL,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    timeseries_path TEXT
);

CREATE TABLE IF NOT EXISTS simulation_results (
    simulation_id INTEGER PRIMARY KEY
        REFERENCES simulations(id) ON DELETE CASCADE,
    result_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sweeps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sweep_type TEXT NOT NULL,           -- '1d' | '2d'
    parameter_a TEXT NOT NULL,          -- dotted path, e.g. 'mix.nuclear.capacity_gw'
    values_a_json TEXT NOT NULL,        -- JSON list of floats
    parameter_b TEXT,                   -- 2d only
    values_b_json TEXT,                 -- 2d only
    n_runs_per_point INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    progress_current INTEGER NOT NULL DEFAULT 0,
    progress_total INTEGER NOT NULL,
    error_message TEXT,
    results_json TEXT,                  -- populated on completion
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL
);
"""


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string.

    Returns:
        ISO-formatted timestamp string.
    """
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> None:
    """Create the database directory and tables if they don't exist.

    Called once during FastAPI app startup (lifespan). Safe to call
    multiple times (uses ``CREATE TABLE IF NOT EXISTS``).

    Also runs idempotent schema migrations for columns added after the
    initial release:
    - ``simulations.timeseries_path``: path to the optional Parquet file
      storing per-run quarter-hour time-series (added for PART B).
    """
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        # Migration: add timeseries_path column if missing. SQLite's
        # CREATE TABLE IF NOT EXISTS will leave old tables alone, so we
        # check the column list and ALTER TABLE when needed.
        cursor = await db.execute("PRAGMA table_info(simulations)")
        existing_cols = {row[1] for row in await cursor.fetchall()}
        if "timeseries_path" not in existing_cols:
            await db.execute(
                "ALTER TABLE simulations ADD COLUMN timeseries_path TEXT")
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    """Open a new async database connection.

    Caller is responsible for closing (use ``async with`` or explicit close).
    Row factory is set to ``aiosqlite.Row`` for dict-like access.

    Returns:
        An open ``aiosqlite.Connection`` with row factory and foreign keys.
    """
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    return db


# ---------------------------------------------------------------------------
# Scenario CRUD helpers
# ---------------------------------------------------------------------------

async def create_scenario(name: str, description: str,
                          config: dict) -> dict[str, Any]:
    """Insert a new scenario and return its row as a dict.

    Args:
        name: Human-readable scenario name.
        description: Optional description.
        config: Full scenario configuration (ScenarioCreate body as dict).

    Returns:
        Dict with keys: id, name, description, config_json, created_at,
        updated_at.
    """
    now = _now_iso()
    config_json = json.dumps(config, ensure_ascii=False)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cursor = await db.execute(
            """INSERT INTO scenarios (name, description, config_json,
                                     created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (name, description, config_json, now, now),
        )
        await db.commit()
        row = await (await db.execute(
            "SELECT * FROM scenarios WHERE id = ?", (cursor.lastrowid,)
        )).fetchone()
        return dict(row)


async def list_scenarios() -> list[dict[str, Any]]:
    """Return all scenarios (without config_json) ordered by creation time.

    Returns:
        List of dicts with keys: id, name, description, created_at, updated_at.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            """SELECT id, name, description, created_at, updated_at
               FROM scenarios ORDER BY created_at DESC"""
        )).fetchall()
        return [dict(r) for r in rows]


async def get_scenario(scenario_id: int) -> dict[str, Any] | None:
    """Fetch a single scenario by ID, including its full config.

    Args:
        scenario_id: Primary key of the scenario.

    Returns:
        Dict with all columns, or None if not found.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT * FROM scenarios WHERE id = ?", (scenario_id,)
        )).fetchone()
        return dict(row) if row else None


async def update_scenario(scenario_id: int, name: str, description: str,
                          config: dict) -> dict[str, Any] | None:
    """Update an existing scenario's name, description, and config.

    Args:
        scenario_id: Primary key of the scenario to update.
        name: New name.
        description: New description.
        config: New full config dict.

    Returns:
        Updated row as dict, or None if not found.
    """
    now = _now_iso()
    config_json = json.dumps(config, ensure_ascii=False)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cursor = await db.execute(
            """UPDATE scenarios
               SET name = ?, description = ?, config_json = ?, updated_at = ?
               WHERE id = ?""",
            (name, description, config_json, now, scenario_id),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None
        row = await (await db.execute(
            "SELECT * FROM scenarios WHERE id = ?", (scenario_id,)
        )).fetchone()
        return dict(row)


async def delete_scenario(scenario_id: int) -> bool:
    """Delete a scenario and its cascaded simulations/results.

    Args:
        scenario_id: Primary key of the scenario to delete.

    Returns:
        True if a row was deleted, False if not found.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        cursor = await db.execute(
            "DELETE FROM scenarios WHERE id = ?", (scenario_id,),
        )
        await db.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Simulation CRUD helpers
# ---------------------------------------------------------------------------

async def create_simulation(scenario_id: int, n_runs: int) -> dict[str, Any]:
    """Insert a new simulation row with status 'pending'.

    Args:
        scenario_id: Associated scenario ID.
        n_runs: Number of Monte Carlo runs to execute.

    Returns:
        Dict of the new row.
    """
    now = _now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cursor = await db.execute(
            """INSERT INTO simulations (scenario_id, status, n_runs, created_at)
               VALUES (?, 'pending', ?, ?)""",
            (scenario_id, n_runs, now),
        )
        await db.commit()
        row = await (await db.execute(
            "SELECT * FROM simulations WHERE id = ?", (cursor.lastrowid,)
        )).fetchone()
        return dict(row)


async def get_simulation(simulation_id: int) -> dict[str, Any] | None:
    """Fetch a simulation row by ID (without the heavy result blob).

    Args:
        simulation_id: Primary key.

    Returns:
        Dict of the row, or None if not found.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT * FROM simulations WHERE id = ?", (simulation_id,)
        )).fetchone()
        return dict(row) if row else None


async def list_simulations() -> list[dict[str, Any]]:
    """List all simulations with their scenario names.

    Returns:
        List of dicts with simulation fields + scenario_name, ordered
        by creation time descending.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            """SELECT s.*, sc.name as scenario_name
               FROM simulations s
               JOIN scenarios sc ON s.scenario_id = sc.id
               ORDER BY s.created_at DESC"""
        )).fetchall()
        return [dict(r) for r in rows]


async def update_simulation_status(
    simulation_id: int,
    status: str,
    error_message: str | None = None,
    summary: dict[str, float] | None = None,
) -> None:
    """Update a simulation's status and optionally its summary stats.

    Called by the background task runner on start, completion, or failure.

    Args:
        simulation_id: Primary key.
        status: New status ('running', 'completed', 'failed').
        error_message: Error details (only for 'failed').
        summary: Dict of summary stats to write (keys match column names).
    """
    now = _now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        if status == "running":
            await db.execute(
                "UPDATE simulations SET status = ?, started_at = ? WHERE id = ?",
                (status, now, simulation_id),
            )
        elif status == "completed":
            sets = ["status = ?", "completed_at = ?"]
            vals: list[Any] = [status, now]
            if summary:
                for key, val in summary.items():
                    sets.append(f"{key} = ?")
                    vals.append(val)
            vals.append(simulation_id)
            await db.execute(
                f"UPDATE simulations SET {', '.join(sets)} WHERE id = ?",
                tuple(vals),
            )
        elif status == "failed":
            await db.execute(
                """UPDATE simulations
                   SET status = ?, completed_at = ?, error_message = ?
                   WHERE id = ?""",
                (status, now, error_message, simulation_id),
            )
        await db.commit()


async def store_simulation_result(simulation_id: int,
                                  result_dict: dict) -> None:
    """Store the full MC result JSON in the simulation_results table.

    Args:
        simulation_id: Associated simulation ID.
        result_dict: Output of ``mc_result_to_dict()``.
    """
    result_json = json.dumps(result_dict, ensure_ascii=False)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO simulation_results
               (simulation_id, result_json) VALUES (?, ?)""",
            (simulation_id, result_json),
        )
        await db.commit()


async def get_simulation_result(simulation_id: int) -> dict | None:
    """Fetch the full MC result JSON for a simulation.

    Args:
        simulation_id: Associated simulation ID.

    Returns:
        Parsed result dict, or None if not found.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT result_json FROM simulation_results WHERE simulation_id = ?",
            (simulation_id,),
        )).fetchone()
        if row:
            return json.loads(row["result_json"])
        return None


async def delete_simulation(simulation_id: int) -> str | None | bool:
    """Delete a simulation and its result, returning the time-series path.

    The caller is responsible for unlinking the Parquet file (if any)
    referenced by the returned path — SQLite cannot clean up filesystem
    artifacts on its own.

    Args:
        simulation_id: Primary key of the simulation to delete.

    Returns:
        The ``timeseries_path`` of the deleted row (possibly ``None``)
        when deletion succeeded, or ``False`` when no row matched the
        given id. Using a distinct sentinel for the not-found case
        preserves the previous boolean contract at the call site.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        row = await (await db.execute(
            "SELECT timeseries_path FROM simulations WHERE id = ?",
            (simulation_id,),
        )).fetchone()
        if row is None:
            return False
        cursor = await db.execute(
            "DELETE FROM simulations WHERE id = ?", (simulation_id,),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return False
        return row["timeseries_path"]


async def set_timeseries_path(simulation_id: int, path: str) -> None:
    """Record the on-disk location of the Parquet time-series file.

    Written by :func:`webapp.backend.tasks.run_simulation_task` after the
    MC runner completes and :mod:`webapp.backend.timeseries_io` has
    serialised the per-run quarter-hour arrays to disk.

    Args:
        simulation_id: Primary key of the simulation.
        path: Absolute path (or path relative to the project root) of
            the Parquet file.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE simulations SET timeseries_path = ? WHERE id = ?",
            (path, simulation_id),
        )
        await db.commit()


async def get_timeseries_path(simulation_id: int) -> str | None:
    """Return the stored Parquet path for a simulation, if any.

    Args:
        simulation_id: Primary key of the simulation.

    Returns:
        The path string or ``None`` if the simulation has no
        time-series file (legacy runs completed before PART B, or rows
        whose Parquet payload was never written).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT timeseries_path FROM simulations WHERE id = ?",
            (simulation_id,),
        )).fetchone()
        return row["timeseries_path"] if row else None


# ---------------------------------------------------------------------------
# Sweep CRUD helpers
# ---------------------------------------------------------------------------

async def create_sweep(
    scenario_id: int,
    name: str,
    sweep_type: str,
    parameter_a: str,
    values_a: list[float],
    parameter_b: str | None,
    values_b: list[float] | None,
    n_runs_per_point: int,
) -> dict[str, Any]:
    """Insert a new sweep row with status 'pending'.

    Args:
        scenario_id: Associated scenario ID.
        name: Human-readable label (e.g. "Nuclear 0–20 GW, base gas").
        sweep_type: Either ``'1d'`` or ``'2d'``.
        parameter_a: Dotted override path (e.g. ``mix.nuclear.capacity_gw``).
        values_a: Values for parameter A.
        parameter_b: Dotted path for 2D sweeps, otherwise ``None``.
        values_b: Values for parameter B, otherwise ``None``.
        n_runs_per_point: Number of MC runs executed at each grid point.

    Returns:
        Dict of the new row.
    """
    now = _now_iso()
    total = len(values_a) * (len(values_b) if values_b else 1)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cursor = await db.execute(
            """INSERT INTO sweeps (
                scenario_id, name, sweep_type, parameter_a, values_a_json,
                parameter_b, values_b_json, n_runs_per_point,
                status, progress_total, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (scenario_id, name, sweep_type, parameter_a,
             json.dumps(values_a),
             parameter_b,
             json.dumps(values_b) if values_b is not None else None,
             n_runs_per_point, total, now),
        )
        await db.commit()
        row = await (await db.execute(
            "SELECT * FROM sweeps WHERE id = ?", (cursor.lastrowid,)
        )).fetchone()
        return dict(row)


async def list_sweeps() -> list[dict[str, Any]]:
    """List all sweeps with their scenario names.

    Returns:
        List of dicts with sweep fields + ``scenario_name``, ordered
        by creation time descending.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            """SELECT sw.*, sc.name as scenario_name
               FROM sweeps sw
               JOIN scenarios sc ON sw.scenario_id = sc.id
               ORDER BY sw.created_at DESC"""
        )).fetchall()
        return [dict(r) for r in rows]


async def get_sweep(sweep_id: int) -> dict[str, Any] | None:
    """Fetch a sweep row by ID (including results_json if populated).

    Args:
        sweep_id: Primary key.

    Returns:
        Dict of the row, or ``None`` if not found.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT * FROM sweeps WHERE id = ?", (sweep_id,)
        )).fetchone()
        return dict(row) if row else None


async def update_sweep_progress(sweep_id: int, current: int) -> None:
    """Update the ``progress_current`` counter for a running sweep.

    Called by the background runner after each grid point completes so
    the frontend poll endpoint can render a progress bar.

    Args:
        sweep_id: Primary key.
        current: Number of grid points completed so far.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sweeps SET progress_current = ? WHERE id = ?",
            (current, sweep_id),
        )
        await db.commit()


async def update_sweep_status(
    sweep_id: int,
    status: str,
    error_message: str | None = None,
    results_json: str | None = None,
) -> None:
    """Transition a sweep to ``running`` / ``completed`` / ``failed``.

    Args:
        sweep_id: Primary key.
        status: New status (``running``, ``completed``, or ``failed``).
        error_message: Traceback string when transitioning to ``failed``.
        results_json: Serialised ``SweepFullResult`` payload when the
            sweep completes.
    """
    now = _now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        if status == "running":
            await db.execute(
                "UPDATE sweeps SET status = ?, started_at = ? WHERE id = ?",
                (status, now, sweep_id),
            )
        elif status == "completed":
            await db.execute(
                """UPDATE sweeps
                   SET status = ?, completed_at = ?, results_json = ?
                   WHERE id = ?""",
                (status, now, results_json, sweep_id),
            )
        elif status == "failed":
            await db.execute(
                """UPDATE sweeps
                   SET status = ?, completed_at = ?, error_message = ?
                   WHERE id = ?""",
                (status, now, error_message, sweep_id),
            )
        await db.commit()


async def delete_sweep(sweep_id: int) -> bool:
    """Delete a sweep row.

    Args:
        sweep_id: Primary key.

    Returns:
        ``True`` if a row was deleted, ``False`` otherwise.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        cursor = await db.execute(
            "DELETE FROM sweeps WHERE id = ?", (sweep_id,),
        )
        await db.commit()
        return cursor.rowcount > 0
