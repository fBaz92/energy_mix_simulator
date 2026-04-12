"""Entry point for the Energy Mix Monte Carlo Simulator.

Runs the full analysis pipeline in nine sequential steps:

1. **Base case**: Monte Carlo simulation of the current Italian mix (no nuclear,
   no coal) under the base gas price scenario.
2. **Nuclear sensitivity sweep**: varies nuclear penetration from 0% to 30%.
3. **Nuclear x Gas heatmap**: cross-analysis of nuclear penetration against three
   gas price scenarios (base/tension/crisis).
4. **Solar sensitivity sweep**: same as step 2 but for solar PV (0%-50%).
5. **Coal sensitivity sweep**: varies coal penetration from 0% to 30%. Coal has
   high CO₂ emissions but cheaper fuel than gas.
6. **Incremental sensitivity heatmaps**: shows how the marginal value of adding
   Δ% of nuclear or solar changes at different base penetration levels. Captures
   non-linearity and price cannibalisation effects.
7. **Fuel price sensitivity**: sweeps gas and coal fuel prices independently
   (1D) and jointly (2D heatmap) to assess electricity price exposure to
   fuel cost shocks. Also computes sensitivity coefficients.
8. **Dispatch day plots**: single-day merit-order stack visualizations showing
   which generators run at each quarter-hour, for summer/winter with and
   without nuclear.

All output PNG files are saved to ``output/``.
"""

import os
import time
from copy import deepcopy

import numpy as np

from energy_sim.config import (
    ITALIAN_MIX, GAS_SCENARIOS, COAL_SCENARIOS, CO2_SCENARIOS,
    QUARTERS_PER_DAY,
)
from energy_sim.models import TimeGrid, LoadProfile
from energy_sim.generators import CarbonPriceModel, build_generators
from energy_sim.simulation import (
    run_monte_carlo, sweep_technology, build_sensitivity_heatmap,
    build_incremental_heatmap, sweep_fuel_price, sweep_fuel_prices_2d,
)
from energy_sim.visualization import (
    plot_heatmap, plot_sensitivity_curve, plot_monthly_heatmap,
    plot_incremental_heatmap, plot_dispatch_day,
    plot_carbon_intensity_curve, plot_emissions_breakdown,
    plot_fuel_price_sensitivity, plot_fuel_sensitivity_coefficient,
    plot_fuel_price_heatmap_2d,
)


