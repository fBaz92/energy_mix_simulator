"""Simulation launch, polling, and result endpoints.

Handles the lifecycle of a Monte Carlo simulation:
1. Launch: create a DB row, start background task.
2. Poll: check status and progress (frontend polls every 500ms).
3. Fetch results: return the full MC result arrays for chart rendering.

Endpoints:
    POST   /api/simulations             — launch a new simulation
    GET    /api/simulations              — list all simulations
    GET    /api/simulations/{id}         — poll status + summary
    GET    /api/simulations/{id}/results — full result arrays
    DELETE /api/simulations/{id}         — delete simulation + results
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException

from webapp.backend.db import (
    create_simulation,
    delete_simulation,
    get_scenario,
    get_simulation,
    get_simulation_result,
    list_simulations,
)
from webapp.backend.models import (
    SimulationFullResult,
    SimulationLaunch,
    SimulationSummary,
)
from webapp.backend.tasks import get_progress, run_simulation_task

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


@router.post("", response_model=SimulationSummary, status_code=201)
async def launch_simulation(
    body: SimulationLaunch,
    background_tasks: BackgroundTasks,
) -> SimulationSummary:
    """Launch a Monte Carlo simulation for the given scenario.

    Creates a simulation row with status 'pending', then starts the
    background task. The frontend should poll ``GET /api/simulations/{id}``
    to track progress.

    Args:
        body: Request with scenario_id.
        background_tasks: FastAPI dependency for background execution.

    Returns:
        SimulationSummary with the new simulation ID and 'pending' status.

    Raises:
        HTTPException 404: If the scenario does not exist.
    """
    # Validate scenario exists
    scenario_row = await get_scenario(body.scenario_id)
    if not scenario_row:
        raise HTTPException(status_code=404, detail="Scenario not found")

    import json
    config = json.loads(scenario_row["config_json"])
    n_runs = config.get("n_runs", 30)

    # Create simulation row
    sim_row = await create_simulation(body.scenario_id, n_runs)

    # Launch background task
    # Note: BackgroundTasks runs after the response is sent. We use
    # asyncio.create_task instead so it starts immediately and we can
    # track progress during the response-poll cycle.
    asyncio.create_task(
        run_simulation_task(sim_row["id"], body.scenario_id))

    return SimulationSummary(
        id=sim_row["id"],
        scenario_id=body.scenario_id,
        scenario_name=scenario_row["name"],
        status="pending",
        progress=0.0,
        n_runs=n_runs,
        created_at=sim_row["created_at"],
    )


@router.get("", response_model=list[SimulationSummary])
async def list_all_simulations() -> list[SimulationSummary]:
    """List all simulations with their status and summary stats.

    Returns:
        List of SimulationSummary ordered by creation time (newest first).
    """
    rows = await list_simulations()
    return [
        SimulationSummary(
            id=r["id"],
            scenario_id=r["scenario_id"],
            scenario_name=r.get("scenario_name", ""),
            status=r["status"],
            progress=get_progress(r["id"]) if r["status"] == "running" else (
                1.0 if r["status"] == "completed" else 0.0),
            n_runs=r["n_runs"],
            error_message=r.get("error_message"),
            started_at=r.get("started_at"),
            completed_at=r.get("completed_at"),
            created_at=r["created_at"],
            avg_price_mean=r.get("avg_price_mean"),
            avg_price_std=r.get("avg_price_std"),
            total_emissions_mean_mt=r.get("total_emissions_mean_mt"),
            carbon_intensity_mean=r.get("carbon_intensity_mean"),
            mean_inertia=r.get("mean_inertia"),
        )
        for r in rows
    ]


@router.get("/{simulation_id}", response_model=SimulationSummary)
async def get_simulation_status(simulation_id: int) -> SimulationSummary:
    """Poll the status of a simulation.

    Returns current progress for running simulations, or summary stats
    for completed ones. The frontend should poll this every ~500ms while
    the simulation is running.

    Args:
        simulation_id: Database primary key.

    Returns:
        SimulationSummary with status, progress, and summary stats.

    Raises:
        HTTPException 404: If simulation not found.
    """
    row = await get_simulation(simulation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Simulation not found")

    # Get scenario name
    scenario_row = await get_scenario(row["scenario_id"])
    scenario_name = scenario_row["name"] if scenario_row else ""

    progress = 0.0
    if row["status"] == "running":
        progress = get_progress(simulation_id)
    elif row["status"] == "completed":
        progress = 1.0

    return SimulationSummary(
        id=row["id"],
        scenario_id=row["scenario_id"],
        scenario_name=scenario_name,
        status=row["status"],
        progress=progress,
        n_runs=row["n_runs"],
        error_message=row.get("error_message"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        created_at=row["created_at"],
        avg_price_mean=row.get("avg_price_mean"),
        avg_price_std=row.get("avg_price_std"),
        total_emissions_mean_mt=row.get("total_emissions_mean_mt"),
        carbon_intensity_mean=row.get("carbon_intensity_mean"),
        mean_inertia=row.get("mean_inertia"),
    )


@router.get("/{simulation_id}/results", response_model=SimulationFullResult)
async def get_results(simulation_id: int) -> SimulationFullResult:
    """Fetch the full MC result arrays for chart rendering.

    Only available for completed simulations. Returns all per-run arrays
    as nested Python lists (JSON-serializable).

    Args:
        simulation_id: Database primary key.

    Returns:
        SimulationFullResult with all arrays.

    Raises:
        HTTPException 404: If simulation not found.
        HTTPException 409: If simulation is not yet completed.
    """
    row = await get_simulation(simulation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Simulation not found")

    if row["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Simulation status is '{row['status']}', not 'completed'",
        )

    result_dict = await get_simulation_result(simulation_id)
    if not result_dict:
        raise HTTPException(
            status_code=404, detail="Result data not found")

    return SimulationFullResult(simulation_id=simulation_id, **result_dict)


@router.delete("/{simulation_id}", status_code=204)
async def delete_simulation_by_id(simulation_id: int) -> None:
    """Delete a simulation and its result data.

    Args:
        simulation_id: Database primary key.

    Raises:
        HTTPException 404: If simulation not found.
    """
    deleted = await delete_simulation(simulation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Simulation not found")
