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
9. **Cross-border exchanges**: Italian base mix with realistic interconnections
   to FR, CH, AT, SI, GR. Compares electricity price, carbon intensity and
   import dependence with vs. without the foreign market. Generates
   flow-summary, flow-duration and price-convergence diagnostics plus a
   dispatch plot showing imports on top of the domestic stack.
10. **Battery storage**: aggregate 2 GW / 4 GWh BESS with rolling-percentile
    arbitrage. Compares price/emissions with and without storage, generates
    SOC annual timeseries and monthly average plots, and sweeps energy capacity
    (1–8 GWh) to produce a revenue-vs-sizing curve.

All output PNG files are saved to ``output/``.
"""

import os
import time
from copy import deepcopy

import numpy as np

from energy_sim.config import (
    ITALIAN_MIX, GAS_SCENARIOS, COAL_SCENARIOS, CO2_SCENARIOS,
    QUARTERS_PER_DAY, P_BASE,
    INTERCONNECTIONS, PRICE_AREAS, PRICE_AREA_CORRELATIONS,
    PRICE_AREAS_CORRELATED, ENABLE_NTC_FAULTS,
    STORAGE_UNITS, ENABLE_STORAGE,
    WEEKDAY_LOAD_FACTORS, HOLIDAY_LOAD_FACTOR,
    ITALIAN_HOLIDAYS_DOY, DEFAULT_LOAD_NOISE_SIGMA,
)
from energy_sim.models import TimeGrid, LoadProfile
from energy_sim.generators import CarbonPriceModel, build_generators
from energy_sim.dispatch import dispatch_year
from energy_sim.interconnections import (
    build_coupling_for_interconnections,
    build_interconnections_from_config,
    realize_interconnections,
)
from energy_sim.storage import build_storage_units
from energy_sim.simulation import (
    run_monte_carlo, sweep_technology, build_sensitivity_heatmap,
    build_incremental_heatmap, sweep_fuel_price, sweep_fuel_prices_2d,
    sweep_storage_capacity,
)
from energy_sim.visualization import (
    plot_heatmap, plot_sensitivity_curve, plot_monthly_heatmap,
    plot_incremental_heatmap, plot_dispatch_day,
    plot_carbon_intensity_curve, plot_emissions_breakdown,
    plot_fuel_price_sensitivity, plot_fuel_sensitivity_coefficient,
    plot_fuel_price_heatmap_2d,
    plot_interconnection_flows_summary, plot_flow_duration_curves,
    plot_price_convergence, plot_dispatch_with_imports,
    plot_import_export_hours, plot_energy_bars_by_country,
    plot_economic_benefit_monthly, plot_co2_benefit_monthly,
    plot_generation_mix_pie,
    plot_storage_soc_timeseries, plot_storage_soc_monthly,
    plot_storage_revenue_vs_capacity,
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

    # ── Step 9: Cross-border exchanges ────────────────────────────────
    # Re-run the base MC with the Italian interconnection topology
    # (IT-FR, IT-CH, IT-AT, IT-SI, IT-GR) wired in. Each border is
    # modelled as a stochastic foreign price (O-U, jointly correlated
    # via Cholesky), a possibly time-varying NTC with random line faults,
    # and a transport cost. Imports compete in the merit order as virtual
    # generators; exports happen post-dispatch whenever the domestic
    # marginal price falls below the foreign floor.
    #
    # Expected effects compared to the closed-system base case:
    # - lower and less volatile domestic price (cheap neighbours displace
    #   marginal gas)
    # - lower carbon intensity when importing from low-carbon areas
    #   (FR @ 50, CH @ 30 gCO₂/kWh) — dual accounting tracks territorial
    #   and consumption-based emissions separately
    # - net imports in line with historical Italian figures (~13-18% of
    #   demand, i.e. ~50-60 TWh/yr)
    print("\n[9/9] Cross-border exchanges (base mix + interconnections)...")
    t0 = time.time()

    ic_mc = run_monte_carlo(
        ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=30,
        interconnections_cfg=INTERCONNECTIONS,
        price_areas_cfg=PRICE_AREAS,
        price_area_correlations=PRICE_AREA_CORRELATIONS,
        price_areas_correlated=PRICE_AREAS_CORRELATED,
        enable_ntc_faults=ENABLE_NTC_FAULTS,
    )

    base_price = base_mc['avg_price'].mean()
    ic_price = ic_mc['avg_price'].mean()
    base_ci = base_mc['carbon_intensity'].mean()
    ic_ci = ic_mc['carbon_intensity'].mean()
    ic_ci_cons = ic_mc['carbon_intensity_consumption'].mean()
    total_net_import = ic_mc['net_import_twh'].sum(axis=1).mean()
    total_imported_emis = ic_mc['imported_emissions_tons'].sum(axis=1).mean()
    total_econ_benefit = ic_mc['total_economic_benefit_eur'].sum(axis=1).mean()
    total_co2_benefit = ic_mc['total_co2_benefit_tons'].sum(axis=1).mean()

    print(f"  Domestic price:   {base_price:.2f} → {ic_price:.2f} "
          f"EUR/MWh  ({ic_price - base_price:+.2f})")
    print(f"  Carbon intensity: {base_ci:.0f} → {ic_ci:.0f} gCO₂/kWh  "
          f"(territorial, domestic only)")
    print(f"  CI consumption:   {ic_ci_cons:.0f} gCO₂/kWh "
          f"(\u0394 vs territorial: {ic_ci_cons - ic_ci:+.1f})")
    print(f"  Net imports:      {total_net_import:.1f} TWh/yr")
    print(f"  Imported CO₂:     {total_imported_emis / 1e6:.2f} Mt/yr "
          f"(consumption-based, embedded in imports)")
    print(f"  Economic benefit: {total_econ_benefit / 1e9:.2f} B\u20ac/yr "
          f"(congestion-rent proxy, all links)")
    print(f"  CO\u2082 benefit:     {total_co2_benefit / 1e6:+.2f} Mt/yr "
          f"(signed; + = avoided vs domestic counterfactual)")

    # Per-link summary table
    print("\n  Per-link flows (MC averages):")
    print(f"  {'Link':<7} {'Net TWh':>9} {'Import':>9} {'Export':>9} "
          f"{'Foreign €':>11} {'Sat %':>7}")
    for i, name in enumerate(ic_mc['interconnection_names']):
        net = ic_mc['net_import_twh'][:, i].mean()
        imp = ic_mc['import_gross_twh'][:, i].mean()
        exp = ic_mc['export_gross_twh'][:, i].mean()
        fp = ic_mc['foreign_price_mean'][:, i].mean()
        sat = ic_mc['ntc_import_saturation_pct'][:, i].mean()
        print(f"  {name:<7} {net:>9.2f} {imp:>9.2f} {exp:>9.2f} "
              f"{fp:>11.2f} {sat:>7.1f}")

    # Summary bar chart across MC runs
    plot_interconnection_flows_summary(
        ic_mc,
        os.path.join(out_dir, 'ic_flows_summary.png'),
    )

    # Phase 6 follow-up: import/export hours, energy by country,
    # economic + CO\u2082 benefit (monthly stacks), and generation mix pie.
    # These plots close out the cross-border metrics requested by the
    # user: utilisation factor per link, TWh traded, economic welfare
    # captured under the congestion-rent convention, and signed CO\u2082
    # impact \u2014 all Monte Carlo averages.
    plot_import_export_hours(
        ic_mc, os.path.join(out_dir, 'ic_hours.png'))
    plot_energy_bars_by_country(
        ic_mc, os.path.join(out_dir, 'ic_energy_by_country.png'))
    plot_economic_benefit_monthly(
        ic_mc, os.path.join(out_dir, 'ic_economic_benefit_monthly.png'))
    plot_co2_benefit_monthly(
        ic_mc, os.path.join(out_dir, 'ic_co2_benefit_monthly.png'))
    plot_generation_mix_pie(
        ic_mc, ITALIAN_MIX,
        os.path.join(out_dir, 'generation_mix_pie.png'))

    # For flow-duration / price-convergence / dispatch-day plots we need
    # a single dispatched year (the MC loop discards per-run DispatchResults
    # to keep memory bounded). Rebuild one with the same seed logic.
    links = build_interconnections_from_config(
        INTERCONNECTIONS, enable_faults=ENABLE_NTC_FAULTS)
    coupling = build_coupling_for_interconnections(
        links, price_areas_cfg=PRICE_AREAS,
        correlations_cfg=PRICE_AREA_CORRELATIONS,
        correlated=PRICE_AREAS_CORRELATED)

    ss = np.random.SeedSequence(42)
    ss_gen, ss_prices, ss_faults = ss.spawn(3)
    rng_gen = np.random.default_rng(ss_gen)
    rng_prices = np.random.default_rng(ss_prices)
    rng_faults = np.random.default_rng(ss_faults)

    tg_ic = TimeGrid()
    tg_ic.set_holiday_calendar(ITALIAN_HOLIDAYS_DOY)

    gens_ic = build_generators(ITALIAN_MIX, GAS_SCENARIOS['base'])
    for g in gens_ic:
        g.prepare_run(tg_ic, rng_gen, CarbonPriceModel(**CO2_SCENARIOS['base']))

    lp_ic = LoadProfile(tg_ic)
    lp_ic.set_weekday_factors({0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0,
                                5: 0.85, 6: 0.75})
    lp_ic.set_holiday_factor(0.80)
    load_ic = lp_ic.generate(rng_gen, noise_sigma=DEFAULT_LOAD_NOISE_SIGMA)

    realizations = realize_interconnections(
        links, coupling, tg_ic, rng_prices, rng_faults)
    result_ic = dispatch_year(gens_ic, load_ic, realizations)

    plot_flow_duration_curves(
        result_ic, os.path.join(out_dir, 'ic_flow_duration.png'))
    plot_price_convergence(
        result_ic, os.path.join(out_dir, 'ic_price_convergence.png'))
    plot_dispatch_with_imports(
        gens_ic, result_ic, load_ic, 15,
        os.path.join(out_dir, 'dispatch_winter_with_imports.png'),
        '(Winter, base mix + interconnections)')
    plot_dispatch_with_imports(
        gens_ic, result_ic, load_ic, 190,
        os.path.join(out_dir, 'dispatch_summer_with_imports.png'),
        '(Summer, base mix + interconnections)')

    print(f"  Time: {time.time() - t0:.1f}s")

    # ── 10. Battery Storage ─────────────────────────────────────────
    print("\n10. Battery storage (Phase 7)")
    t0 = time.time()

    # MC with storage vs without
    storage_mc = run_monte_carlo(
        ITALIAN_MIX, GAS_SCENARIOS['base'],
        coal_scenario=COAL_SCENARIOS['base'],
        co2_scenario=CO2_SCENARIOS['base'],
        n_runs=30, seed=42,
        storage_cfg=STORAGE_UNITS if ENABLE_STORAGE else None,
    )
    base_price_ns = base_mc['avg_price'].mean()
    stor_price = storage_mc['avg_price'].mean()
    stor_ci = storage_mc['carbon_intensity'].mean()

    print(f"  Price: {base_price_ns:.2f} -> {stor_price:.2f} EUR/MWh "
          f"({stor_price - base_price_ns:+.2f})")
    print(f"  CI:    {stor_ci:.0f} gCO\u2082/kWh")

    if storage_mc['storage_names']:
        rev = storage_mc['storage_revenue_eur'][:, 0]
        cycles = storage_mc['storage_equivalent_cycles'][:, 0]
        avg_soc = storage_mc['storage_avg_soc'][:, 0]
        print(f"  Revenue: {rev.mean() / 1e6:+.1f} M\u20ac/yr "
              f"(\u00b1{rev.std() / 1e6:.1f})")
        print(f"  Equiv. cycles: {cycles.mean():.0f}/yr")
        print(f"  Avg SOC: {avg_soc.mean():.2f}")

        # SOC monthly bar chart
        plot_storage_soc_monthly(
            storage_mc, os.path.join(out_dir, 'storage_soc_monthly.png'))

    # Single dispatch for SOC timeseries plot
    tg_st = TimeGrid()
    tg_st.set_holiday_calendar(ITALIAN_HOLIDAYS_DOY)
    lp_st = LoadProfile(tg_st)
    lp_st.set_weekday_factors(WEEKDAY_LOAD_FACTORS)
    lp_st.set_holiday_factor(HOLIDAY_LOAD_FACTOR)
    rng_st = np.random.default_rng(np.random.SeedSequence(42).spawn(3)[0])
    gens_st = build_generators(ITALIAN_MIX, GAS_SCENARIOS['base'],
                               COAL_SCENARIOS['base'])
    co2_st = CarbonPriceModel(**CO2_SCENARIOS['base'])
    for g in gens_st:
        g.prepare_run(tg_st, rng_st, co2_st)
    load_st = lp_st.generate(rng_st, noise_sigma=DEFAULT_LOAD_NOISE_SIGMA)
    su = build_storage_units(STORAGE_UNITS)
    result_st = dispatch_year(gens_st, load_st, storage_units=su)
    plot_storage_soc_timeseries(
        result_st, os.path.join(out_dir, 'storage_soc_annual.png'))

    # Capacity vs revenue sweep
    print("\n  Storage capacity sweep...")
    sweep_res = sweep_storage_capacity(
        ITALIAN_MIX, GAS_SCENARIOS['base'],
        power_gw=2.0,
        energy_gwh_range=np.array([1.0, 2.0, 4.0, 6.0, 8.0]),
        coal_scenario=COAL_SCENARIOS['base'],
        co2_scenario=CO2_SCENARIOS['base'],
        n_runs=15, seed=42,
    )
    plot_storage_revenue_vs_capacity(
        sweep_res, os.path.join(out_dir, 'storage_revenue_vs_capacity.png'))

    print(f"  Time: {time.time() - t0:.1f}s")

    print("\n" + "=" * 60)
    print(f"DONE. All outputs in {out_dir}/")
    print("=" * 60)


if __name__ == '__main__':
    main()
