"""Background simulation task runner.

Runs ``energy_sim.simulation.run_monte_carlo()`` in a thread pool executor
to avoid blocking the FastAPI event loop (the simulation is CPU-bound,
taking 2-7 seconds depending on mix complexity and n_runs).

Progress tracking uses a module-level dict ``_progress`` keyed by
simulation ID. The FastAPI poll endpoint reads this dict to report
progress to the frontend.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from energy_sim.simulation import run_monte_carlo

from webapp.backend.db import (
    get_scenario,
    get_sweep,
    set_timeseries_path,
    store_simulation_result,
    update_simulation_status,
    update_sweep_progress,
    update_sweep_status,
)
from webapp.backend.models import ScenarioCreate
from webapp.backend.serializers import mc_result_to_dict, scenario_to_sim_config
from webapp.backend.sweeps import run_sweep
from webapp.backend.timeseries_io import (
    parquet_path_for,
    write_timeseries_parquet,
)

# Dedicated thread pool for sweep tasks so a long sweep (e.g. 10 × 10 ×
# 30 MC runs ≈ 10 min CPU) does not starve normal simulation launches
# on the default executor.
_sweep_executor = ThreadPoolExecutor(max_workers=2)

logger = logging.getLogger(__name__)

# In-memory progress store: {simulation_id: fraction 0.0-1.0}
_progress: dict[int, float] = {}


def get_progress(simulation_id: int) -> float:
    """Return current progress for a simulation (0.0 to 1.0).

    Args:
        simulation_id: The simulation being tracked.

    Returns:
        Progress fraction, or 0.0 if not tracked.
    """
    return _progress.get(simulation_id, 0.0)


def _run_mc_sync(sim_config, simulation_id: int):
    """Synchronous wrapper that runs MC and updates progress.

    Designed to be called inside ``loop.run_in_executor()``. Collects
    per-run :class:`DispatchResult` objects so the caller can serialise
    them to Parquet once the MC completes.

    Args:
        sim_config: A ``SimulationConfig`` instance.
        simulation_id: Used to update the progress dict.

    Returns:
        Tuple ``(mc_result, per_run_dispatch_results)`` with the
        aggregated MC output and the ordered list of per-run dispatches.
    """
    def progress_cb(fraction: float) -> None:
        _progress[simulation_id] = fraction

    per_run: list = []

    def dispatch_cb(_run_idx: int, dispatch_result) -> None:
        per_run.append(dispatch_result)

    result = run_monte_carlo(
        sim_config,
        progress_callback=progress_cb,
        dispatch_callback=dispatch_cb,
    )
    return result, per_run


async def run_simulation_task(simulation_id: int, scenario_id: int) -> None:
    """Background task: load scenario, run MC, store results.

    This coroutine is launched via FastAPI's BackgroundTasks. It:
    1. Loads the scenario config from the DB.
    2. Converts it to a ``SimulationConfig``.
    3. Runs the MC simulation in a thread pool.
    4. Serializes and stores the result.
    5. Updates the simulation status to 'completed' or 'failed'.

    Args:
        simulation_id: The simulation row to update.
        scenario_id: The scenario whose config to load.
    """
    _progress[simulation_id] = 0.0

    try:
        # Mark as running
        await update_simulation_status(simulation_id, "running")

        # Load scenario config
        scenario_row = await get_scenario(scenario_id)
        if not scenario_row:
            raise ValueError(f"Scenario {scenario_id} not found")

        import json
        config_dict = json.loads(scenario_row["config_json"])
        scenario = ScenarioCreate(**config_dict)
        sim_config = scenario_to_sim_config(scenario)

        # Run MC in thread pool (CPU-bound)
        loop = asyncio.get_event_loop()
        mc_result, per_run_dispatch = await loop.run_in_executor(
            None, _run_mc_sync, sim_config, simulation_id
        )

        # Serialize and store
        result_dict = mc_result_to_dict(mc_result)
        await store_simulation_result(simulation_id, result_dict)

        # Persist per-run quarter-hour time-series to Parquet. The file
        # sits beside the DB in ``webapp/data/timeseries/`` and is
        # referenced by ``simulations.timeseries_path``. We do this
        # off-loop in a thread pool because pyarrow serialisation is
        # CPU-bound for 100 MC runs × 35 040 qh.
        if per_run_dispatch:
            ts_path = parquet_path_for(simulation_id)
            await loop.run_in_executor(
                None, write_timeseries_parquet,
                str(ts_path), per_run_dispatch,
            )
            await set_timeseries_path(simulation_id, str(ts_path))

        # Compute summary stats
        summary = {
            "avg_price_mean": float(np.mean(mc_result.avg_price)),
            "avg_price_std": float(np.std(mc_result.avg_price)),
            "total_emissions_mean_mt": float(
                np.mean(mc_result.total_emissions) / 1e6),
            "carbon_intensity_mean": float(
                np.mean(mc_result.carbon_intensity)),
            "mean_inertia": float(np.mean(mc_result.avg_inertia)),
        }

        await update_simulation_status(
            simulation_id, "completed", summary=summary)
        logger.info("Simulation %d completed: avg_price=%.2f EUR/MWh",
                     simulation_id, summary["avg_price_mean"])

    except Exception as e:
        logger.error("Simulation %d failed: %s", simulation_id, e)
        await update_simulation_status(
            simulation_id, "failed", error_message=traceback.format_exc())

    finally:
        _progress.pop(simulation_id, None)


# ---------------------------------------------------------------------------
# Sweep runner (PART C)
# ---------------------------------------------------------------------------


def _run_sweep_sync(sim_config, sweep_row: dict[str, Any],
                    progress_cb) -> list[dict[str, Any]]:
    """Synchronous wrapper invoked on the dedicated sweep thread pool.

    Parses the grid from the stored JSON blobs and delegates to
    :func:`webapp.backend.sweeps.run_sweep`.

    Args:
        sim_config: Base scenario ``SimulationConfig``.
        sweep_row: Dict of the sweep row as stored in SQLite (values
            for ``values_a_json`` / ``values_b_json`` are JSON strings
            that this function parses).
        progress_cb: Synchronous progress callback forwarded to
            ``run_sweep`` — it is wrapped by the async caller to pump
            updates into SQLite.

    Returns:
        Ordered list of grid points (dicts) returned by
        :func:`run_sweep`.
    """
    values_a = json.loads(sweep_row["values_a_json"])
    values_b = (json.loads(sweep_row["values_b_json"])
                if sweep_row.get("values_b_json") else None)
    return run_sweep(
        sim_config,
        sweep_type=sweep_row["sweep_type"],
        parameter_a=sweep_row["parameter_a"],
        values_a=values_a,
        parameter_b=sweep_row.get("parameter_b"),
        values_b=values_b,
        n_runs_per_point=sweep_row["n_runs_per_point"],
        seed=42,
        progress_cb=progress_cb,
    )


async def run_sweep_task(sweep_id: int) -> None:
    """Background task: load the sweep row, execute the grid, persist.

    Uses a dedicated ``ThreadPoolExecutor`` so a long sweep does not
    block normal simulation launches. Progress is reported via
    ``update_sweep_progress`` after every grid point completes — the
    frontend poll endpoint reads the same counter.

    Args:
        sweep_id: Primary key of the sweep row to execute.
    """
    try:
        sweep_row = await get_sweep(sweep_id)
        if not sweep_row:
            raise ValueError(f"Sweep {sweep_id} not found")

        # Load the base scenario and convert it once. Config mutation
        # happens inside :mod:`webapp.backend.sweeps` per grid point.
        scenario_row = await get_scenario(sweep_row["scenario_id"])
        if not scenario_row:
            raise ValueError(
                f"Scenario {sweep_row['scenario_id']} not found")
        config_dict = json.loads(scenario_row["config_json"])
        scenario = ScenarioCreate(**config_dict)
        sim_config = scenario_to_sim_config(scenario)

        await update_sweep_status(sweep_id, "running")

        loop = asyncio.get_event_loop()

        # Adapter: the sweep engine is synchronous but we need to write
        # progress back to the async DB. Schedule a coroutine on the
        # event loop from the worker thread.
        def progress_cb(current: int, _total: int) -> None:
            asyncio.run_coroutine_threadsafe(
                update_sweep_progress(sweep_id, current), loop,
            )

        points = await loop.run_in_executor(
            _sweep_executor,
            _run_sweep_sync, sim_config, sweep_row, progress_cb,
        )

        results_payload = {
            "sweep_id": sweep_id,
            "sweep_type": sweep_row["sweep_type"],
            "parameter_a": sweep_row["parameter_a"],
            "values_a": json.loads(sweep_row["values_a_json"]),
            "parameter_b": sweep_row.get("parameter_b"),
            "values_b": (json.loads(sweep_row["values_b_json"])
                         if sweep_row.get("values_b_json") else None),
            "points": points,
        }
        await update_sweep_status(
            sweep_id, "completed",
            results_json=json.dumps(results_payload),
        )
        logger.info("Sweep %d completed: %d grid points",
                    sweep_id, len(points))

    except Exception as e:
        logger.error("Sweep %d failed: %s", sweep_id, e)
        await update_sweep_status(
            sweep_id, "failed", error_message=traceback.format_exc())
