/**
 * TypeScript types mirroring the FastAPI Pydantic models.
 * Keep in sync with webapp/backend/models.py.
 */

export interface FuelScenarioParams {
  mu: number;
  sigma: number;
  theta: number;
}

export interface GeneratorParams {
  capacity_gw: number;
  capex_per_kw: number;
  lifetime_years: number;
  vom_eur_mwh: number;
  fom_eur_kw_yr: number;
  efficiency: number;
  emission_factor: number;
  h_inertia: number;
  min_stable_pct: number;
  ramp_rate_pct_per_min: number;
  startup_cost_eur_mw: number;
  fuel_cost_eur_mwh_th?: number | null;
}

export interface ReliabilityParams {
  type: string;
  tech?: string | null;
  mttr_sigma_log?: number | null;
}

export interface InterconnectionParams {
  price_area: string;
  ntc_import_gw: number;
  ntc_export_gw: number;
  transport_cost_eur_mwh: number;
  seasonal_ntc_factor_monthly?: number[] | null;
  reliability: ReliabilityParams;
}

export interface PriceAreaParams {
  mu: number;
  sigma: number;
  theta: number;
  carbon_intensity_g_per_kwh: number;
}

export interface StorageParams {
  energy_capacity_gwh: number;
  power_capacity_gw: number;
  efficiency_roundtrip: number;
  soc_min_frac: number;
  soc_max_frac: number;
  initial_soc_frac: number;
  self_discharge_per_day: number;
  h_synthetic: number;
  inertia_soc_margin: number;
}

export interface ScenarioCreate {
  name: string;
  description: string;
  mix_config: Record<string, GeneratorParams>;
  gas_scenario: FuelScenarioParams;
  coal_scenario?: FuelScenarioParams | null;
  co2_scenario?: FuelScenarioParams | null;
  interconnections?: Record<string, InterconnectionParams> | null;
  price_areas?: Record<string, PriceAreaParams> | null;
  price_area_correlations?: Array<Array<string | number>> | null;
  price_areas_correlated: boolean;
  enable_ntc_faults: boolean;
  storage?: Record<string, StorageParams> | null;
  n_runs: number;
  seed: number;
  load_noise: number;
}

export interface ScenarioResponse {
  id: number;
  name: string;
  description: string;
  config: ScenarioCreate;
  created_at: string;
  updated_at: string;
}

export interface ScenarioListItem {
  id: number;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface SimulationSummary {
  id: number;
  scenario_id: number;
  scenario_name: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  n_runs: number;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  avg_price_mean?: number | null;
  avg_price_std?: number | null;
  total_emissions_mean_mt?: number | null;
  carbon_intensity_mean?: number | null;
  mean_inertia?: number | null;
}

export interface SimulationFullResult {
  simulation_id: number;
  avg_price: number[];
  monthly_prices: number[][];
  curtailment: number[];
  avg_inertia: number[];
  total_emissions: number[];
  carbon_intensity: number[];
  carbon_intensity_consumption: number[];
  emissions_by_tech: Record<string, number[]>;
  interconnection_names: string[];
  net_import_twh: number[][];
  import_gross_twh: number[][];
  export_gross_twh: number[][];
  foreign_price_mean: number[][];
  ntc_import_saturation_pct: number[][];
  import_hours: number[][];
  export_hours: number[][];
  import_energy_mwh: number[][];
  export_energy_mwh: number[][];
  total_economic_benefit_eur: number[][];
  total_co2_benefit_tons: number[][];
  economic_benefit_monthly_eur: number[][][];
  co2_benefit_monthly_tons: number[][][];
  storage_names: string[];
  storage_energy_cycled_mwh: number[][];
  storage_revenue_eur: number[][];
  storage_equivalent_cycles: number[][];
  storage_avg_soc: number[][];
  storage_monthly_avg_soc: number[][][];
}

export interface DefaultsResponse {
  italian_mix: Record<string, GeneratorParams>;
  gas_scenarios: Record<string, FuelScenarioParams>;
  coal_scenarios: Record<string, FuelScenarioParams>;
  co2_scenarios: Record<string, FuelScenarioParams>;
  interconnections: Record<string, InterconnectionParams>;
  price_areas: Record<string, PriceAreaParams>;
  price_area_correlations: Array<Array<string | number>>;
  storage_units: Record<string, StorageParams>;
}
