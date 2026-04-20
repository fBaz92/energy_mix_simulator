"""Serialization helpers for converting between energy_sim types and JSON.

Provides two-way conversion:
- ``mc_result_to_dict``: ``MonteCarloResult`` (numpy) -> nested Python lists
- ``scenario_to_sim_config``: ``ScenarioCreate`` (Pydantic) -> ``SimulationConfig``

These functions are the sole bridge between ``energy_sim`` (numpy-based) and
the webapp (JSON-based). All numpy ``.tolist()`` calls are centralized here.
"""

from __future__ import annotations

import numpy as np

from energy_sim.simulation import MonteCarloResult, SimulationConfig
from webapp.backend.models import ScenarioCreate


def _ndarray_to_list(arr: np.ndarray) -> list:
    """Convert a numpy array to a nested Python list.

    Handles empty arrays (shape contains 0) by returning an empty list.

    Args:
        arr: Numpy array of any dimensionality.

    Returns:
        Nested Python list, or empty list if the array has zero elements.
    """
    if arr.size == 0:
        return []
    return arr.tolist()


def mc_result_to_dict(result: MonteCarloResult) -> dict:
    """Convert a MonteCarloResult to a JSON-serializable dictionary.

    Every numpy array field is converted via ``.tolist()``. Dict fields
    (``emissions_by_tech``) have their values converted individually.
    List fields (``interconnection_names``, ``storage_names``) pass through.

    Args:
        result: The MonteCarloResult from ``run_monte_carlo()``.

    Returns:
        Dictionary with all fields as nested Python lists/dicts, ready
        for JSON serialization or storage in SQLite.
    """
    return {
        # Core
        "avg_price": _ndarray_to_list(result.avg_price),
        "monthly_prices": _ndarray_to_list(result.monthly_prices),
        "curtailment": _ndarray_to_list(result.curtailment),
        "avg_inertia": _ndarray_to_list(result.avg_inertia),
        # Emissions
        "total_emissions": _ndarray_to_list(result.total_emissions),
        "carbon_intensity": _ndarray_to_list(result.carbon_intensity),
        "carbon_intensity_consumption": _ndarray_to_list(
            result.carbon_intensity_consumption),
        "emissions_by_tech": {
            k: _ndarray_to_list(v)
            for k, v in result.emissions_by_tech.items()
        },
        # Interconnections
        "interconnection_names": list(result.interconnection_names),
        "net_import_twh": _ndarray_to_list(result.net_import_twh),
        "import_gross_twh": _ndarray_to_list(result.import_gross_twh),
        "export_gross_twh": _ndarray_to_list(result.export_gross_twh),
        "imported_emissions_tons": _ndarray_to_list(
            result.imported_emissions_tons),
        "foreign_price_mean": _ndarray_to_list(result.foreign_price_mean),
        "ntc_import_saturation_pct": _ndarray_to_list(
            result.ntc_import_saturation_pct),
        "import_hours": _ndarray_to_list(result.import_hours),
        "export_hours": _ndarray_to_list(result.export_hours),
        "import_energy_mwh": _ndarray_to_list(result.import_energy_mwh),
        "export_energy_mwh": _ndarray_to_list(result.export_energy_mwh),
        "total_economic_benefit_eur": _ndarray_to_list(
            result.total_economic_benefit_eur),
        "total_co2_benefit_tons": _ndarray_to_list(
            result.total_co2_benefit_tons),
        "economic_benefit_monthly_eur": _ndarray_to_list(
            result.economic_benefit_monthly_eur),
        "co2_benefit_monthly_tons": _ndarray_to_list(
            result.co2_benefit_monthly_tons),
        # Storage
        "storage_names": list(result.storage_names),
        "storage_energy_cycled_mwh": _ndarray_to_list(
            result.storage_energy_cycled_mwh),
        "storage_revenue_eur": _ndarray_to_list(result.storage_revenue_eur),
        "storage_equivalent_cycles": _ndarray_to_list(
            result.storage_equivalent_cycles),
        "storage_avg_soc": _ndarray_to_list(result.storage_avg_soc),
        "storage_monthly_avg_soc": _ndarray_to_list(
            result.storage_monthly_avg_soc),
        # Price-setter (per-tech dicts)
        "price_setter_hours_by_tech": {
            k: _ndarray_to_list(v)
            for k, v in result.price_setter_hours_by_tech.items()
        },
        "price_setter_pct_by_tech": {
            k: _ndarray_to_list(v)
            for k, v in result.price_setter_pct_by_tech.items()
        },
        "price_setter_by_month_hour": {
            k: _ndarray_to_list(v)
            for k, v in result.price_setter_by_month_hour.items()
        },
    }


