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

83 tests covering config, models, generators, dispatch, and simulation. Tests marked `@pytest.mark.slow` involve multiple MC sweep runs.

## Extending the Model

### Adding a new generator type
1. Add default parameters in `config.py` → `ITALIAN_MIX`
2. If it needs a custom availability model, create a class in `generators.py` with `generate_profile(time_grid, rng) → np.ndarray(35040,)`
3. Add the routing logic in `build_generators()` (fuel model selection, availability model selection)
4. The dispatch engine is fully generic — no changes needed there

### Adding load variability (weekday, holiday, stochastic)
`LoadProfile` already supports `set_weekday_factors()`, `set_holiday_factor()`, and `noise_sigma` in `generate()`. The `TimeGrid` has `day_of_week` and `is_holiday` attributes ready. Just populate them.

### Adding storage (batteries)
This is the most impactful missing feature. Storage has inter-temporal state (SOC) like hydro reservoirs but simpler (no inflows, no evaporation). Implementation approach:
- Create `StorageUnit` with `capacity_mwh`, `power_mw`, `efficiency_roundtrip`, `soc` state
- In `dispatch_year()`, after merit-order dispatch: if marginal price < threshold → charge; if marginal price > threshold → discharge. The threshold can be a rolling percentile of recent prices.
- This breaks pure vectorization — the SOC loop must be sequential. But it's only one unit, so the loop is O(35040), not O(n_gen × 35040).

### Incremental sensitivity heatmap (Δ price)
Implemented in `build_incremental_heatmap()` and `plot_incremental_heatmap()`. Shows the marginal price impact of adding Δ% of a technology at different base penetration levels. Collects all unique penetration levels, runs a single `sweep_technology()` call, then assembles finite-difference matrices (delta_price and marginal_cost per %).

### Making CO2 stochastic
`CarbonPriceModel` already has the same interface as `FuelPriceModel`. Replace the `generate_path()` implementation with O-U process. Suggested parameters: μ=65, σ=10, θ=0.05 (slower mean-reversion than gas).

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
