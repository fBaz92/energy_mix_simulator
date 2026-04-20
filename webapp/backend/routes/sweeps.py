"""Parameter-sweep REST router.

Exposes five endpoints mirroring the simulation lifecycle:

- ``POST /api/sweeps`` — launch a new 1D or 2D sweep.
- ``GET /api/sweeps`` — list all sweeps (no results payload).
- ``GET /api/sweeps/{id}`` — poll status + progress.
- ``GET /api/sweeps/{id}/results`` — full ordered list of grid-point
  metrics (only available once the sweep completes).
- ``DELETE /api/sweeps/{id}`` — remove a sweep row.

The actual execution happens on a dedicated thread pool (see
:mod:`webapp.backend.tasks`) so a long sweep does not starve concurrent
simulation launches.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, HTTPException

from webapp.backend.db import (
    create_sweep,
    delete_sweep,
    get_scenario,
    get_sweep,
    list_sweeps,
)
from webapp.backend.models import (
    SweepCreate,
    SweepFullResult,
    SweepOut,
)
from webapp.backend.tasks import run_sweep_task

router = APIRouter(prefix="/api/sweeps", tags=["sweeps"])


def _row_to_out(row: dict) -> SweepOut:
    """Convert a DB row (with JSON blobs for values) into a ``SweepOut``.

    Parses ``values_a_json`` and ``values_b_json`` so the frontend
    receives native numeric lists. Joins ``scenario_name`` when
    present (list endpoint) but leaves it ``None`` on row lookups.
    """
    return SweepOut(
        id=row["id"],
        scenario_id=row["scenario_id"],
        scenario_name=row.get("scenario_name"),
        name=row["name"],
        sweep_type=row["sweep_type"],
        parameter_a=row["parameter_a"],
        values_a=json.loads(row["values_a_json"]),
        parameter_b=row.get("parameter_b"),
        values_b=(json.loads(row["values_b_json"])
                  if row.get("values_b_json") else None),
        n_runs_per_point=row["n_runs_per_point"],
        status=row["status"],
        progress_current=row["progress_current"],
        progress_total=row["progress_total"],
        error_message=row.get("error_message"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        created_at=row["created_at"],
    )


@router.post("", response_model=SweepOut, status_code=201)
async def launch_sweep(
    body: SweepCreate,
    background_tasks: BackgroundTasks,
) -> SweepOut:
    """Create a new sweep row and start the background runner.

    Validates that the scenario exists, the grid is non-empty, and for
    2D sweeps that ``parameter_b`` / ``values_b`` are supplied. The
    per-grid-point MC runs are bounded below (``n_runs_per_point >= 2``)
    to keep the dispersion estimate meaningful.

    Args:
        body: :class:`SweepCreate` request body.
        background_tasks: FastAPI helper used to schedule
            :func:`run_sweep_task` after the HTTP response returns.

    Raises:
        HTTPException 400: On invalid grid, unknown scenario, or mis-
            configured 2D inputs.
    """
    # Input validation keeps obviously broken requests out of the
    # background runner, where they would surface as status='failed'
    # minutes later — confusing for the frontend.
    if body.sweep_type not in ("1d", "2d"):
        raise HTTPException(status_code=400,
                            detail="sweep_type must be '1d' or '2d'")
    if not body.values_a:
        raise HTTPException(status_code=400,
                            detail="values_a must be non-empty")
    if body.sweep_type == "2d":
        if not body.parameter_b or not body.values_b:
            raise HTTPException(
                status_code=400,
                detail="2d sweep requires parameter_b and values_b")
    if body.n_runs_per_point < 2:
        raise HTTPException(
            status_code=400,
            detail="n_runs_per_point must be >= 2 (needed for std)")

    scenario = await get_scenario(body.scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=400,
            detail=f"scenario {body.scenario_id} does not exist")

    row = await create_sweep(
        scenario_id=body.scenario_id,
        name=body.name,
        sweep_type=body.sweep_type,
        parameter_a=body.parameter_a,
        values_a=body.values_a,
        parameter_b=body.parameter_b if body.sweep_type == "2d" else None,
        values_b=body.values_b if body.sweep_type == "2d" else None,
        n_runs_per_point=body.n_runs_per_point,
    )
    background_tasks.add_task(run_sweep_task, row["id"])
    return _row_to_out(row)


@router.get("", response_model=list[SweepOut])
async def list_all_sweeps() -> list[SweepOut]:
    """Return all sweeps (lightweight — no ``results_json`` payload)."""
    rows = await list_sweeps()
    return [_row_to_out(r) for r in rows]


@router.get("/{sweep_id}", response_model=SweepOut)
async def get_sweep_by_id(sweep_id: int) -> SweepOut:
    """Poll a single sweep's status + progress counters.

    Args:
        sweep_id: Primary key.

    Raises:
        HTTPException 404: If the sweep does not exist.
    """
    row = await get_sweep(sweep_id)
    if not row:
        raise HTTPException(status_code=404, detail="Sweep not found")
    return _row_to_out(row)


@router.get("/{sweep_id}/results", response_model=SweepFullResult)
async def get_sweep_results(sweep_id: int) -> SweepFullResult:
    """Return the full grid-point list of a completed sweep.

    Args:
        sweep_id: Primary key.

    Raises:
        HTTPException 404: If the sweep does not exist.
        HTTPException 409: If the sweep is not yet completed.
    """
    row = await get_sweep(sweep_id)
    if not row:
        raise HTTPException(status_code=404, detail="Sweep not found")
    if row["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Sweep status is '{row['status']}', not completed")
    payload = row.get("results_json")
    if not payload:
        raise HTTPException(
            status_code=404, detail="Results JSON missing for completed sweep")
    return SweepFullResult(**json.loads(payload))


@router.delete("/{sweep_id}", status_code=204)
async def delete_sweep_by_id(sweep_id: int) -> None:
    """Delete a sweep row.

    The background worker checks the row's existence on each iteration
    by re-reading it through :func:`get_sweep`; deletion mid-run results
    in the worker terminating at the next boundary rather than
    completing the grid — acceptable for a best-effort cancel path.

    Args:
        sweep_id: Primary key.

    Raises:
        HTTPException 404: If the sweep does not exist.
    """
    deleted = await delete_sweep(sweep_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Sweep not found")
