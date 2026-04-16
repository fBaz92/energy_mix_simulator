"""Scenario CRUD endpoints.

Provides REST API for creating, reading, updating, and deleting energy
mix scenarios. Each scenario stores a full ``ScenarioCreate`` config as
a JSON blob in SQLite. A defaults endpoint returns the ``energy_sim.config``
reference values to populate the frontend form.

Endpoints:
    GET    /api/scenarios          — list all scenarios (lightweight)
    GET    /api/scenarios/defaults — default config dicts for form population
    GET    /api/scenarios/{id}     — full scenario with config
    POST   /api/scenarios          — create new scenario
    PUT    /api/scenarios/{id}     — update scenario
    DELETE /api/scenarios/{id}     — delete scenario + cascaded simulations
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from energy_sim.config import (
    ITALIAN_MIX,
    GAS_SCENARIOS,
    COAL_SCENARIOS,
    CO2_SCENARIOS,
    INTERCONNECTIONS,
    PRICE_AREAS,
    PRICE_AREA_CORRELATIONS,
    STORAGE_UNITS,
)
from webapp.backend.db import (
    create_scenario,
    delete_scenario,
    get_scenario,
    list_scenarios,
    update_scenario,
)
from webapp.backend.models import (
    DefaultsResponse,
    ScenarioCreate,
    ScenarioListItem,
    ScenarioResponse,
)

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("/defaults", response_model=DefaultsResponse)
async def get_defaults() -> DefaultsResponse:
    """Return all default config dicts from ``energy_sim.config``.

    Used by the frontend to populate the scenario editor form with
    sensible starting values (Italian reference system). The price area
    correlations are serialized from ``{(a, b): corr}`` to
    ``[[a, b, corr], ...]`` for JSON compatibility.

    Returns:
        DefaultsResponse with italian_mix, gas/coal/co2 scenarios,
        interconnections, price_areas, correlations, and storage_units.
    """
    # Serialize tuple-keyed correlations as list of [area1, area2, corr]
    correlations_list = [
        [a, b, corr]
        for (a, b), corr in PRICE_AREA_CORRELATIONS.items()
    ]

    return DefaultsResponse(
        italian_mix=ITALIAN_MIX,
        gas_scenarios=GAS_SCENARIOS,
        coal_scenarios=COAL_SCENARIOS,
        co2_scenarios=CO2_SCENARIOS,
        interconnections=INTERCONNECTIONS,
        price_areas=PRICE_AREAS,
        price_area_correlations=correlations_list,
        storage_units=STORAGE_UNITS,
    )


@router.get("", response_model=list[ScenarioListItem])
async def list_all_scenarios() -> list[ScenarioListItem]:
    """List all saved scenarios (without full config).

    Returns:
        List of ScenarioListItem ordered by creation time (newest first).
    """
    rows = await list_scenarios()
    return [ScenarioListItem(**r) for r in rows]


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario_by_id(scenario_id: int) -> ScenarioResponse:
    """Fetch a single scenario with its full config.

    Args:
        scenario_id: Database primary key.

    Returns:
        ScenarioResponse with parsed config.

    Raises:
        HTTPException 404: If scenario not found.
    """
    row = await get_scenario(scenario_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scenario not found")
    config = json.loads(row["config_json"])
    return ScenarioResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        config=ScenarioCreate(**config),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.post("", response_model=ScenarioResponse, status_code=201)
async def create_new_scenario(body: ScenarioCreate) -> ScenarioResponse:
    """Create a new scenario from the provided config.

    Args:
        body: Full scenario configuration.

    Returns:
        ScenarioResponse with the new scenario's ID and timestamps.
    """
    config_dict = body.model_dump(mode="json")
    row = await create_scenario(body.name, body.description, config_dict)
    return ScenarioResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        config=body,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.put("/{scenario_id}", response_model=ScenarioResponse)
async def update_existing_scenario(scenario_id: int,
                                   body: ScenarioCreate) -> ScenarioResponse:
    """Update an existing scenario's configuration.

    Replaces the entire config — partial updates are not supported.

    Args:
        scenario_id: Database primary key.
        body: Full new scenario configuration.

    Returns:
        Updated ScenarioResponse.

    Raises:
        HTTPException 404: If scenario not found.
    """
    config_dict = body.model_dump(mode="json")
    row = await update_scenario(
        scenario_id, body.name, body.description, config_dict)
    if not row:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return ScenarioResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        config=body,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario_by_id(scenario_id: int) -> None:
    """Delete a scenario and all its associated simulations/results.

    Args:
        scenario_id: Database primary key.

    Raises:
        HTTPException 404: If scenario not found.
    """
    deleted = await delete_scenario(scenario_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scenario not found")