def scenario_to_sim_config(scenario: ScenarioCreate) -> SimulationConfig:
    """Convert a ScenarioCreate Pydantic model to a SimulationConfig.

    Translates the JSON-friendly Pydantic schemas back into the raw dict
    format expected by ``energy_sim.simulation.SimulationConfig``.

    Handles:
    - GeneratorParams -> plain dicts
    - FuelScenarioParams -> plain dicts
    - InterconnectionParams -> plain dicts with nested reliability
    - PriceAreaParams -> plain dicts
    - price_area_correlations: list of [area1, area2, corr] -> dict of tuples
    - StorageParams -> plain dicts

    Args:
        scenario: The validated ScenarioCreate from the API request.

    Returns:
        A SimulationConfig ready to pass to ``run_monte_carlo()``.
    """
    # Mix config: GeneratorParams -> plain dicts
    mix_config = {
        tech: params.model_dump(exclude_none=True)
        for tech, params in scenario.mix_config.items()
    }

    # Fuel scenarios
    gas_scenario = scenario.gas_scenario.model_dump()
    coal_scenario = (scenario.coal_scenario.model_dump()
                     if scenario.coal_scenario else None)
    co2_scenario = (scenario.co2_scenario.model_dump()
                    if scenario.co2_scenario else None)

    # Interconnections
    interconnections_cfg = None
    if scenario.interconnections:
        interconnections_cfg = {
            name: params.model_dump()
            for name, params in scenario.interconnections.items()
        }
        # Convert reliability from Pydantic to plain dict (already done by
        # model_dump, but ensure nested ReliabilityParams is a dict)
        for name, cfg in interconnections_cfg.items():
            if isinstance(cfg.get("reliability"), dict):
                # Remove None values from reliability
                cfg["reliability"] = {
                    k: v for k, v in cfg["reliability"].items()
                    if v is not None
                }

    # Price areas
    price_areas_cfg = None
    if scenario.price_areas:
        price_areas_cfg = {
            name: params.model_dump()
            for name, params in scenario.price_areas.items()
        }

    # Price area correlations: [[area1, area2, corr], ...] -> {(a1, a2): corr}
    price_area_correlations = None
    if scenario.price_area_correlations:
        price_area_correlations = {
            (str(entry[0]), str(entry[1])): float(entry[2])
            for entry in scenario.price_area_correlations
        }

    # Storage
    storage_cfg = None
    if scenario.storage:
        storage_cfg = {
            name: params.model_dump()
            for name, params in scenario.storage.items()
        }

    return SimulationConfig(
        mix_config=mix_config,
        gas_scenario=gas_scenario,
        coal_scenario=coal_scenario,
        co2_scenario=co2_scenario,
        n_runs=scenario.n_runs,
        seed=scenario.seed,
        load_noise=scenario.load_noise,
        interconnections_cfg=interconnections_cfg,
        price_areas_cfg=price_areas_cfg,
        price_area_correlations=price_area_correlations,
        price_areas_correlated=scenario.price_areas_correlated,
        enable_ntc_faults=scenario.enable_ntc_faults,
        storage_cfg=storage_cfg,
    )
