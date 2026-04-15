"""
Monte Carlo simulation runner and scenario sweep utilities.

Provides the core simulation loop (:func:`run_monte_carlo`) that repeatedly
builds generators, generates stochastic paths, dispatches, and aggregates
price statistics. Also provides sweep utilities for sensitivity analysis
across technology penetrations and gas price scenarios.
"""

import numpy as np
from copy import deepcopy

from energy_sim.config import (
    QUARTERS_PER_YEAR, N_MC_RUNS, RANDOM_SEED, P_PEAK_GW, P_BASE,
    ITALIAN_MIX, GAS_SCENARIOS, COAL_SCENARIOS, CO2_SCENARIOS,
    QUARTERS_PER_DAY,
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


def run_monte_carlo(mix_config: dict, gas_scenario: dict,
                    coal_scenario: dict | None = None,
                    co2_scenario: dict | None = None,
                    n_runs: int = N_MC_RUNS,
                    load_noise: float = DEFAULT_LOAD_NOISE_SIGMA,
                    seed: int = RANDOM_SEED,
                    weekday_factors: dict[int, float] | None = WEEKDAY_LOAD_FACTORS,
                    holiday_factor: float | None = HOLIDAY_LOAD_FACTOR,
                    holiday_calendar: list[int] | None = ITALIAN_HOLIDAYS_DOY,
                    interconnections_cfg: dict[str, dict] | None = None,
                    price_areas_cfg: dict[str, dict] | None = None,
                    price_area_correlations: dict[tuple[str, str], float] | None = None,
                    price_areas_correlated: bool = True,
                    enable_ntc_faults: bool = True) -> dict:
    """Run a Monte Carlo simulation of the electricity market.

    For each run: builds fresh generators (new stochastic fuel price paths),
    generates a load profile with noise, dispatches via merit order, and
    collects price/curtailment/inertia statistics.

    Args:
        mix_config: Generation mix dictionary (see
            :data:`~energy_sim.config.ITALIAN_MIX`).
        gas_scenario: Gas price scenario parameters (keys: ``mu``, ``sigma``,
            ``theta``).
        coal_scenario: Coal price scenario parameters. If ``None``, defaults
            to ``COAL_SCENARIOS['base']``.
        co2_scenario: CO2 price scenario parameters (keys: ``mu``, ``sigma``,
            ``theta``). If ``None``, defaults to ``CO2_SCENARIOS['base']``.
        n_runs: Number of Monte Carlo runs. Defaults to ``N_MC_RUNS``.
        load_noise: Standard deviation of multiplicative Gaussian load noise.
            Defaults to ``DEFAULT_LOAD_NOISE_SIGMA`` (0.04).
        seed: Base random seed. Run *i* uses ``seed + i``.
            Defaults to ``RANDOM_SEED``.
        weekday_factors: Day-of-week load multipliers (0=Monday, 6=Sunday).
            Defaults to ``WEEKDAY_LOAD_FACTORS`` (reduced weekend demand).
            Pass ``None`` to disable weekday modulation.
        holiday_factor: Load multiplier for public holidays, applied on top
            of weekday factors. Defaults to ``HOLIDAY_LOAD_FACTOR`` (0.80).
            Pass ``None`` to disable holiday modulation.
        holiday_calendar: List of day-of-year indices (0-364) for public
            holidays. Defaults to ``ITALIAN_HOLIDAYS_DOY``.
            Pass ``None`` to disable holiday modulation.
        interconnections_cfg: Optional mapping ``name -> link_params``
            (see :data:`~energy_sim.config.INTERCONNECTIONS`). When ``None``
            or empty, the simulation runs without cross-border exchanges —
            fully backward compatible. When supplied, must be accompanied by
            ``price_areas_cfg``.
        price_areas_cfg: Optional mapping ``area_name -> price_params``
            (see :data:`~energy_sim.config.PRICE_AREAS`). Required when
            ``interconnections_cfg`` is supplied.
        price_area_correlations: Optional pairwise correlation dict for the
            foreign-price stochastic coupling. Missing pairs default to 0.
        price_areas_correlated: If ``False``, each foreign price path is
            simulated independently (Cholesky step is identity).
        enable_ntc_faults: If ``False``, all interconnections are forced to
            :class:`~energy_sim.reliability.PerfectReliability` — useful to
            isolate the price effect of faults from other noise sources.

    Returns:
        dict: Aggregated results with keys:

            - ``'avg_price'`` (np.ndarray): Mean annual price for each run,
              shape ``(n_runs,)``, EUR/MWh.
            - ``'monthly_prices'`` (np.ndarray): Monthly average prices,
              shape ``(n_runs, 12)``, EUR/MWh.
            - ``'curtailment'`` (np.ndarray): Total curtailed energy per run,
              shape ``(n_runs,)``, in p.u.-quarter-hours.
            - ``'avg_inertia'`` (np.ndarray): Mean system inertia per run,
              shape ``(n_runs,)``, in seconds.
            - ``'total_emissions'`` (np.ndarray): Total annual CO₂ emissions
              per run, shape ``(n_runs,)``, in tons (territorial).
            - ``'carbon_intensity'`` (np.ndarray): Average carbon intensity
              per run, shape ``(n_runs,)``, in gCO₂/kWh (territorial).
            - ``'emissions_by_tech'`` (dict[str, np.ndarray]): Per-technology
              annual emissions, each shape ``(n_runs,)``, in tons.

            When interconnections are active, additional keys are populated
            (otherwise they hold empty arrays / lists):

            - ``'interconnection_names'`` (list[str]): Ordered link names.
            - ``'net_import_twh'`` (np.ndarray): Per-run, per-link net
              imports (positive = into domestic system, negative = export),
              shape ``(n_runs, n_links)``, in TWh.
            - ``'import_gross_twh'`` (np.ndarray): Gross imports per run
              per link, shape ``(n_runs, n_links)``, in TWh.
            - ``'export_gross_twh'`` (np.ndarray): Gross exports per run
              per link, shape ``(n_runs, n_links)``, in TWh.
            - ``'imported_emissions_tons'`` (np.ndarray): Consumption-based
              CO₂ embedded in net imports, shape ``(n_runs, n_links)``,
              in tons.
            - ``'foreign_price_mean'`` (np.ndarray): Time-average foreign
              day-ahead price per link, shape ``(n_runs, n_links)``,
              in EUR/MWh.
            - ``'ntc_import_saturation_pct'`` (np.ndarray): Share of
              timesteps where import dispatch reached the effective NTC
              ceiling (availability-derated), shape ``(n_runs, n_links)``,
              in percent.
            - ``'import_hours'`` (np.ndarray): Hours per year in net-import
              state per link, shape ``(n_runs, n_links)``, in hours.
            - ``'export_hours'`` (np.ndarray): Hours per year in net-export
              state per link, shape ``(n_runs, n_links)``, in hours.
            - ``'import_energy_mwh'`` (np.ndarray): Gross import volume per
              run per link, shape ``(n_runs, n_links)``, in MWh.
            - ``'export_energy_mwh'`` (np.ndarray): Gross export volume per
              run per link, shape ``(n_runs, n_links)``, in MWh.
            - ``'total_economic_benefit_eur'`` (np.ndarray): Congestion-rent
              economic benefit per link over the year, shape
              ``(n_runs, n_links)``, in EUR. Always ≥ 0.
            - ``'total_co2_benefit_tons'`` (np.ndarray): Signed CO₂ benefit
              (positive = avoided emissions) per link over the year, shape
              ``(n_runs, n_links)``, in tonnes. Can be negative when
              importing from a dirtier foreign mix.
            - ``'economic_benefit_monthly_eur'`` (np.ndarray): Monthly
              economic benefit, shape ``(n_runs, n_links, 12)``, in EUR.
            - ``'co2_benefit_monthly_tons'`` (np.ndarray): Monthly CO₂
              benefit (signed), shape ``(n_runs, n_links, 12)``, in tonnes.
            - ``'carbon_intensity_consumption'`` (np.ndarray): Consumption-
              based carbon intensity (domestic emissions plus signed
              attribution of cross-border flows divided by load), shape
              ``(n_runs,)``, in gCO₂/kWh. Always populated; equals
              ``carbon_intensity`` when no interconnections are active.
    """
    tg = TimeGrid()
    if holiday_calendar is not None:
        tg.set_holiday_calendar(holiday_calendar)

    lp = LoadProfile(tg)
    if weekday_factors is not None:
        lp.set_weekday_factors(weekday_factors)
    if holiday_factor is not None and holiday_calendar is not None:
        lp.set_holiday_factor(holiday_factor)

    co2_params = co2_scenario or CO2_SCENARIOS['base']
    co2 = CarbonPriceModel(**co2_params)

    # ── Interconnection setup (once per MC, reused across runs) ────────
    # Both sides of the cross-border abstraction are built outside the loop:
    # static link definitions are invariant across MC runs, and the coupling
    # carries no random state (only the correlation structure + price-model
    # parameters). Per-run stochasticity is injected via independent RNGs
    # derived from the base seed, below.
    has_ic = bool(interconnections_cfg)
    if has_ic:
        if not price_areas_cfg:
            raise ValueError(
                "price_areas_cfg is required when interconnections_cfg is "
                "supplied (each link references a price area).")
        links = build_interconnections_from_config(
            interconnections_cfg, enable_faults=enable_ntc_faults)
        coupling = build_coupling_for_interconnections(
            links,
            price_areas_cfg=price_areas_cfg,
            correlations_cfg=price_area_correlations,
            correlated=price_areas_correlated,
        )
        ic_names = [l.name for l in links]
    else:
        links = []
        coupling = None
        ic_names = []
    n_links = len(ic_names)

    # Energy conversion factor: p.u.·quarter-hour → MWh.
    # 1 p.u. = P_BASE GW = P_BASE · 1000 MW; integrated over 0.25 h gives MWh.
    pu_qh_to_mwh = P_BASE * 1000.0 * 0.25

    avg_prices = []
    monthly_avg_prices = []
    total_curtailment = []
    avg_inertia = []
    total_emissions = []
    carbon_intensity = []
    emissions_by_tech_lists: dict[str, list[float]] = {}
    net_import_twh_rows = []
    import_gross_twh_rows = []
    export_gross_twh_rows = []
    imported_emissions_tons_rows = []
    foreign_price_mean_rows = []
    ntc_import_saturation_rows = []
    # New per-link metrics from InterconnectionMetrics (Phase 6 follow-up).
    # Monthly aggregates are kept per run so the caller can derive both
    # year-on-year variability and seasonal patterns without storing the
    # full 35040-step granularity (~42 MB per metric per run).
    import_hours_rows = []
    export_hours_rows = []
    import_energy_mwh_rows = []
    export_energy_mwh_rows = []
    total_econ_benefit_rows = []
    total_co2_benefit_rows = []
    econ_benefit_monthly_rows = []
    co2_benefit_monthly_rows = []
    # Consumption-based carbon intensity: always populated, equal to
    # territorial when no links are active. Tracks how cross-border
    # attribution shifts Italy's footprint relative to the IPCC
    # territorial figure already exposed in ``carbon_intensity``.
    carbon_intensity_consumption = []

    for run in range(n_runs):
        # RNG separation: derive three independent streams from a single
        # SeedSequence so that the stochastic sources (generators, foreign
        # prices, link faults) can be isolated in sensitivity studies
        # without their random draws interfering with one another.
        ss = np.random.SeedSequence(seed + run)
        ss_gen, ss_prices, ss_faults = ss.spawn(3)
        rng = np.random.default_rng(ss_gen)
        rng_prices = np.random.default_rng(ss_prices)
        rng_faults = np.random.default_rng(ss_faults)

        gens = build_generators(mix_config, gas_scenario, coal_scenario)
        for g in gens:
            g.prepare_run(tg, rng, co2)

        load = lp.generate(rng, noise_sigma=load_noise)

        if has_ic:
            realizations = realize_interconnections(
                links, coupling, tg, rng_prices, rng_faults)
        else:
            realizations = None

        result = dispatch_year(gens, load, realizations)

        avg_prices.append(result.marginal_price.mean())
        total_curtailment.append(result.curtailment.sum())
        avg_inertia.append(result.h_system.mean())

        monthly = np.zeros(12)
        for m in range(1, 13):
            mask = tg.month == m
            monthly[m - 1] = result.marginal_price[mask].mean()
        monthly_avg_prices.append(monthly)

        # CO₂ emissions aggregation (territorial).
        # result.emissions is in tCO₂ per quarter-hour despite the dispatch
        # docstring wording; unit analysis:
        # power_pu · P_BASE(GW) · 0.25(h) · 1000 · ef(tCO₂/MWh_th) / η = tCO₂.
        run_total_emissions = result.emissions.sum()
        total_emissions.append(run_total_emissions)

        # Carbon intensity: gCO₂/kWh
        # Total energy served = sum(power_pu) * P_BASE(GW) * 0.25(h) * 1e6(kW/GW)
        total_energy_kwh = result.power.sum() * P_PEAK_GW * 0.25 * 1e6
        # Total emissions in grams = tons * 1e6
        ci = (run_total_emissions * 1e6 / total_energy_kwh
              if total_energy_kwh > 0 else 0.0)
        carbon_intensity.append(ci)

        # Per-technology emissions (tons)
        for i, name in enumerate(result.gen_names):
            if name not in emissions_by_tech_lists:
                emissions_by_tech_lists[name] = []
            emissions_by_tech_lists[name].append(result.emissions[i].sum())

        # ── Per-link aggregates when interconnections are active ──
        if has_ic:
            # Net flows: integrate signed p.u.·qh → MWh → TWh.
            net_mwh = result.net_import_pu.sum(axis=1) * pu_qh_to_mwh
            # Gross import = positive part of net + any export-clawback is
            # already separated at the dispatch level: import_power lives in
            # the power matrix (rows n_domestic:), export_power is net - import.
            import_power = result.power[-n_links:, :] if n_links > 0 else (
                np.zeros((0, result.power.shape[1])))
            export_power = np.maximum(
                import_power - result.net_import_pu, 0.0)
            import_twh = import_power.sum(axis=1) * pu_qh_to_mwh / 1e6
            export_twh = export_power.sum(axis=1) * pu_qh_to_mwh / 1e6

            net_import_twh_rows.append(net_mwh / 1e6)
            import_gross_twh_rows.append(import_twh)
            export_gross_twh_rows.append(export_twh)
            # DispatchResult.emissions_imported_tons is already in tonnes
            # per quarter-hour — simply sum over the year.
            imported_emissions_tons_rows.append(
                result.emissions_imported_tons.sum(axis=1))
            foreign_price_mean_rows.append(result.foreign_prices.mean(axis=1))

            # NTC saturation: share of timesteps where import reaches the
            # availability-derated ceiling. Tolerance 1e-9 p.u. to tolerate
            # floating-point slack.
            ntc_ceiling = np.array([r.ntc_import_pu_path for r in realizations])
            saturated = (
                import_power >= np.maximum(ntc_ceiling - 1e-9, 0.0)
            ) & (ntc_ceiling > 1e-12)
            sat_pct = 100.0 * saturated.mean(axis=1) if n_links > 0 else (
                np.zeros(0))
            ntc_import_saturation_rows.append(sat_pct)

            # ── New per-link metrics (InterconnectionMetrics) ──────────
            # dispatch_year() attaches an ic_metrics object when at least
            # one interconnection is active. We promote its annual totals
            # into per-run rows and aggregate the per-qh series to monthly
            # matrices: full-series retention would be (n_runs, n_links,
            # 35040) ≈ 42 MB per metric per 100 runs per link, which is
            # unnecessary for the charts the user asked for.
            icm = result.ic_metrics
            import_hours_rows.append(icm.import_hours)
            export_hours_rows.append(icm.export_hours)
            import_energy_mwh_rows.append(icm.import_energy_mwh)
            export_energy_mwh_rows.append(icm.export_energy_mwh)
            total_econ_benefit_rows.append(icm.total_economic_benefit_eur)
            total_co2_benefit_rows.append(icm.total_co2_benefit_tons)

            # Monthly aggregation: sum per-qh values inside each calendar
            # month, producing (n_links, 12) matrices per run. Stacking
            # yields (n_runs, n_links, 12) after the loop.
            econ_monthly = np.zeros((n_links, 12))
            co2_monthly = np.zeros((n_links, 12))
            for m in range(1, 13):
                mask = tg.month == m
                econ_monthly[:, m - 1] = (
                    icm.economic_benefit_eur_qh[:, mask].sum(axis=1))
                co2_monthly[:, m - 1] = (
                    icm.co2_benefit_tons_qh[:, mask].sum(axis=1))
            econ_benefit_monthly_rows.append(econ_monthly)
            co2_benefit_monthly_rows.append(co2_monthly)

        # ── Consumption-based carbon intensity ────────────────────────
        # Attribute cross-border emissions to the consuming jurisdiction:
        # imports add their foreign CI × volume, exports subtract our
        # domestic marginal CI × volume. Without interconnections the
        # consumption-based figure collapses onto the territorial one,
        # which preserves backward compatibility for callers that read
        # this key unconditionally.
        # Denominator intentionally aligned with the territorial CI
        # above: in the no-link case the two metrics must coincide
        # numerically, not just conceptually. Any residual difference
        # between load.sum() and result.power.sum() (curtailment +
        # unserved) would otherwise leak into the "consumption" figure
        # even when there are no cross-border flows to attribute.
        if has_ic:
            imported_emis_tons = result.emissions_imported_tons.sum()
            # Exports carry away emissions at the domestic marginal CI.
            # export_power is p.u.·qh. Tons = pu·qh × P_BASE(GW) ×
            # 0.25(h) × CI(g/kWh) with the usual 10⁶/10⁻⁶ cancellation.
            marg_ci = result.ic_metrics.domestic_marginal_ci_g_per_kwh
            exported_emis_tons = (
                export_power * 0.25 * P_BASE * marg_ci[np.newaxis, :]
            ).sum()
            cons_emis_grams = (
                run_total_emissions - exported_emis_tons + imported_emis_tons
            ) * 1e6
        else:
            cons_emis_grams = run_total_emissions * 1e6
        ci_cons = (cons_emis_grams / total_energy_kwh
                   if total_energy_kwh > 0 else 0.0)
        carbon_intensity_consumption.append(ci_cons)

    emissions_by_tech = {k: np.array(v) for k, v in emissions_by_tech_lists.items()}

    # Per-link aggregates: stack rows or return empty arrays for uniform shape
    def _stack_or_empty(rows):
        return (np.stack(rows, axis=0) if rows
                else np.zeros((n_runs, n_links)))

    def _stack_or_empty_monthly(rows):
        return (np.stack(rows, axis=0) if rows
                else np.zeros((n_runs, n_links, 12)))

    return {
        'avg_price': np.array(avg_prices),
        'monthly_prices': np.array(monthly_avg_prices),
        'curtailment': np.array(total_curtailment),
        'avg_inertia': np.array(avg_inertia),
        'total_emissions': np.array(total_emissions),
        'carbon_intensity': np.array(carbon_intensity),
        'carbon_intensity_consumption': np.array(carbon_intensity_consumption),
        'emissions_by_tech': emissions_by_tech,
        'interconnection_names': ic_names,
        'net_import_twh': _stack_or_empty(net_import_twh_rows),
        'import_gross_twh': _stack_or_empty(import_gross_twh_rows),
        'export_gross_twh': _stack_or_empty(export_gross_twh_rows),
        'imported_emissions_tons': _stack_or_empty(imported_emissions_tons_rows),
        'foreign_price_mean': _stack_or_empty(foreign_price_mean_rows),
        'ntc_import_saturation_pct': _stack_or_empty(ntc_import_saturation_rows),
        'import_hours': _stack_or_empty(import_hours_rows),
        'export_hours': _stack_or_empty(export_hours_rows),
        'import_energy_mwh': _stack_or_empty(import_energy_mwh_rows),
        'export_energy_mwh': _stack_or_empty(export_energy_mwh_rows),
        'total_economic_benefit_eur': _stack_or_empty(total_econ_benefit_rows),
        'total_co2_benefit_tons': _stack_or_empty(total_co2_benefit_rows),
        'economic_benefit_monthly_eur':
            _stack_or_empty_monthly(econ_benefit_monthly_rows),
        'co2_benefit_monthly_tons':
            _stack_or_empty_monthly(co2_benefit_monthly_rows),
    }


def sweep_technology(base_mix: dict, tech: str,
                     penetrations_pct: np.ndarray,
                     gas_scenario: dict, coal_scenario: dict | None = None,
                     co2_scenario: dict | None = None,
                     n_runs: int = 30,
                     seed: int = RANDOM_SEED) -> list[dict]:
    """Sweep technology penetration and collect price/inertia statistics.

    For each penetration level, sets the target technology's capacity to
    ``total_system_capacity * pct / 100`` and runs a Monte Carlo simulation.

    Args:
        base_mix: Base generation mix dictionary to modify.
        tech: Technology type to sweep (e.g. ``'nuclear'``, ``'solar'``).
        penetrations_pct: Array of penetration levels in percent of total
            installed capacity.
        gas_scenario: Gas price scenario parameters.
        coal_scenario: Coal price scenario parameters. If ``None``, defaults
            to ``COAL_SCENARIOS['base']``.
        co2_scenario: CO2 price scenario parameters. If ``None``, defaults
            to ``CO2_SCENARIOS['base']``.
        n_runs: Number of MC runs per penetration level. Defaults to 30.
        seed: Base random seed. Defaults to ``RANDOM_SEED``.

    Returns:
        list[dict]: One dict per penetration level with keys:

            - ``'pct'`` (float): Penetration percentage.
            - ``'mean_price'`` (float): Mean electricity price (EUR/MWh).
            - ``'std_price'`` (float): Std dev of annual price across MC runs.
            - ``'monthly_mean'`` (np.ndarray): Monthly mean prices, shape ``(12,)``.
            - ``'mean_curtailment'`` (float): Mean total curtailment (p.u.-qh).
            - ``'mean_inertia'`` (float): Mean system inertia (seconds).
            - ``'mean_emissions'`` (float): Mean total annual CO₂ emissions (tons).
            - ``'mean_carbon_intensity'`` (float): Mean carbon intensity (gCO₂/kWh).
            - ``'mean_emissions_by_tech'`` (dict[str, float]): Mean annual
              emissions per technology (tons).
    """
    results = []
    total_capacity_gw = sum(v['capacity_gw'] for v in base_mix.values())

    for pct in penetrations_pct:
        mix = deepcopy(base_mix)
        new_cap = total_capacity_gw * pct / 100.0
        mix[tech] = deepcopy(mix.get(tech, mix['gas']))

        if tech in mix:
            mix[tech]['capacity_gw'] = new_cap

        # Nuclear defaults if absent
        if tech == 'nuclear' and 'fuel_cost_eur_mwh_th' not in mix[tech]:
            nuc_defaults = {
                'capex_per_kw': 5500, 'lifetime_years': 60, 'vom_eur_mwh': 2.5,
                'fom_eur_kw_yr': 80.0, 'efficiency': 0.33, 'emission_factor': 0.0,
                'h_inertia': 6.0, 'min_stable_pct': 0.50,
                'ramp_rate_pct_per_min': 0.03,
                'startup_cost_eur_mw': 200.0, 'fuel_cost_eur_mwh_th': 3.0,
            }
            mix[tech].update(nuc_defaults)

        # Coal defaults if absent
        if tech == 'coal' and 'efficiency' not in mix[tech]:
            coal_defaults = {
                'capex_per_kw': 1500, 'lifetime_years': 40, 'vom_eur_mwh': 4.0,
                'fom_eur_kw_yr': 35.0, 'efficiency': 0.40, 'emission_factor': 0.34,
                'h_inertia': 5.0, 'min_stable_pct': 0.45,
                'ramp_rate_pct_per_min': 0.02,
                'startup_cost_eur_mw': 80.0,
            }
            mix[tech].update(coal_defaults)

        mc = run_monte_carlo(mix, gas_scenario, coal_scenario,
                             co2_scenario=co2_scenario,
                             n_runs=n_runs, seed=seed)
        mean_ebt = {k: v.mean() for k, v in mc['emissions_by_tech'].items()}
        results.append({
            'pct': pct,
            'mean_price': mc['avg_price'].mean(),
            'std_price': mc['avg_price'].std(),
            'monthly_mean': mc['monthly_prices'].mean(axis=0),
            'mean_curtailment': mc['curtailment'].mean(),
            'mean_inertia': mc['avg_inertia'].mean(),
            'mean_emissions': mc['total_emissions'].mean(),
            'mean_carbon_intensity': mc['carbon_intensity'].mean(),
            'mean_emissions_by_tech': mean_ebt,
        })
        print(f"  {tech} {pct:.0f}%: price={results[-1]['mean_price']:.2f} EUR/MWh, "
              f"H={results[-1]['mean_inertia']:.2f}s, "
              f"CO₂={results[-1]['mean_emissions'] / 1e6:.2f} Mt, "
              f"CI={results[-1]['mean_carbon_intensity']:.0f} gCO₂/kWh")

    return results


def build_sensitivity_heatmap(base_mix: dict, tech: str,
                              gas_scenarios_sweep: dict,
                              penetrations_pct: np.ndarray,
                              coal_scenario: dict | None = None,
                              co2_scenario: dict | None = None,
                              n_runs: int = 20,
                              seed: int = RANDOM_SEED) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build 2D sensitivity data: tech penetration vs gas price scenario.

    Runs :func:`sweep_technology` for each gas scenario, producing matrices
    of price and inertia indexed by (gas_scenario, penetration_level).

    Args:
        base_mix: Base generation mix dictionary.
        tech: Technology type to sweep.
        gas_scenarios_sweep: Dict mapping scenario labels to gas price
            parameter dicts.
        penetrations_pct: Array of penetration levels in percent.
        coal_scenario: Coal price scenario parameters. If ``None``, defaults
            to ``COAL_SCENARIOS['base']``.
        co2_scenario: CO2 price scenario parameters. If ``None``, defaults
            to ``CO2_SCENARIOS['base']``.
        n_runs: MC runs per data point. Defaults to 20.
        seed: Base random seed. Defaults to ``RANDOM_SEED``.

    Returns:
        tuple: A 3-tuple of:

            - **price_matrix** (np.ndarray): Shape
              ``(n_gas_scenarios, n_penetrations)``, mean prices in EUR/MWh.
            - **inertia_matrix** (np.ndarray): Shape
              ``(n_gas_scenarios, n_penetrations)``, mean inertia in seconds.
            - **gas_labels** (list[str]): Formatted labels for each gas
              scenario row.
    """
    gas_labels = []
    price_matrix = []
    inertia_matrix = []

    for label, gas_params in gas_scenarios_sweep.items():
        print(f"\n\u2500\u2500 Gas scenario: {label} "
              f"(\u03bc={gas_params['mu']:.0f} EUR/MWh) \u2500\u2500")
        gas_labels.append(f"{label}\n(\u03bc={gas_params['mu']:.0f})")
        row_prices = []
        row_inertia = []
        results = sweep_technology(base_mix, tech, penetrations_pct,
                                   gas_params, coal_scenario,
                                   co2_scenario=co2_scenario,
                                   n_runs=n_runs, seed=seed)
        for r in results:
            row_prices.append(r['mean_price'])
            row_inertia.append(r['mean_inertia'])
        price_matrix.append(row_prices)
        inertia_matrix.append(row_inertia)

    return np.array(price_matrix), np.array(inertia_matrix), gas_labels


def build_incremental_heatmap(
    base_mix: dict,
    tech: str,
    base_penetrations_pct: np.ndarray,
    increments_pct: np.ndarray,
    gas_scenario: dict,
    coal_scenario: dict | None = None,
    co2_scenario: dict | None = None,
    n_runs: int = 20,
    seed: int = RANDOM_SEED,
) -> tuple[np.ndarray, np.ndarray]:
    """Build incremental sensitivity heatmap: marginal price impact of adding
    Δ% of a technology at different base penetration levels.

    Collects all unique penetration levels needed (base and base+delta pairs),
    runs a single :func:`sweep_technology` call to avoid redundant MC runs,
    then assembles the finite-difference matrices.

    Args:
        base_mix: Base generation mix dictionary.
        tech: Technology type to sweep (e.g. ``'nuclear'``, ``'solar'``).
        base_penetrations_pct: Array of base penetration levels in percent
            (e.g. ``[0, 5, 10, 15, 20, 25]``).
        increments_pct: Array of incremental Δ% values to test
            (e.g. ``[1, 2, 5, 10]``).
        gas_scenario: Gas price scenario parameters.
        coal_scenario: Coal price scenario parameters. If ``None``, defaults
            to ``COAL_SCENARIOS['base']``.
        co2_scenario: CO2 price scenario parameters. If ``None``, defaults
            to ``CO2_SCENARIOS['base']``.
        n_runs: Number of MC runs per penetration level. Defaults to 20.
        seed: Base random seed. Defaults to ``RANDOM_SEED``.

    Returns:
        tuple: A 2-tuple of:

            - **delta_price_matrix** (np.ndarray): Shape
              ``(len(base_penetrations_pct), len(increments_pct))``,
              price difference in EUR/MWh (price at base+delta minus price
              at base). Negative means adding the technology lowers prices.
            - **marginal_cost_matrix** (np.ndarray): Same shape,
              EUR/MWh per percentage point (delta_price / delta_pct).
    """
    # Collect all unique penetration levels needed
    all_levels = set()
    for base in base_penetrations_pct:
        all_levels.add(float(base))
        for delta in increments_pct:
            all_levels.add(float(base + delta))
    all_levels_sorted = np.array(sorted(all_levels))

    print(f"\n── Incremental heatmap for {tech}: "
          f"{len(all_levels_sorted)} unique penetration levels ──")

    # Single sweep over all unique levels
    sweep_results = sweep_technology(
        base_mix, tech, all_levels_sorted, gas_scenario,
        coal_scenario=coal_scenario, co2_scenario=co2_scenario,
        n_runs=n_runs, seed=seed,
    )

    # Build lookup: penetration % → mean price
    price_lookup = {r['pct']: r['mean_price'] for r in sweep_results}

    # Assemble matrices
    n_base = len(base_penetrations_pct)
    n_inc = len(increments_pct)
    delta_price_matrix = np.zeros((n_base, n_inc))
    marginal_cost_matrix = np.zeros((n_base, n_inc))

    for i, base in enumerate(base_penetrations_pct):
        for j, delta in enumerate(increments_pct):
            p_base = price_lookup[float(base)]
            p_target = price_lookup[float(base + delta)]
            delta_price_matrix[i, j] = p_target - p_base
            marginal_cost_matrix[i, j] = (p_target - p_base) / delta

    return delta_price_matrix, marginal_cost_matrix


def sweep_fuel_price(base_mix: dict, fuel_type: str,
                     mu_range: np.ndarray,
                     base_gas_scenario: dict,
                     base_coal_scenario: dict | None = None,
                     co2_scenario: dict | None = None,
                     n_runs: int = 20,
                     seed: int = RANDOM_SEED) -> list[dict]:
    """Sweep a single fuel's mean price (μ) and collect electricity price and
    emission statistics, keeping the energy mix fixed.

    For each μ value in ``mu_range``, builds the corresponding fuel scenario
    (preserving σ and θ from the base scenario) and runs a full Monte Carlo
    simulation. This answers the question: "given this mix, how exposed is the
    electricity price to changes in fuel cost?"

    Args:
        base_mix: Generation mix dictionary (fixed across the sweep).
        fuel_type: Which fuel to sweep. Must be ``'gas'`` or ``'coal'``.
        mu_range: Array of long-run mean fuel prices (EUR/MWh_th) to test.
        base_gas_scenario: Base gas price scenario parameters.
        base_coal_scenario: Base coal price scenario parameters. If ``None``,
            defaults to ``COAL_SCENARIOS['base']``.
        co2_scenario: CO2 price scenario parameters. If ``None``, defaults
            to ``CO2_SCENARIOS['base']``.
        n_runs: Number of MC runs per data point. Defaults to 20.
        seed: Base random seed. Defaults to ``RANDOM_SEED``.

    Returns:
        list[dict]: One dict per μ value with keys:

            - ``'fuel_mu'`` (float): Fuel mean price tested (EUR/MWh_th).
            - ``'mean_price'`` (float): Mean electricity price (EUR/MWh).
            - ``'std_price'`` (float): Std dev of annual price across MC runs.
            - ``'mean_emissions'`` (float): Mean total annual CO₂ (tons).
            - ``'mean_carbon_intensity'`` (float): Mean CI (gCO₂/kWh).
            - ``'mean_emissions_by_tech'`` (dict[str, float]): Per-technology
              mean annual emissions (tons).

    Raises:
        ValueError: If ``fuel_type`` is not ``'gas'`` or ``'coal'``.
    """
    if fuel_type not in ('gas', 'coal'):
        raise ValueError(f"fuel_type must be 'gas' or 'coal', got '{fuel_type}'")

    coal_params = base_coal_scenario or COAL_SCENARIOS['base']

    # Determine base scenario for the swept fuel (to preserve sigma/theta)
    if fuel_type == 'gas':
        base_fuel = base_gas_scenario
    else:
        base_fuel = coal_params

    results = []
    for mu in mu_range:
        # Build the swept scenario with the new mu
        swept = {'mu': float(mu), 'sigma': base_fuel['sigma'],
                 'theta': base_fuel['theta']}

        if fuel_type == 'gas':
            gas_sc = swept
            coal_sc = coal_params
        else:
            gas_sc = base_gas_scenario
            coal_sc = swept

        mc = run_monte_carlo(base_mix, gas_sc, coal_sc,
                             co2_scenario=co2_scenario,
                             n_runs=n_runs, seed=seed)
        mean_ebt = {k: v.mean() for k, v in mc['emissions_by_tech'].items()}
        results.append({
            'fuel_mu': float(mu),
            'mean_price': mc['avg_price'].mean(),
            'std_price': mc['avg_price'].std(),
            'mean_emissions': mc['total_emissions'].mean(),
            'mean_carbon_intensity': mc['carbon_intensity'].mean(),
            'mean_emissions_by_tech': mean_ebt,
        })
        print(f"  {fuel_type} μ={mu:.0f}: elec_price={results[-1]['mean_price']:.2f} EUR/MWh, "
              f"CI={results[-1]['mean_carbon_intensity']:.0f} gCO₂/kWh")

    return results


def sweep_fuel_prices_2d(base_mix: dict,
                         gas_mu_range: np.ndarray,
                         coal_mu_range: np.ndarray,
                         base_gas_scenario: dict,
                         base_coal_scenario: dict | None = None,
                         co2_scenario: dict | None = None,
                         n_runs: int = 20,
                         seed: int = RANDOM_SEED) -> tuple[np.ndarray, np.ndarray]:
    """Sweep gas and coal mean prices simultaneously and collect electricity
    price and carbon intensity in 2D grids.

    For each (gas_μ, coal_μ) combination, runs a Monte Carlo simulation with
    the energy mix fixed. Produces heatmaps that reveal fuel-switching dynamics:
    regions where coal is cheaper than gas vs. vice versa.

    Args:
        base_mix: Generation mix dictionary (fixed across the sweep).
        gas_mu_range: Array of gas mean prices (EUR/MWh_th) to test.
        coal_mu_range: Array of coal mean prices (EUR/MWh_th) to test.
        base_gas_scenario: Base gas price scenario (used for σ, θ).
        base_coal_scenario: Base coal price scenario (used for σ, θ).
            If ``None``, defaults to ``COAL_SCENARIOS['base']``.
        co2_scenario: CO2 price scenario parameters. If ``None``, defaults
            to ``CO2_SCENARIOS['base']``.
        n_runs: Number of MC runs per data point. Defaults to 20.
        seed: Base random seed. Defaults to ``RANDOM_SEED``.

    Returns:
        tuple: A 2-tuple of:

            - **price_matrix** (np.ndarray): Shape
              ``(len(gas_mu_range), len(coal_mu_range))``, mean electricity
              price in EUR/MWh. Rows = gas μ, columns = coal μ.
            - **ci_matrix** (np.ndarray): Same shape, mean carbon intensity
              in gCO₂/kWh.
    """
    coal_params = base_coal_scenario or COAL_SCENARIOS['base']
    n_gas = len(gas_mu_range)
    n_coal = len(coal_mu_range)
    price_matrix = np.zeros((n_gas, n_coal))
    ci_matrix = np.zeros((n_gas, n_coal))

    for i, gas_mu in enumerate(gas_mu_range):
        gas_sc = {'mu': float(gas_mu), 'sigma': base_gas_scenario['sigma'],
                  'theta': base_gas_scenario['theta']}
        for j, coal_mu in enumerate(coal_mu_range):
            coal_sc = {'mu': float(coal_mu), 'sigma': coal_params['sigma'],
                       'theta': coal_params['theta']}

            mc = run_monte_carlo(base_mix, gas_sc, coal_sc,
                                 co2_scenario=co2_scenario,
                                 n_runs=n_runs, seed=seed)
            price_matrix[i, j] = mc['avg_price'].mean()
            ci_matrix[i, j] = mc['carbon_intensity'].mean()
            print(f"  gas_μ={gas_mu:.0f}, coal_μ={coal_mu:.0f}: "
                  f"price={price_matrix[i, j]:.2f} EUR/MWh, "
                  f"CI={ci_matrix[i, j]:.0f} gCO₂/kWh")

    return price_matrix, ci_matrix
