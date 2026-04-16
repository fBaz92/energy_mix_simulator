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
import logging
import traceback
from typing import Any

import numpy as np

from energy_sim.simulation import run_monte_carlo

from webapp.backend.db import (
    get_scenario,
    store_simulation_result,
    update_simulation_status,
)
from webapp.backend.models import ScenarioCreate
from webapp.backend.serializers import mc_result_to_dict, scenario_to_sim_config

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

    Designed to be called inside ``loop.run_in_executor()``.

    Args:
        sim_config: A ``SimulationConfig`` instance.
        simulation_id: Used to update the progress dict.

    Returns:
        The ``MonteCarloResult`` from ``run_monte_carlo()``.
    """
    def progress_cb(fraction: float) -> None:
        _progress[simulation_id] = fraction

    result = run_monte_carlo(sim_config, progress_callback=progress_cb)
    return result


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
        mc_result = await loop.run_in_executor(
            None, _run_mc_sync, sim_config, simulation_id
        )

        # Serialize and store
        result_dict = mc_result_to_dict(mc_result)
        await store_simulation_result(simulation_id, result_dict)

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
