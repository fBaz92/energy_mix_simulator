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
    QUARTERS_PER_YEAR, N_MC_RUNS, RANDOM_SEED, P_PEAK_GW,
    ITALIAN_MIX, GAS_SCENARIOS, QUARTERS_PER_DAY,
)
from energy_sim.models import TimeGrid, LoadProfile
from energy_sim.generators import CarbonPriceModel, build_generators
from energy_sim.dispatch import dispatch_year


def run_monte_carlo(mix_config: dict, gas_scenario: dict,
                    n_runs: int = N_MC_RUNS,
                    load_noise: float = 0.02,
                    seed: int = RANDOM_SEED) -> dict:
    """Run a Monte Carlo simulation of the electricity market.

    For each run: builds fresh generators (new stochastic fuel price paths),
    generates a load profile with noise, dispatches via merit order, and
    collects price/curtailment/inertia statistics.

    Args:
        mix_config: Generation mix dictionary (see
            :data:`~energy_sim.config.ITALIAN_MIX`).
        gas_scenario: Gas price scenario parameters (keys: ``mu``, ``sigma``,
            ``theta``).
        n_runs: Number of Monte Carlo runs. Defaults to ``N_MC_RUNS``.
        load_noise: Standard deviation of multiplicative Gaussian load noise.
            Defaults to 0.02 (2%).
        seed: Base random seed. Run *i* uses ``seed + i``.
            Defaults to ``RANDOM_SEED``.

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
              per run, shape ``(n_runs,)``, in tons.
            - ``'carbon_intensity'`` (np.ndarray): Average carbon intensity
              per run, shape ``(n_runs,)``, in gCO₂/kWh.
            - ``'emissions_by_tech'`` (dict[str, np.ndarray]): Per-technology
              annual emissions, each shape ``(n_runs,)``, in tons.
    """
    tg = TimeGrid()
    lp = LoadProfile(tg)
    co2 = CarbonPriceModel()

    avg_prices = []
    monthly_avg_prices = []
    total_curtailment = []
    avg_inertia = []
    total_emissions = []
    carbon_intensity = []
    emissions_by_tech_lists: dict[str, list[float]] = {}

    for run in range(n_runs):
        rng = np.random.default_rng(seed + run)

        gens = build_generators(mix_config, gas_scenario)
        for g in gens:
            g.prepare_run(tg, rng, co2)

        load = lp.generate(rng, noise_sigma=load_noise)
        result = dispatch_year(gens, load)

        avg_prices.append(result.marginal_price.mean())
        total_curtailment.append(result.curtailment.sum())
        avg_inertia.append(result.h_system.mean())

        monthly = np.zeros(12)
        for m in range(1, 13):
            mask = tg.month == m
            monthly[m - 1] = result.marginal_price[mask].mean()
        monthly_avg_prices.append(monthly)

        # CO₂ emissions aggregation
        run_total_emissions = result.emissions.sum()
        total_emissions.append(run_total_emissions)

        # Carbon intensity: gCO₂/kWh
        # Total energy served = sum(power_pu) * P_BASE(GW) * 0.25(h) * 1e6(kW/GW)
        total_energy_kwh = result.power.sum() * P_PEAK_GW * 0.25 * 1e6
        # Total emissions in grams = tons * 1e6
        ci = (run_total_emissions * 1e6 / total_energy_kwh
              if total_energy_kwh > 0 else 0.0)
        carbon_intensity.append(ci)

        # Per-technology emissions
        for i, name in enumerate(result.gen_names):
            if name not in emissions_by_tech_lists:
                emissions_by_tech_lists[name] = []
            emissions_by_tech_lists[name].append(result.emissions[i].sum())

    emissions_by_tech = {k: np.array(v) for k, v in emissions_by_tech_lists.items()}

    return {
        'avg_price': np.array(avg_prices),
        'monthly_prices': np.array(monthly_avg_prices),
        'curtailment': np.array(total_curtailment),
        'avg_inertia': np.array(avg_inertia),
        'total_emissions': np.array(total_emissions),
        'carbon_intensity': np.array(carbon_intensity),
        'emissions_by_tech': emissions_by_tech,
    }


def sweep_technology(base_mix: dict, tech: str,
                     penetrations_pct: np.ndarray,
                     gas_scenario: dict, n_runs: int = 30,
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

        mc = run_monte_carlo(mix, gas_scenario, n_runs=n_runs, seed=seed)
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
                                   gas_params, n_runs, seed)
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
