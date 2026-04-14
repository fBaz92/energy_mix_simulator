# CLAUDE.md — Energy Mix Monte Carlo Simulator

## Project Overview

Monte Carlo simulator for analyzing the impact of different energy generation mixes on annualized electricity prices. Built around the Italian power system as reference case (60 GW peak), but designed to be technology-agnostic and extensible.

The core workflow: define a generation mix → run N Monte Carlo years (each 35040 quarter-hours) → dispatch via merit order with system constraints → aggregate price statistics → sweep scenarios and visualize sensitivity.

## Architecture

```
energy_sim/
├── config.py          # All parameters, defaults, scenarios, coefficients
├── models.py          # TimeGrid (temporal backbone), LoadProfile (multiplicative load model)
├── generators.py      # FuelPriceModel (O-U process), CarbonPriceModel, availability models
│                      #   (Solar/Wind/MustRun/Dispatchable), Generator class, build_generators()
├── dispatch.py        # Vectorized merit-order dispatch with inertia/reserve constraints
├── simulation.py      # run_monte_carlo, sweep_technology, build_sensitivity_heatmap,
│                      #   build_incremental_heatmap (Δ price finite-difference analysis)
├── visualization.py   # All plotting functions incl. plot_incremental_heatmap
│                      #   (side-effect only, no logic to test)
└── output/            # Generated PNGs

main.py                # Entry point: runs full pipeline (base case, sweeps, dispatch plots)

tests/
├── conftest.py        # Shared fixtures (TimeGrid, rng, make_generator, co2_model)
├── test_config.py     # Constants, _solar_envelope(), dict completeness, ITALIAN_MIX
├── test_models.py     # TimeGrid calendar metadata, LoadProfile shape/noise/weekday/holiday
├── test_generators.py # Price models, availability models, Generator, build_generators
├── test_dispatch.py   # Merit order, marginal pricing, load balance, inertia fix, curtailment
└── test_simulation.py # MC reproducibility, sweep results, heatmap shapes, incremental heatmap, price sanity

notebooks/
└── wind_solar_analysis.ipynb  # Visual analysis of wind/solar profiles and distributions
```

## Code Conventions

### Docstrings
Every module, class, function, and test method MUST have a detailed docstring. Follow these rules:
- **Modules**: describe what the module contains, what it validates (for tests), and its role in the project.
- **Classes**: describe the purpose, what is being tested (for test classes), and key attributes.
- **Functions/methods**: describe what the function does, its Args (with types and meaning), Returns, and any important side effects or preconditions.
- **Test methods**: describe exactly what property is being verified and what the expected behavior is. The docstring should explain *why* the test exists, not just restate the assertion.
- Use Google-style docstring format (Args/Returns/Raises sections).

### General
- All prices in EUR/MWh (electrical) unless noted as EUR/MWh_th (thermal)
- All powers in per-unit of P_BASE (60 GW) internally; GW in config and dispatch plots
- Time resolution: quarter-hour (0.25h). Index 0 = Jan 1 00:00, index 35039 = Dec 31 23:45
- Months are 1-indexed (1=January). Hours are 0-indexed (0=midnight).
- Random seeds: base seed + run index. Deterministic and reproducible.

## Key Design Decisions

- **Per-unit system**: all powers are normalized to P_BASE = 60 GW. Generator capacities are stored in GW but converted to p.u. internally. Graphs should show p.u. unless converting to GW for dispatch plots.
- **Merit order is the marginal price setter**: the SRMC of the last dispatched generator sets the system marginal price at each timestep. This is the standard European day-ahead market model.
- **Inertia constraint (H_MIN = 3.5s)**: if the weighted average inertia of online synchronous generators drops below threshold, the cheapest offline synchronous generator is forced online at minimum stable generation. Renewables are curtailed if this causes oversupply.
- **Fuel price via Ornstein-Uhlenbeck**: mean-reverting stochastic process. Each MC run generates a fresh gas price path. Uranium and CO2 are currently constant but use the same interface.
- **Wind model**: AR(1) process in Gaussian space → Weibull transform → turbine power curve. This preserves temporal autocorrelation (weather fronts last days, not hours). NOT a simple coefficient model like solar.
- **Solar model**: deterministic envelope (month × hour Gaussian) × Markov chain cloud state (per-day, two-state). Night hours are hard-zeroed.
- **Hydro**: must-run band at fixed capacity. Interface ready for future reservoir/energy-budget model. Do NOT try to make it dispatchable without implementing state tracking.

