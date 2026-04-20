# CLAUDE.md — Energy Mix Monte Carlo Simulator

## Project Overview

Monte Carlo simulator for analyzing the impact of different energy generation mixes on annualized electricity prices. Built around the Italian power system as reference case (60 GW peak), but designed to be technology-agnostic and extensible.

The core workflow: define a generation mix → run N Monte Carlo years (each 35040 quarter-hours) → dispatch via merit order with system constraints → aggregate price statistics → sweep scenarios and visualize sensitivity.

## Architecture

```
energy_sim/                # Core simulation library (no web/UI dependencies)
├── config.py              # Parameters, defaults, scenarios, coefficients, Italian mix
├── models.py              # TimeGrid (temporal backbone), LoadProfile (multiplicative load)
├── generators.py          # FuelPriceModel/CarbonPriceModel (O-U), availability models
│                          #   (Solar/Wind/MustRun/Dispatchable), Generator, build_generators()
├── dispatch.py            # Vectorized merit-order dispatch with inertia/reserve constraints
├── simulation.py          # run_monte_carlo, sweep_technology, build_sensitivity_heatmap,
│                          #   build_incremental_heatmap, fuel-price sweeps
├── storage.py             # StorageUnit with SOC, build_storage_units factory
├── interconnections.py    # Interconnection class: import as virtual gen, export as extra load
├── price_areas.py         # Multi-zone price-area handling
├── reliability.py         # Reliability/adequacy metrics
└── visualization.py       # Matplotlib plotting (side-effect only, no logic to test)

main.py                    # Entry point: runs full pipeline (base case, sweeps, dispatch plots)
output/                    # Generated PNGs

tests/                     # Pytest suite — shared fixtures in conftest.py
├── test_config.py
├── test_models.py
├── test_generators.py
├── test_dispatch.py
├── test_simulation.py
├── test_storage.py
├── test_interconnections.py
├── test_price_areas.py
└── test_reliability.py

notebooks/                 # Educational + exploratory notebooks
├── 01_time_grid_and_load.ipynb      # Tier 1 — fundamentals
├── 02_fuel_and_carbon_prices.ipynb
├── 03_renewable_availability.ipynb
├── 04_generators_and_merit_order.ipynb
├── 05_dispatch_engine.ipynb         # Tier 2 — core engine
├── 06_monte_carlo_and_sensitivity.ipynb
├── 07_fuel_price_sensitivity.ipynb  # Tier 3 — advanced modules
├── 08_emissions_tracking.ipynb
├── 09_interconnections.ipynb
├── 10_battery_storage.ipynb
├── 11_full_analysis_pipeline.ipynb  # Tier 4 — capstone
├── phase6_interconnections.ipynb    # Legacy exploratory
└── wind_solar_analysis.ipynb        # Legacy exploratory

webapp/                    # Interactive web UI (imports energy_sim/, never vice-versa)
├── backend/               # FastAPI + SQLite; exposes scenarios/simulations/results APIs
├── frontend/              # React + Vite + TypeScript + Plotly.js
├── data/                  # SQLite DB + generated artifacts
└── run.py                 # Dev launcher
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
- **Fuel and carbon price via Ornstein-Uhlenbeck**: mean-reverting stochastic processes. Each MC run generates a fresh path. Gas, coal, and CO₂ all use the same O-U interface with their own μ/σ/θ.
- **Wind model**: AR(1) process in Gaussian space → Weibull transform → turbine power curve. This preserves temporal autocorrelation (weather fronts last days, not hours). NOT a simple coefficient model like solar.
- **Solar model**: deterministic envelope (month × hour Gaussian) × Markov chain cloud state (per-day, two-state). Night hours are hard-zeroed.
- **Hydro**: currently a must-run band at fixed capacity. A reservoir/SOC-based dispatch model is planned (see `ROADMAP.md`). Do NOT try to make it dispatchable ad-hoc without state tracking — it needs the planned reservoir design.
- **Interconnections**: imports enter the merit order as virtual generators with `srmc = foreign_price + transport_cost`; exports are post-dispatch adjustments when domestic marginal price < foreign_price − transport_cost.
- **Storage**: battery SOC is sequential (breaks vectorization) but O(35040) per unit; charge/discharge triggered by rolling price percentiles.
- **Library/UI separation**: `energy_sim/` is a pure numpy/scipy library with no web or plotting-UI dependencies. The webapp imports it; the reverse is never allowed.

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

244 tests covering config, models, generators, dispatch, simulation, and storage. Tests marked `@pytest.mark.slow` involve multiple MC sweep runs.

## Performance Notes

- Single dispatch (35040 timesteps, ~5 generators): ~30ms (vectorized numpy)
- The inertia-fix loop is NOT vectorized (iterates over violation timesteps only). With the Italian mix this affects 0-5% of timesteps. If it becomes a bottleneck with high-renewable scenarios, consider batch-processing violations.
- Wind availability `generate_profile()` uses a Python loop for AR(1). For very large MC runs, consider rewriting with `scipy.signal.lfilter`.
- 100 MC runs × full dispatch ≈ 7 seconds. Sweeps multiply this by number of scenario points.

## Known Limitations

- No transmission constraints inside the country (copper-plate assumption within a zone)
- No unit commitment (min up/down times, startup sequencing)
- No ramp-rate enforcement between timesteps (only min stable generation)
- Hydro is a flat must-run band, not dispatchable (reservoir model planned — see `ROADMAP.md`)
- No demand response or elastic demand
- Interconnections use a pragmatic import-as-virtual-gen / export-as-extra-load approach, not simultaneous market coupling
- Solar envelope is symmetric around 13:00; real irradiance is slightly asymmetric
- Wind spatial correlation not modeled (all wind farms see same wind process)

## Development Direction

Planned features, priorities, and the distinction between done / in-progress / planned work live in `ROADMAP.md`. Keep this file focused on *what the project is* and how it works; put *where it's going* in the roadmap.
