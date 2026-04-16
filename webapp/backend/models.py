"""Pydantic schemas for the webapp REST API.

Provides JSON-serializable request/response models that mirror the
``energy_sim`` dataclasses (``SimulationConfig``, ``MonteCarloResult``)
but use plain Python types instead of numpy arrays.

Model hierarchy:
- Input: ``FuelScenarioParams``, ``GeneratorParams``, ``InterconnectionParams``,
  ``PriceAreaParams``, ``StorageParams`` -> ``ScenarioCreate`` -> ``ScenarioResponse``
- Output: ``SimulationSummary`` (lightweight), ``SimulationFullResult`` (heavy)
- Defaults: ``DefaultsResponse`` (all config dicts from ``energy_sim.config``)
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models (building blocks)
# ---------------------------------------------------------------------------

class FuelScenarioParams(BaseModel):
    """Ornstein-Uhlenbeck fuel/carbon price parameters.

    Used for gas, coal, and CO2 price scenarios. The O-U process
    mean-reverts around ``mu`` with volatility ``sigma`` and speed ``theta``.

    Attributes:
        mu: Long-run mean price (EUR/MWh_th for fuel, EUR/ton for CO2).
        sigma: Volatility of the stochastic process.
        theta: Mean-reversion speed (higher = faster reversion).
    """

    mu: float
    sigma: float
    theta: float


class GeneratorParams(BaseModel):
    """Parameters for a single generator technology in the mix.

    Maps directly to the per-technology dicts in ``ITALIAN_MIX``.

    Attributes:
        capacity_gw: Installed capacity in GW.
        capex_per_kw: Capital expenditure (EUR/kW).
        lifetime_years: Economic lifetime (years).
        vom_eur_mwh: Variable O&M cost (EUR/MWh).
        fom_eur_kw_yr: Fixed O&M cost (EUR/kW/year).
        efficiency: Thermal-to-electric efficiency (1.0 for renewables).
        emission_factor: CO2 emission factor (tCO2/MWh_th).
        h_inertia: Inertia constant H (seconds, 0 for non-synchronous).
        min_stable_pct: Minimum stable generation (fraction of capacity).
        ramp_rate_pct_per_min: Ramp rate (fraction of capacity per minute).
        startup_cost_eur_mw: Start-up cost (EUR/MW).
        fuel_cost_eur_mwh_th: Fixed fuel cost for nuclear (EUR/MWh_th).
            None for generators whose fuel cost comes from the O-U model.
    """

    capacity_gw: float
    capex_per_kw: float
    lifetime_years: float
    vom_eur_mwh: float
    fom_eur_kw_yr: float
    efficiency: float
    emission_factor: float
    h_inertia: float
    min_stable_pct: float
    ramp_rate_pct_per_min: float
    startup_cost_eur_mw: float
    fuel_cost_eur_mwh_th: float | None = None


class ReliabilityParams(BaseModel):
    """Reliability model specification for an interconnection.

    Routed through ``energy_sim.reliability.build_reliability_model``.

    Attributes:
        type: Model type ('perfect', 'explicit', 'availability', 'technology').
        tech: Technology key (e.g. 'hvdc_back_to_back', 'overhead_ac',
            'submarine_cable_hvdc').
        mttr_sigma_log: Log-normal MTTR sigma for submarine cables (optional).
    """

    type: str
    tech: str | None = None
    mttr_sigma_log: float | None = None


class InterconnectionParams(BaseModel):
    """Parameters for a single cross-border interconnection link.

    Maps directly to entries in the ``INTERCONNECTIONS`` config dict.

    Attributes:
        price_area: Foreign price area name (key in ``PRICE_AREAS``).
        ntc_import_gw: Net Transfer Capacity for import (GW).
        ntc_export_gw: Net Transfer Capacity for export (GW).
        transport_cost_eur_mwh: Wheeling fee + losses (EUR/MWh).
        seasonal_ntc_factor_monthly: Optional 12-element monthly NTC multipliers.
        reliability: Reliability model specification.
    """

    price_area: str
    ntc_import_gw: float
    ntc_export_gw: float
    transport_cost_eur_mwh: float
    seasonal_ntc_factor_monthly: list[float] | None = None
    reliability: ReliabilityParams


class PriceAreaParams(BaseModel):
    """Parameters for a foreign electricity price area.

    Maps to entries in ``PRICE_AREAS``. The O-U process models the
    neighbouring market's day-ahead price.

    Attributes:
        mu: Long-run mean day-ahead price (EUR/MWh).
        sigma: Volatility.
        theta: Mean-reversion speed.
        carbon_intensity_g_per_kwh: Avg emission intensity (gCO2/kWh).
    """

    mu: float
    sigma: float
    theta: float
    carbon_intensity_g_per_kwh: float


class StorageParams(BaseModel):
    """Parameters for a battery storage unit.

    Maps to entries in ``STORAGE_UNITS``.

    Attributes:
        energy_capacity_gwh: Nameplate energy capacity (GWh AC).
        power_capacity_gw: Nameplate charge/discharge power (GW AC).
        efficiency_roundtrip: AC-AC round-trip efficiency.
        soc_min_frac: Minimum operational SOC (fraction).
        soc_max_frac: Maximum operational SOC (fraction).
        initial_soc_frac: Starting SOC at t=0 (fraction).
        self_discharge_per_day: Idle energy loss per 24h (fraction).
        h_synthetic: Emulated inertia constant (seconds).
        inertia_soc_margin: SOC headroom for inertia support (fraction).
    """

    energy_capacity_gwh: float = 4.0
    power_capacity_gw: float = 2.0
    efficiency_roundtrip: float = 0.88
    soc_min_frac: float = 0.10
    soc_max_frac: float = 0.90
    initial_soc_frac: float = 0.50
    self_discharge_per_day: float = 0.001
    h_synthetic: float = 4.0
    inertia_soc_margin: float = 0.02


# ---------------------------------------------------------------------------
# Scenario models
# ---------------------------------------------------------------------------

class ScenarioCreate(BaseModel):
    """Request body for creating or updating a scenario.

    Contains all parameters needed to configure a Monte Carlo simulation.
    Default values match the Italian reference system from ``energy_sim.config``.

    Attributes:
        name: Human-readable scenario name.
        description: Optional description.
        mix_config: Generation mix (tech_name -> GeneratorParams).
        gas_scenario: Gas price O-U parameters.
        coal_scenario: Coal price O-U parameters (None -> base defaults).
        co2_scenario: CO2 price O-U parameters (None -> base defaults).
        interconnections: Cross-border links (link_name -> params). None disables.
        price_areas: Foreign price areas (area_name -> params).
        price_area_correlations: Pairwise correlations as list of [area1, area2, corr].
        price_areas_correlated: Enable Cholesky correlation coupling.
        enable_ntc_faults: Enable stochastic NTC faults.
        storage: Battery storage units (unit_name -> params). None disables.
        n_runs: Number of Monte Carlo years.
        seed: Base random seed.
        load_noise: Std dev of multiplicative load noise.
    """

    name: str
    description: str = ""
    mix_config: dict[str, GeneratorParams]
    gas_scenario: FuelScenarioParams
    coal_scenario: FuelScenarioParams | None = None
    co2_scenario: FuelScenarioParams | None = None
    interconnections: dict[str, InterconnectionParams] | None = None
    price_areas: dict[str, PriceAreaParams] | None = None
    price_area_correlations: list[list[str | float]] | None = None
    price_areas_correlated: bool = True
    enable_ntc_faults: bool = True
    storage: dict[str, StorageParams] | None = None
    n_runs: int = 30
    seed: int = 42
    load_noise: float = 0.04


class ScenarioResponse(BaseModel):
    """Response model for a saved scenario.

    Extends ``ScenarioCreate`` fields with database metadata.

    Attributes:
        id: Database primary key.
        name: Scenario name.
        description: Scenario description.
        config: Full scenario configuration (ScenarioCreate body).
        created_at: ISO timestamp of creation.
        updated_at: ISO timestamp of last update.
    """

    id: int
    name: str
    description: str
    config: ScenarioCreate
    created_at: str
    updated_at: str


class ScenarioListItem(BaseModel):
    """Lightweight scenario entry for list views.

    Omits the full config JSON to keep the list endpoint fast.

    Attributes:
        id: Database primary key.
        name: Scenario name.
        description: Scenario description.
        created_at: ISO timestamp.
        updated_at: ISO timestamp.
    """

    id: int
    name: str
    description: str
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Simulation models
# ---------------------------------------------------------------------------

class SimulationLaunch(BaseModel):
    """Request body for launching a simulation.

    Attributes:
        scenario_id: ID of the scenario to simulate.
    """

    scenario_id: int


class SimulationSummary(BaseModel):
    """Lightweight simulation status and summary stats.

    Returned by the poll endpoint. Summary stats are populated only
    after the simulation completes.

    Attributes:
        id: Simulation database ID.
        scenario_id: Associated scenario ID.
        scenario_name: Scenario name (for display).
        status: Current status ('pending', 'running', 'completed', 'failed').
        progress: Completion fraction (0.0 to 1.0).
        n_runs: Number of Monte Carlo runs.
        error_message: Error details if status is 'failed'.
        started_at: ISO timestamp when simulation started.
        completed_at: ISO timestamp when simulation finished.
        created_at: ISO timestamp of creation.
        avg_price_mean: Mean electricity price across runs (EUR/MWh).
        avg_price_std: Std dev of electricity price (EUR/MWh).
        total_emissions_mean_mt: Mean annual CO2 (Mt).
        carbon_intensity_mean: Mean carbon intensity (gCO2/kWh).
        mean_inertia: Mean system inertia (seconds).
    """

    id: int
    scenario_id: int
    scenario_name: str = ""
    status: str
    progress: float = 0.0
    n_runs: int = 0
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str = ""
    avg_price_mean: float | None = None
    avg_price_std: float | None = None
    total_emissions_mean_mt: float | None = None
    carbon_intensity_mean: float | None = None
    mean_inertia: float | None = None


class SimulationFullResult(BaseModel):
    """Full simulation results with all per-run arrays.

    Fetched on demand for chart rendering. All numpy arrays from
    ``MonteCarloResult`` are serialized as nested Python lists.

    Attributes:
        simulation_id: Associated simulation ID.
        avg_price: Per-run annual prices, shape (n_runs,).
        monthly_prices: Per-run monthly prices, shape (n_runs, 12).
        curtailment: Per-run curtailment, shape (n_runs,).
        avg_inertia: Per-run inertia, shape (n_runs,).
        total_emissions: Per-run emissions in tons, shape (n_runs,).
        carbon_intensity: Per-run territorial CI, shape (n_runs,).
        carbon_intensity_consumption: Per-run consumption CI, shape (n_runs,).
        emissions_by_tech: Per-tech emissions {tech: [per_run_tons]}.
        interconnection_names: Ordered link names.
        net_import_twh: Shape (n_runs, n_links).
        import_gross_twh: Shape (n_runs, n_links).
        export_gross_twh: Shape (n_runs, n_links).
        foreign_price_mean: Shape (n_runs, n_links).
        ntc_import_saturation_pct: Shape (n_runs, n_links).
        import_hours: Shape (n_runs, n_links).
        export_hours: Shape (n_runs, n_links).
        total_economic_benefit_eur: Shape (n_runs, n_links).
        total_co2_benefit_tons: Shape (n_runs, n_links).
        economic_benefit_monthly_eur: Shape (n_runs, n_links, 12).
        co2_benefit_monthly_tons: Shape (n_runs, n_links, 12).
        storage_names: Ordered storage unit names.
        storage_energy_cycled_mwh: Shape (n_runs, n_storage).
        storage_revenue_eur: Shape (n_runs, n_storage).
        storage_equivalent_cycles: Shape (n_runs, n_storage).
        storage_avg_soc: Shape (n_runs, n_storage).
        storage_monthly_avg_soc: Shape (n_runs, n_storage, 12).
    """

    simulation_id: int

    # Core
    avg_price: list[float]
    monthly_prices: list[list[float]]
    curtailment: list[float]
    avg_inertia: list[float]

    # Emissions
    total_emissions: list[float]
    carbon_intensity: list[float]
    carbon_intensity_consumption: list[float]
    emissions_by_tech: dict[str, list[float]]

    # Interconnections
    interconnection_names: list[str] = Field(default_factory=list)
    net_import_twh: list[list[float]] = Field(default_factory=list)
    import_gross_twh: list[list[float]] = Field(default_factory=list)
    export_gross_twh: list[list[float]] = Field(default_factory=list)
    foreign_price_mean: list[list[float]] = Field(default_factory=list)
    ntc_import_saturation_pct: list[list[float]] = Field(default_factory=list)
    import_hours: list[list[float]] = Field(default_factory=list)
    export_hours: list[list[float]] = Field(default_factory=list)
    import_energy_mwh: list[list[float]] = Field(default_factory=list)
    export_energy_mwh: list[list[float]] = Field(default_factory=list)
    total_economic_benefit_eur: list[list[float]] = Field(default_factory=list)
    total_co2_benefit_tons: list[list[float]] = Field(default_factory=list)
    economic_benefit_monthly_eur: list[list[list[float]]] = Field(
        default_factory=list)
    co2_benefit_monthly_tons: list[list[list[float]]] = Field(
        default_factory=list)

    # Storage
    storage_names: list[str] = Field(default_factory=list)
    storage_energy_cycled_mwh: list[list[float]] = Field(default_factory=list)
    storage_revenue_eur: list[list[float]] = Field(default_factory=list)
    storage_equivalent_cycles: list[list[float]] = Field(default_factory=list)
    storage_avg_soc: list[list[float]] = Field(default_factory=list)
    storage_monthly_avg_soc: list[list[list[float]]] = Field(
        default_factory=list)


# ---------------------------------------------------------------------------
# Defaults response
# ---------------------------------------------------------------------------

class DefaultsResponse(BaseModel):
    """All default config dicts from ``energy_sim.config``.

    Returned by ``GET /api/scenarios/defaults`` to populate the
    scenario editor form with sensible starting values.

    Attributes:
        italian_mix: Default generation mix (ITALIAN_MIX).
        gas_scenarios: Gas price scenarios (GAS_SCENARIOS).
        coal_scenarios: Coal price scenarios (COAL_SCENARIOS).
        co2_scenarios: CO2 price scenarios (CO2_SCENARIOS).
        interconnections: Default interconnection topology (INTERCONNECTIONS).
        price_areas: Foreign price areas (PRICE_AREAS).
        price_area_correlations: Pairwise correlations (serialized as list).
        storage_units: Default storage config (STORAGE_UNITS).
    """

    italian_mix: dict
    gas_scenarios: dict
    coal_scenarios: dict
    co2_scenarios: dict
    interconnections: dict
    price_areas: dict
    price_area_correlations: list[list[str | float]]
    storage_units: dict