## How to Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install numpy scipy matplotlib
python main.py
```

Output goes to `output/`. Runtime ~2 minutes for the full sweep (100 MC runs base + sensitivity sweeps at 20-30 runs each).

### Running Tests

```bash
pip install pytest
python -m pytest tests/ -v              # all tests (~2s)
python -m pytest tests/ -v -m "not slow" # skip slow MC sweeps
```

134 tests covering config, models, generators, dispatch, and simulation. Tests marked `@pytest.mark.slow` involve multiple MC sweep runs.

## Performance Notes

- Single dispatch (35040 timesteps, ~5 generators): ~30ms (vectorized numpy)
- The inertia-fix loop is NOT vectorized (iterates over violation timesteps only). With the Italian mix this affects 0-5% of timesteps. If it becomes a bottleneck with high-renewable scenarios, consider batch-processing violations.
- Wind availability `generate_profile()` uses a Python loop for AR(1). For very large MC runs, consider rewriting with `scipy.signal.lfilter`.
- 100 MC runs × full dispatch ≈ 7 seconds. Sweeps multiply this by number of scenario points.

## Known Limitations

- No transmission constraints (copper-plate assumption — single bus)
- No unit commitment (min up/down times, startup sequencing)
- No ramp-rate enforcement between timesteps (only min stable generation)
- Hydro is a flat must-run band, not dispatchable
- No demand response or elastic demand
- No import/export with neighboring countries (partially captured by hydro band)
- Solar envelope is symmetric around 13:00; real irradiance is slightly asymmetric
- Wind spatial correlation not modeled (all wind farms see same wind process)

## Roadmap

Items are ordered so that each builds on the previous ones. Implement in sequence.

**IMPORTANT**: Every time a roadmap item is implemented, this roadmap must be updated to reflect the new status (change "not started" to "implemented").

### 1. CO₂ Emissions Tracking
**Status**: implemented
**Priority**: high — low effort, high analytical value
**Depends on**: nothing (pure post-processing on existing dispatch output)

Add per-timestep and per-generator CO₂ emission accounting. All data needed is already available: `Generator.emission_factor` (tCO₂/MWh_th), `Generator.efficiency`, and `DispatchResult.power` (p.u.).

Implementation:
- In `dispatch_year()` or as post-processing: compute `emissions[i, t] = power_pu[i, t] * P_BASE * 0.25 * emission_factor[i] / efficiency[i]` (tons CO₂ per quarter-hour).
- Add `emissions` array (shape `(n_gen, 35040)`) to `DispatchResult`.
- In `run_monte_carlo()`: aggregate total annual emissions (tons), average carbon intensity (gCO₂/kWh), and per-technology breakdown across MC runs.
- New visualization: carbon intensity vs technology penetration curves; emission breakdown stacked bar.

### 2. Coal Generator Type
**Status**: implemented
**Priority**: high — completes the fossil fuel picture
**Depends on**: item 1 (coal's high emission factor makes CO₂ tracking essential to evaluate it)

Add coal as a dispatchable thermal generator. Typical parameters for a hard-coal plant:
- Efficiency: 38–42%
- Emission factor: ~0.34 tCO₂/MWh_th (significantly higher than gas at 0.20)
- Inertia H: ~5.0s
- Min stable generation: ~45%
- Ramp rate: ~0.02%/min (slower than gas)
- Fuel cost: 10–15 EUR/MWh_th (cheaper than gas, but higher CO₂ cost offsets this)

Implementation:
- Add `coal` entry in `ITALIAN_MIX` (or custom mix dicts) with all standard generator parameters.
- Fuel price model: either `ConstantFuelPrice` for fixed coal price, or a dedicated `FuelPriceModel` O-U process with coal-specific parameters (lower volatility than gas, e.g. μ=12, σ=3, θ=0.05).
- In `build_generators()`: route `coal` to the appropriate fuel model and `DispatchableAvailability()`.
- No dispatch engine changes needed — coal enters the merit order naturally.
- Define coal price scenarios analogous to gas scenarios in `config.py` (e.g. `COAL_SCENARIOS = {'base': {'mu': 12, 'sigma': 3, 'theta': 0.05}, 'crisis': {'mu': 25, 'sigma': 8, 'theta': 0.05}}`).

Note: with high CO₂ prices (>60 EUR/ton), coal SRMC can exceed gas SRMC ("fuel switching"), making merit-order position price-dependent. This is realistic and the model handles it correctly since SRMC is recomputed at each timestep.

### 3. Stochastic CO₂ Price
**Status**: implemented
**Priority**: medium — low effort, enables richer scenario analysis
**Depends on**: items 1–2 (CO₂ tracking and coal must be in place for the stochastic CO₂ price to produce meaningful fuel-switching dynamics)

`CarbonPriceModel` already has the same interface as `FuelPriceModel`. Replace the `generate_path()` implementation with an O-U process. Suggested parameters: μ=65, σ=10, θ=0.05 (slower mean-reversion than gas). This interacts with coal vs gas merit-order positioning: a volatile CO₂ price creates timesteps where coal is cheaper than gas and vice versa, producing realistic fuel-switching behavior.

### 4. Fuel Price Sensitivity Analysis
**Status**: implemented
**Priority**: high — critical for energy security assessment
**Depends on**: items 1–3 (needs coal in the mix and CO₂ tracking to show fuel-switching and emission impacts)

Add systematic sensitivity analysis of electricity price to fuel price variations, at fixed energy mix. This answers the question: "given this mix, how exposed am I to fuel price shocks?"

Implementation:
- New function `sweep_fuel_price(base_mix, fuel_type, mu_range, n_runs, seed)` in `simulation.py`. For each μ value in `mu_range`, run a full MC with the corresponding fuel price parameters, keeping the mix fixed.
- For multi-fuel analysis: `sweep_fuel_prices_2d(base_mix, fuel_configs, n_runs, seed)` where `fuel_configs` is a dict like `{'gas': np.linspace(20, 100, 10), 'coal': np.linspace(8, 30, 6)}`. Produces a 2D heatmap of electricity price vs (gas_price, coal_price).
- New visualizations:
  - 1D curve: electricity price ± σ vs fuel μ for a single fuel.
  - 2D heatmap: electricity price vs (gas μ, coal μ) — shows fuel-switching dynamics.
  - Sensitivity coefficient: ∂(electricity_price)/∂(fuel_price) at each operating point — measures exposure.
- Pair with CO₂ tracking (item 1) to show how emission intensity changes with fuel price (high gas price → more coal dispatch → higher emissions).

### 5. Load Profile Enhancements
**Status**: implemented
**Priority**: medium — infrastructure already exists, just needs activation
**Depends on**: nothing (independent, but best done before interconnections which add load complexity)

`LoadProfile` already supports `set_weekday_factors()`, `set_holiday_factor()`, and `noise_sigma` in `generate()`. The `TimeGrid` has `day_of_week` and `is_holiday` attributes ready. Implementation:
- Define default weekday factors in `config.py` (e.g. Saturday 0.85, Sunday 0.75, weekdays 1.0).
- Define an Italian holiday calendar (day-of-year list) in `config.py`.
- Activate both in `run_monte_carlo()` before generating the load profile.
- Increase default `noise_sigma` from 0.02 to 0.03–0.05 for more realistic intra-day variability.

### 6. Import/Export Model (Interconnections)
**Status**: implemented
**Priority**: medium — significant modeling addition, requires careful design
**Depends on**: items 1–4 (the full domestic model — emissions, coal, fuel sensitivity — should be stable before adding cross-border flows)

Model cross-border electricity exchanges using a pragmatic approach: imports as virtual generators in the merit order, exports as price-dependent additional load.

Design:
- New class `Interconnection` with attributes: `name` (str, e.g. "IT-FR"), `ntc_import_gw` (float, Net Transfer Capacity for import), `ntc_export_gw` (float, NTC for export), `foreign_price_model` (a `FuelPriceModel` or `ConstantFuelPrice` instance representing the neighboring market's marginal price), `transport_cost_eur_mwh` (float, transmission losses + wheeling fee).
- **Import**: modeled as a virtual generator with `srmc = foreign_price + transport_cost` and `capacity = ntc_import_gw`. Enters the merit order alongside domestic generators. When it's cheaper than domestic alternatives, the system imports.
- **Export**: after the merit-order dispatch, if the domestic marginal price < foreign_price - transport_cost, excess generation is "sold" up to `ntc_export_gw`. This is equivalent to adding `min(surplus, ntc_export_gw)` to the load and re-dispatching (or, more efficiently, just accounting for the additional load in a post-dispatch adjustment).
- Configuration: add `INTERCONNECTIONS` dict in `config.py`, e.g.:
  ```python
  INTERCONNECTIONS = {
      'IT-FR': {'ntc_import_gw': 3.0, 'ntc_export_gw': 2.5, 'foreign_price_mu': 50, 'foreign_price_sigma': 12, 'transport_cost': 3.0},
      'IT-CH': {'ntc_import_gw': 4.0, 'ntc_export_gw': 1.5, 'foreign_price_mu': 45, 'foreign_price_sigma': 8, 'transport_cost': 2.0},
      'IT-AT': {'ntc_import_gw': 1.0, 'ntc_export_gw': 0.5, 'foreign_price_mu': 55, 'foreign_price_sigma': 10, 'transport_cost': 4.0},
  }
  ```
- In `dispatch_year()`: build import virtual generators from interconnections before Phase 1 merit order. After Phase 1, check for export opportunities and adjust load/dispatch accordingly.
- Track net import/export per timestep in `DispatchResult` (new field `net_import`, shape `(n_interconnections, 35040)`).
- New visualizations: net flow per interconnection over time; import/export duration curves; price convergence analysis.

Explicit non-goals (for now): loop flows, market coupling (simultaneous clearing), DC load flow, transmission losses as a function of flow, and multi-zone sequential clearing.

### 7. Battery Storage
**Status**: not started
**Priority**: medium — most impactful missing flexibility resource
**Depends on**: items 1–6 (storage value depends on price spreads shaped by the full generation mix and interconnections)

Add utility-scale battery storage with inter-temporal state (SOC). Simpler than hydro reservoirs (no inflows, no evaporation).

Implementation:
- Create `StorageUnit` class with `capacity_mwh`, `power_mw`, `efficiency_roundtrip`, `soc` state.
- In `dispatch_year()`, after merit-order dispatch: if marginal price < charge_threshold → charge; if marginal price > discharge_threshold → discharge. Thresholds can be rolling percentiles of recent prices (e.g. 25th and 75th).
- This breaks pure vectorization — the SOC loop must be sequential. But it's only one unit, so the loop is O(35040), not O(n_gen × 35040).
- Track SOC timeseries, charge/discharge power, and revenue in `DispatchResult`.
- New visualization: SOC profile over time; storage revenue vs capacity sizing curves.

### 8. Web Application
**Status**: not started
**Priority**: low — large standalone project, implement after core model features are stable
**Depends on**: all previous items (the web app exposes the full model, so the model should be feature-complete first)

Interactive web interface for scenario definition, simulation execution, and result visualization.

Architecture:
- **Backend**: Python (FastAPI or Flask). Exposes `energy_sim/` as a library. Endpoints: CRUD for scenarios, trigger simulation runs (async, background worker), fetch results and plots.
- **Database**: SQLite for single-user (upgrade to PostgreSQL for multi-user). Schema:
  - `scenarios` table: id, name, mix_config (JSON), fuel_params (JSON), interconnections (JSON), p_peak_gw, n_mc_runs, created_at.
  - `runs` table: id, scenario_id, status (pending/running/done/failed), started_at, finished_at, results (JSON with avg_price, monthly_prices, curtailment, inertia, emissions).
  - `interconnections` table: id, scenario_id, name, ntc_import, ntc_export, foreign_price_params (JSON), transport_cost.
- **Frontend**: Streamlit for MVP (fast to build, pure Python, good enough for internal/research use). Migrate to React + Plotly.js for production if needed.
- **Key views**:
  - Scenario editor: define mix (sliders for each technology's capacity), fuel price parameters (μ, σ, θ per fuel), system parameters (P_peak, H_min), interconnections.
  - Simulation launcher: select scenario, set n_runs, launch (progress bar).
  - Results dashboard: price distribution histograms, monthly price heatmaps, dispatch stack charts for selected days, CO₂ emission breakdowns, sensitivity curves.
  - Scenario comparison: side-by-side price/emissions/curtailment for 2+ scenarios.
- **Important**: the `energy_sim/` package must remain a standalone library with no web dependencies. The web app imports and calls it, never the other way around.
- Replace matplotlib with Plotly for all web-facing visualizations (interactive zoom, hover tooltips, responsive layout). Keep matplotlib as fallback for CLI/batch mode.