def main() -> None:
    """Run the full simulation and visualization pipeline.

    Executes all nine analysis steps sequentially, printing progress and
    key results to stdout. Each step is timed independently.
    """
    # Create the output directory if it doesn't exist. All generated PNGs
    # (sensitivity curves, heatmaps, dispatch plots) are saved here.
    out_dir = os.path.join(os.path.dirname(__file__), 'output')
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("ENERGY MIX MONTE CARLO SIMULATOR")
    print("=" * 60)

    # ── Step 1: Base case Monte Carlo ──────────────────────────────────
    # Run 30 Monte Carlo years of the current Italian generation mix
    # (gas 45 GW, solar 30 GW, wind 13 GW, hydro 8 GW, nuclear 0 GW)
    # under the base gas price scenario (TTF mu=35 EUR/MWh_th).
    #
    # Each MC run generates fresh stochastic fuel prices (O-U process),
    # solar/wind availability profiles, and noisy load. The dispatch
    # engine runs merit-order + inertia fix for each year.
    #
    # Result: avg_price is the mean annual electricity price across runs
    # (EUR/MWh), avg_inertia is the mean system inertia constant (seconds).
    # These serve as the reference point for all sensitivity analyses.
    print("\n[1/9] Running base case (Italian mix, no nuclear, gas base)...")
    t0 = time.time()
    base_mc = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=30)
    print(f"  Base price: {base_mc['avg_price'].mean():.2f} "
          f"\u00b1 {base_mc['avg_price'].std():.2f} EUR/MWh")
    print(f"  Mean inertia: {base_mc['avg_inertia'].mean():.2f} s")
    print(f"  Total CO₂: {base_mc['total_emissions'].mean() / 1e6:.2f} Mt/year")
    print(f"  Carbon intensity: {base_mc['carbon_intensity'].mean():.0f} gCO₂/kWh")
    for tech, vals in base_mc['emissions_by_tech'].items():
        if vals.mean() > 0:
            print(f"    {tech}: {vals.mean() / 1e6:.2f} Mt/year")
    print(f"  Time: {time.time() - t0:.1f}s")

    # ── Step 2: Nuclear penetration sensitivity ───────────────────────
    # Sweep nuclear capacity from 0% to 30% of total installed capacity
    # (0 to ~29 GW). At each level, run 30 MC years and record mean
    # price, price std, monthly breakdown, curtailment, and inertia.
    #
    # Two plots are generated:
    # - nuclear_sensitivity.png: mean price vs nuclear % with error bars
    # - nuclear_monthly.png: heatmap of monthly prices across penetrations
    #
    # Interpretation: nuclear displaces gas in the merit order (lower SRMC),
    # reducing the marginal price. The inertia also improves since nuclear
    # is synchronous (H=6s). Curtailment should stay low because nuclear
    # is must-run (CF=0.9) but has high min_stable_pct.
    print("\n[2/9] Nuclear penetration sweep (base gas scenario)...")
    t0 = time.time()
    nuc_pcts = np.array([0, 5, 10, 15, 20, 25, 30])
    nuc_results = sweep_technology(ITALIAN_MIX, 'nuclear', nuc_pcts,
                                   GAS_SCENARIOS['base'], n_runs=30)
    plot_sensitivity_curve(nuc_results, 'Nuclear',
                           os.path.join(out_dir, 'nuclear_sensitivity.png'))
    plot_monthly_heatmap(nuc_results, 'Nuclear',
                         os.path.join(out_dir, 'nuclear_monthly.png'))
    plot_carbon_intensity_curve(nuc_results, 'Nuclear',
                                os.path.join(out_dir, 'nuclear_co2.png'))
    plot_emissions_breakdown(nuc_results, 'Nuclear',
                             os.path.join(out_dir, 'nuclear_emissions_breakdown.png'))
    print(f"  Time: {time.time() - t0:.1f}s")

    # ── Step 3: Nuclear x Gas price 2D heatmap ────────────────────────
    # Cross-analyze nuclear penetration against all three gas scenarios:
    # base (mu=35), tension (mu=55), crisis (mu=90 EUR/MWh_th).
    #
    # For each (gas_scenario, nuclear_%) combination, run 20 MC years.
    # Result is a 2D matrix of mean electricity prices.
    #
    # Output: nuclear_gas_heatmap.png — shows how the value of nuclear
    # increases with gas price: at mu=35 the price reduction is modest,
    # but at mu=90 (crisis) nuclear dramatically lowers system cost.
    print("\n[3/9] Nuclear \u00d7 Gas price heatmap...")
    t0 = time.time()
    price_mat, inertia_mat, gas_labels = build_sensitivity_heatmap(
        ITALIAN_MIX, 'nuclear', GAS_SCENARIOS, nuc_pcts, n_runs=20)
    plot_heatmap(price_mat, nuc_pcts, gas_labels, 'Nuclear',
                 os.path.join(out_dir, 'nuclear_gas_heatmap.png'))
    print(f"  Time: {time.time() - t0:.1f}s")

    # ── Step 4: Solar PV penetration sensitivity ──────────────────────
    # Same methodology as step 2 but for solar PV (0% to 50%).
    # Solar has zero SRMC (no fuel, low VOM) so it enters at the bottom
    # of the merit order, but its output is concentrated in midday hours
    # and varies seasonally (high in summer, low in winter).
    #
    # Key differences from nuclear:
    # - Solar is non-synchronous (H=0) → may trigger inertia violations
    # - Solar is intermittent → higher curtailment at high penetrations
    # - Price reduction is strongest in summer midday, minimal at night
    #
    # Output: solar_sensitivity.png and solar_monthly.png
    print("\n[4/9] Solar penetration sweep...")
    t0 = time.time()
    sol_pcts = np.array([0, 10, 20, 30, 40, 50])
    sol_results = sweep_technology(ITALIAN_MIX, 'solar', sol_pcts,
                                   GAS_SCENARIOS['base'], n_runs=20)
    plot_sensitivity_curve(sol_results, 'Solar PV',
                           os.path.join(out_dir, 'solar_sensitivity.png'))
    plot_monthly_heatmap(sol_results, 'Solar PV',
                         os.path.join(out_dir, 'solar_monthly.png'))
    plot_carbon_intensity_curve(sol_results, 'Solar PV',
                                os.path.join(out_dir, 'solar_co2.png'))
    plot_emissions_breakdown(sol_results, 'Solar PV',
                             os.path.join(out_dir, 'solar_emissions_breakdown.png'))
    print(f"  Time: {time.time() - t0:.1f}s")

    # ── Step 5: Coal penetration sensitivity ─────────────────────────
    # Coal is a dispatchable thermal generator with high CO₂ emissions
    # (0.34 tCO₂/MWh_th, ~850 gCO₂/kWh_e) but cheaper fuel than gas.
    # At current CO₂ prices (~65 EUR/ton), coal SRMC ≈ gas SRMC, making
    # merit-order position sensitive to CO₂ and fuel price fluctuations.
    #
    # Key metrics to watch:
    # - Price impact: coal may lower price if its SRMC < gas SRMC
    # - Emissions: adding coal dramatically increases system CO₂
    # - Inertia: coal is synchronous (H=5s), improving grid stability
    print("\n[5/9] Coal penetration sweep...")
    t0 = time.time()
    coal_pcts = np.array([0, 5, 10, 15, 20, 25, 30])
    coal_results = sweep_technology(ITALIAN_MIX, 'coal', coal_pcts,
                                    GAS_SCENARIOS['base'], n_runs=20)
    plot_sensitivity_curve(coal_results, 'Coal',
                           os.path.join(out_dir, 'coal_sensitivity.png'))
    plot_monthly_heatmap(coal_results, 'Coal',
                         os.path.join(out_dir, 'coal_monthly.png'))
    plot_carbon_intensity_curve(coal_results, 'Coal',
                                os.path.join(out_dir, 'coal_co2.png'))
    plot_emissions_breakdown(coal_results, 'Coal',
                             os.path.join(out_dir, 'coal_emissions_breakdown.png'))
    print(f"  Time: {time.time() - t0:.1f}s")

    # ── Step 6: Incremental sensitivity heatmaps ──────────────────────
    # For nuclear and solar, show how the marginal price impact of adding
    # an extra Δ% changes depending on the base penetration level.
    #
    # Example: adding +5% nuclear when starting from 0% may reduce the
    # price by X EUR/MWh, but adding the same +5% when starting from 20%
    # may have a different (usually smaller) effect — diminishing returns.
    # For solar, high penetrations can even cause price cannibalisation
    # (near-zero midday prices make further solar less valuable).
    #
    # The function collects all unique penetration levels, runs a single
    # sweep_technology() call, then assembles finite differences.
    print("\n[6/9] Incremental sensitivity heatmaps...")
    t0 = time.time()

    inc_base_pcts = np.array([0, 5, 10, 15, 20, 25])
    inc_deltas = np.array([1, 2, 5, 10])

    delta_nuc, marginal_nuc = build_incremental_heatmap(
        ITALIAN_MIX, 'nuclear', inc_base_pcts, inc_deltas,
        GAS_SCENARIOS['base'], n_runs=20)
    plot_incremental_heatmap(delta_nuc, inc_base_pcts, inc_deltas, 'Nuclear',
                             os.path.join(out_dir, 'nuclear_incremental.png'))

    delta_sol, marginal_sol = build_incremental_heatmap(
        ITALIAN_MIX, 'solar', inc_base_pcts, inc_deltas,
        GAS_SCENARIOS['base'], n_runs=20)
    plot_incremental_heatmap(delta_sol, inc_base_pcts, inc_deltas, 'Solar PV',
                             os.path.join(out_dir, 'solar_incremental.png'))
    print(f"  Time: {time.time() - t0:.1f}s")

    # ── Step 7: Fuel price sensitivity analysis ──────────────────────
    # Sweep gas and coal fuel prices independently to measure the
    # electricity price exposure to fuel cost shocks. Then sweep both
    # jointly in a 2D grid to visualize fuel-switching dynamics.
    #
    # Uses a mix with coal (15 GW) to make the 2D analysis meaningful.
    # Without coal in the mix, the coal price sweep has no effect.
    #
    # Three plot types:
    # - 1D curve: electricity price ± σ vs fuel μ
    # - Sensitivity coefficient: ∂(elec_price)/∂(fuel_price)
    # - 2D heatmap: electricity price vs (gas μ, coal μ)
    print("\n[7/9] Fuel price sensitivity analysis...")
    t0 = time.time()

    # Mix with coal for fuel price analysis
    mix_fuel = deepcopy(ITALIAN_MIX)
    mix_fuel['coal']['capacity_gw'] = 15.0

    # 1D gas price sweep (with coal in mix)
    gas_mu_range = np.array([20, 30, 40, 50, 60, 70, 80, 90, 100])
    print("  Gas price sweep:")
    gas_results = sweep_fuel_price(
        mix_fuel, 'gas', gas_mu_range,
        GAS_SCENARIOS['base'], COAL_SCENARIOS['base'],
        n_runs=20)
    plot_fuel_price_sensitivity(
        gas_results, 'Gas',
        os.path.join(out_dir, 'fuel_sensitivity_gas.png'))
    plot_fuel_sensitivity_coefficient(
        gas_results, 'Gas',
        os.path.join(out_dir, 'fuel_sensitivity_coeff_gas.png'))

    # 1D coal price sweep (with coal in mix)
    coal_mu_range = np.array([8, 12, 16, 20, 24, 28])
    print("  Coal price sweep:")
    coal_fuel_results = sweep_fuel_price(
        mix_fuel, 'coal', coal_mu_range,
        GAS_SCENARIOS['base'], COAL_SCENARIOS['base'],
        n_runs=20)
    plot_fuel_price_sensitivity(
        coal_fuel_results, 'Coal',
        os.path.join(out_dir, 'fuel_sensitivity_coal.png'))
    plot_fuel_sensitivity_coefficient(
        coal_fuel_results, 'Coal',
        os.path.join(out_dir, 'fuel_sensitivity_coeff_coal.png'))

    # 2D gas × coal price heatmap
    gas_mu_2d = np.array([25, 40, 55, 70, 90])
    coal_mu_2d = np.array([8, 14, 20, 26])
    print("  2D gas × coal price sweep:")
    price_2d, ci_2d = sweep_fuel_prices_2d(
        mix_fuel, gas_mu_2d, coal_mu_2d,
        GAS_SCENARIOS['base'], COAL_SCENARIOS['base'],
        n_runs=15)
    plot_fuel_price_heatmap_2d(
        price_2d, gas_mu_2d, coal_mu_2d,
        os.path.join(out_dir, 'fuel_price_heatmap_2d.png'))

    print(f"  Time: {time.time() - t0:.1f}s")

    # ── Step 8: Dispatch day plots ────────────────────────────────────
    # Generate single-day merit-order stack area charts showing how each
    # generator is dispatched across 96 quarter-hours. These give an
    # intuitive picture of the dispatch dynamics that aggregate statistics
    # (steps 1-4) cannot capture.
    print("\n[8/9] Dispatch day plots...")

    # Set up the temporal grid, load profile (with 2% noise), and a
    # fixed RNG seed so the plots are reproducible across runs.
    tg = TimeGrid()
    lp = LoadProfile(tg)
    rng = np.random.default_rng(42)
    load = lp.generate(rng, noise_sigma=0.02)

    # Plot A: Summer day (day 190 ~ July 9), current mix (no nuclear).
    # Solar output peaks around 13:00, gas fills the rest. Wind contributes
    # variably. Hydro provides a flat must-run band at the bottom.
    # This is the status quo dispatch pattern.
    gens_base = build_generators(ITALIAN_MIX, GAS_SCENARIOS['base'])
    for g in gens_base:
        g.prepare_run(tg, rng, CarbonPriceModel(**CO2_SCENARIOS['base']))
    plot_dispatch_day(gens_base, tg, load, 190,
                      os.path.join(out_dir, 'dispatch_summer.png'),
                      '(Summer, no nuclear)')

    # Plot B: Same summer day but with 20% nuclear added to the mix.
    # Nuclear runs as must-run at 90% CF, displacing gas. The gas plant
    # now only ramps up during peak hours. Compare with Plot A to see
    # how much gas is displaced and how the marginal price changes.
    mix_nuc = deepcopy(ITALIAN_MIX)
    mix_nuc['nuclear']['capacity_gw'] = (
        sum(v['capacity_gw'] for v in ITALIAN_MIX.values()) * 0.20
    )
    gens_nuc = build_generators(mix_nuc, GAS_SCENARIOS['base'])
    for g in gens_nuc:
        g.prepare_run(tg, rng, CarbonPriceModel(**CO2_SCENARIOS['base']))
    plot_dispatch_day(gens_nuc, tg, load, 190,
                      os.path.join(out_dir, 'dispatch_summer_nuclear.png'),
                      '(Summer, 20% nuclear)')

    # Plot C: Winter day (day 15 ~ Jan 15) with 20% nuclear.
    # Solar output is much lower in winter, so gas covers a larger share.
    # Nuclear's contribution is more visible relative to the reduced
    # renewable output. Load shape also differs (evening peak vs summer
    # afternoon peak).
    plot_dispatch_day(gens_nuc, tg, load, 15,
                      os.path.join(out_dir, 'dispatch_winter_nuclear.png'),
                      '(Winter, 20% nuclear)')

    print("\n" + "=" * 60)
    print(f"DONE. All outputs in {out_dir}/")
    print("=" * 60)


if __name__ == '__main__':
    main()
