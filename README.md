# Energy Mix Monte Carlo Simulator

A Monte Carlo simulator for analysing the impact of electricity generation mixes on annualised power prices. Built around the Italian power system (60 GW peak) as a reference case, but technology-agnostic and extensible.

The model captures merit-order dispatch with synchronous inertia constraints, stochastic fuel and carbon prices, renewable availability (solar envelope + cloud Markov chain, wind AR(1)+Weibull), cross-border interconnections, and battery storage. Each Monte Carlo year simulates 35 040 quarter-hours and aggregates price, emission, and curtailment statistics.

Two ways to use it:

- **CLI / library**: Python package `energy_sim/` + entry point `main.py` for scripted analyses.
- **Web application**: FastAPI backend + React frontend for interactive scenario editing, simulation launching, and result visualisation.

## Quick start

### CLI

```bash
python -m venv .venv
source .venv/bin/activate
pip install numpy scipy matplotlib

python main.py
```

Runs the full reference analysis in ~2 minutes: base case, nuclear and solar sweeps, fuel-price sensitivity, interconnections, storage. Outputs PNGs to `output/`.

### Web app

```bash
# Backend dependencies
pip install numpy scipy matplotlib fastapi uvicorn aiosqlite pydantic

# Frontend dependencies (one-time)
cd webapp/frontend && npm install && cd ../..

# Start both backend + frontend
python webapp/run.py
```

Then open http://localhost:5173.

### Tests

```bash
pip install pytest
python -m pytest tests/ -v                 # all tests (~25s)
python -m pytest tests/ -v -m "not slow"   # skip slow MC sweeps
```

229 tests covering config, models, generators, dispatch, simulation, and storage.

## Project layout

```
energy_sim/              # Core simulation library (no web dependencies)
  config.py              # All parameters: ITALIAN_MIX, scenarios, constants
  models.py              # TimeGrid, LoadProfile
  generators.py          # FuelPriceModel, CarbonPriceModel, availability, Generator
  dispatch.py            # Vectorized merit-order dispatch with inertia fix
  simulation.py          # run_monte_carlo, sweep_* utilities, SimulationConfig
  interconnections.py    # Cross-border links and foreign price coupling
  storage.py             # Battery storage with SOC tracking
  visualization.py       # 22 matplotlib plotting functions

main.py                  # CLI pipeline: full analysis with all sweeps

tests/                   # 229 pytest tests

notebooks/               # 11 educational notebooks (time grid → full pipeline)

webapp/
  backend/               # FastAPI REST API
    app.py               # FastAPI app factory
    models.py            # Pydantic request/response schemas
    db.py                # SQLite + aiosqlite helpers
    tasks.py             # Background Monte Carlo runner
    serializers.py       # numpy → JSON bridge
    routes/              # Scenarios + simulations endpoints
  frontend/              # React + TypeScript + Vite
    src/
      api/               # TanStack Query hooks
      components/
        layout/          # AppShell
        scenarios/       # ScenarioForm with 5 tabs
        charts/          # Plotly chart components
        ui/              # shadcn/ui components
      pages/             # ScenariosPage, SimulationsPage, ResultsPage, etc.
  run.py                 # Convenience launcher (backend + vite dev)
```

## How it works

### The simulation pipeline

1. **Scenario definition**: mix of generators (capacity GW, efficiency, emission factor, inertia, etc.), fuel O-U price parameters, interconnection topology, storage.
2. **Monte Carlo loop** (`run_monte_carlo`): for each of N runs, generate fresh stochastic paths for gas/coal/CO₂ prices, solar/wind availability, and noisy load.
3. **Dispatch** (`dispatch_year`): merit-order clearing at each quarter-hour. If synchronous inertia drops below H_min=3.5 s, the cheapest synchronous unit is forced online at minimum stable generation (non-vectorised inertia fix).
4. **Interconnections**: imports compete in merit order as virtual generators; exports happen post-dispatch when domestic price < foreign floor.
5. **Storage**: rolling-percentile arbitrage (charge below 25th, discharge above 75th).
6. **Aggregation**: per-run annual price, monthly prices, emissions, curtailment, inertia, storage revenue, cross-border flows.

### Key design decisions

- **Per-unit internally**: all powers normalised to P_BASE = 60 GW; GW used only in config and dispatch plots.
- **Fuel prices**: Ornstein-Uhlenbeck (mean-reverting stochastic). Fresh path per MC run.
- **Wind**: AR(1) in Gaussian space → Weibull transform → turbine power curve. Preserves temporal autocorrelation.
- **Solar**: deterministic Gaussian envelope (peak 13:00) × per-day two-state cloud Markov chain.
- **Marginal price**: SRMC of the last dispatched generator (standard European day-ahead model).
- **Reproducibility**: base seed + run index. Identical seed → identical results.

### Webapp architecture

`energy_sim/` is a standalone library with **no web dependencies**. The web stack imports and calls it; never the other way around.

- Backend: FastAPI + Pydantic + aiosqlite. Simulations run in a `ThreadPoolExecutor` to avoid blocking the event loop; progress is reported via an optional callback (the only change to `energy_sim.simulation.run_monte_carlo`, default None preserves full CLI compatibility).
- Frontend: React + TypeScript + Vite + Tailwind + shadcn/ui + TanStack Query + Plotly.js. The Vite dev server proxies `/api` → `localhost:8000`.
- Polling: the frontend polls `GET /api/simulations/{id}` every 500 ms while the status is pending/running, then stops automatically.

## Known limitations

- No transmission constraints (copper-plate single bus).
- No unit commitment (min up/down times, startup sequencing).
- No ramp-rate enforcement between timesteps (only min stable generation).
- Hydro is a flat must-run band, not dispatchable.
- No demand response or price-elastic demand.
- Solar envelope symmetric around 13:00 (real irradiance slightly asymmetric).
- Wind spatial correlation not modelled (all wind farms see the same process).

## Roadmap

Items implemented (see `CLAUDE.md` for details):

1. ✅ CO₂ emissions tracking
2. ✅ Coal generator type
3. ✅ Stochastic CO₂ price
4. ✅ Fuel price sensitivity analysis
5. ✅ Load profile enhancements (weekday/holiday factors)
6. ✅ Import/export model (interconnections)
7. ✅ Battery storage
8. ✅ Educational notebook series (11 tiered notebooks)
9. 🚧 Web application (phases 1–4 done: backend, scenario editor, results dashboard with 6 charts; phases 5–6 remaining: interconnection/storage charts, comparison view)

## Performance

- Single dispatch (35 040 timesteps, ~5 generators): ~30 ms (vectorised numpy).
- 100 MC runs × full dispatch: ~7 seconds.
- Sweeps multiply this by the number of scenario points (typically 20–30 s each).

## License

See repository root for licence details.
