"""
Visualization functions for simulation results.

All plotting functions accept pre-computed data and save figures to disk.
Uses the ``Agg`` backend for headless rendering.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from energy_sim.config import QUARTERS_PER_DAY, P_PEAK_GW, N_MC_RUNS
from energy_sim.generators import Generator, CarbonPriceModel
from energy_sim.models import TimeGrid
from energy_sim.dispatch import dispatch_year


def plot_heatmap(price_matrix: np.ndarray, penetrations_pct: np.ndarray,
                 gas_labels: list[str], tech_name: str,
                 out_path: str) -> None:
    """Plot a heatmap of price sensitivity: tech penetration vs gas scenario.

    X-axis is technology penetration, Y-axis is gas price scenario. Cell color
    shows the percentage change in electricity price relative to the 0%
    penetration column. Cell annotations show both the delta and absolute price.

    Args:
        price_matrix: Mean price matrix of shape
            ``(n_gas_scenarios, n_penetrations)`` in EUR/MWh.
        penetrations_pct: Array of penetration levels in percent.
        gas_labels: List of gas scenario labels (one per row).
        tech_name: Technology name for axis labels and title.
        out_path: File path to save the figure (PNG).
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    base_prices = price_matrix[:, 0:1]
    delta_pct = (price_matrix - base_prices) / base_prices * 100

    im = ax.imshow(delta_pct, aspect='auto', cmap='RdYlGn_r',
                   origin='lower',
                   extent=[penetrations_pct[0], penetrations_pct[-1],
                           -0.5, len(gas_labels) - 0.5])

    ax.set_xticks(penetrations_pct)
    ax.set_xticklabels([f'{p:.0f}%' for p in penetrations_pct])
    ax.set_yticks(range(len(gas_labels)))
    ax.set_yticklabels(gas_labels)
    ax.set_xlabel(f'{tech_name} penetration (% of installed capacity)')
    ax.set_ylabel('Gas price scenario')
    ax.set_title(f'Electricity price sensitivity to {tech_name} penetration\n'
                 f'(\u0394% from base mix, {N_MC_RUNS}-run Monte Carlo)')

    for i in range(len(gas_labels)):
        for j in range(len(penetrations_pct)):
            val = delta_pct[i, j]
            price = price_matrix[i, j]
            ax.text(penetrations_pct[j], i, f'{val:+.1f}%\n({price:.0f}\u20ac)',
                    ha='center', va='center', fontsize=7,
                    color='white' if abs(val) > 10 else 'black')

    plt.colorbar(im, ax=ax, label='\u0394% electricity price vs. no ' + tech_name)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_sensitivity_curve(results_list: list[dict], tech_name: str,
                           out_path: str) -> None:
    """Plot price and inertia vs technology penetration.

    Dual-axis line plot: left axis shows mean price with +/- 1 sigma band,
    right axis shows mean system inertia with the H_min threshold line.

    Args:
        results_list: List of dicts from :func:`~energy_sim.simulation.sweep_technology`,
            each with keys ``'pct'``, ``'mean_price'``, ``'std_price'``,
            ``'mean_inertia'``.
        tech_name: Technology name for labels and title.
        out_path: File path to save the figure (PNG).
    """
    fig, ax1 = plt.subplots(figsize=(10, 5))

    pcts = [r['pct'] for r in results_list]
    means = [r['mean_price'] for r in results_list]
    stds = [r['std_price'] for r in results_list]
    inertias = [r['mean_inertia'] for r in results_list]

    ax1.fill_between(pcts,
                     np.array(means) - np.array(stds),
                     np.array(means) + np.array(stds),
                     alpha=0.3, color='steelblue')
    ax1.plot(pcts, means, 'o-', color='steelblue', label='Mean price \u00b1 \u03c3')
    ax1.set_xlabel(f'{tech_name} penetration (%)')
    ax1.set_ylabel('Avg. electricity price (EUR/MWh)', color='steelblue')
    ax1.tick_params(axis='y', labelcolor='steelblue')

    ax2 = ax1.twinx()
    ax2.plot(pcts, inertias, 's--', color='firebrick', label='System inertia H')
    ax2.set_ylabel('Mean system inertia H (s)', color='firebrick')
    ax2.tick_params(axis='y', labelcolor='firebrick')
    ax2.axhline(y=3.5, color='firebrick', linestyle=':', alpha=0.5, label='H_min')

    ax1.set_title(f'Impact of {tech_name} on electricity price and system inertia\n'
                  f'(Italian mix, gas base scenario, Monte Carlo)')
    fig.legend(loc='upper right', bbox_to_anchor=(0.88, 0.88))
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_monthly_heatmap(results_list: list[dict], tech_name: str,
                         out_path: str) -> None:
    """Plot monthly price sensitivity heatmap.

    X-axis is month, Y-axis is penetration level. Cell color shows the
    percentage change in monthly price relative to the 0% penetration row.

    Args:
        results_list: List of dicts from :func:`~energy_sim.simulation.sweep_technology`,
            each with keys ``'pct'`` and ``'monthly_mean'``.
        tech_name: Technology name for labels and title.
        out_path: File path to save the figure (PNG).
    """
    pcts = [r['pct'] for r in results_list]
    monthly = np.array([r['monthly_mean'] for r in results_list])

    base_monthly = monthly[0:1, :]
    delta = (monthly - base_monthly) / base_monthly * 100

    fig, ax = plt.subplots(figsize=(12, 5))
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    im = ax.imshow(delta, aspect='auto', cmap='RdYlGn_r', origin='lower')
    ax.set_xticks(range(12))
    ax.set_xticklabels(months)
    ax.set_yticks(range(len(pcts)))
    ax.set_yticklabels([f'{p:.0f}%' for p in pcts])
    ax.set_xlabel('Month')
    ax.set_ylabel(f'{tech_name} penetration (%)')
    ax.set_title(f'Monthly electricity price sensitivity to {tech_name}\n'
                 f'(\u0394% from 0% penetration)')

    for i in range(len(pcts)):
        for j in range(12):
            ax.text(j, i, f'{delta[i, j]:+.1f}%',
                    ha='center', va='center', fontsize=6,
                    color='white' if abs(delta[i, j]) > 8 else 'black')

    plt.colorbar(im, ax=ax, label='\u0394% price')
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_incremental_heatmap(
    delta_price_matrix: np.ndarray,
    base_penetrations_pct: np.ndarray,
    increments_pct: np.ndarray,
    tech_name: str,
    out_path: str,
) -> None:
    """Plot an incremental sensitivity heatmap showing the price impact of
    adding Δ% of a technology at various base penetration levels.

    X-axis is the base penetration level, Y-axis is the incremental Δ%.
    Cell color shows the price change in EUR/MWh (green = price decrease,
    red = price increase). Annotations show the numeric delta.

    Args:
        delta_price_matrix: Price difference matrix of shape
            ``(len(base_penetrations_pct), len(increments_pct))`` in EUR/MWh.
        base_penetrations_pct: Array of base penetration levels in percent.
        increments_pct: Array of incremental Δ% values.
        tech_name: Technology name for labels and title.
        out_path: File path to save the figure (PNG).
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    # Transpose so X=base penetration (columns), Y=increment (rows)
    data = delta_price_matrix.T

    im = ax.imshow(data, aspect='auto', cmap='RdYlGn_r', origin='lower')

    ax.set_xticks(range(len(base_penetrations_pct)))
    ax.set_xticklabels([f'{p:.0f}%' for p in base_penetrations_pct])
    ax.set_yticks(range(len(increments_pct)))
    ax.set_yticklabels([f'+{d:.0f}%' for d in increments_pct])
    ax.set_xlabel(f'{tech_name} base penetration (% of installed capacity)')
    ax.set_ylabel(f'Incremental \u0394%')
    ax.set_title(f'Incremental price impact of adding \u0394% {tech_name}\n'
                 f'(EUR/MWh change, Monte Carlo)')

    for i in range(len(increments_pct)):
        for j in range(len(base_penetrations_pct)):
            val = data[i, j]
            ax.text(j, i, f'{val:+.1f}',
                    ha='center', va='center', fontsize=8,
                    color='white' if abs(val) > abs(data).max() * 0.5 else 'black')

    plt.colorbar(im, ax=ax, label='\u0394 price (EUR/MWh)')
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_carbon_intensity_curve(results_list: list[dict], tech_name: str,
                                out_path: str) -> None:
    """Plot carbon intensity and total emissions vs technology penetration.

    Dual-axis line plot: left axis shows mean carbon intensity (gCO₂/kWh),
    right axis shows total annual emissions (Mt CO₂).

    Args:
        results_list: List of dicts from :func:`~energy_sim.simulation.sweep_technology`,
            each with keys ``'pct'``, ``'mean_carbon_intensity'``,
            ``'mean_emissions'``.
        tech_name: Technology name for labels and title.
        out_path: File path to save the figure (PNG).
    """
    fig, ax1 = plt.subplots(figsize=(10, 5))

    pcts = [r['pct'] for r in results_list]
    ci = [r['mean_carbon_intensity'] for r in results_list]
    emissions_mt = [r['mean_emissions'] / 1e6 for r in results_list]

    ax1.plot(pcts, ci, 'o-', color='darkgreen', label='Carbon intensity')
    ax1.set_xlabel(f'{tech_name} penetration (%)')
    ax1.set_ylabel('Carbon intensity (gCO₂/kWh)', color='darkgreen')
    ax1.tick_params(axis='y', labelcolor='darkgreen')

    ax2 = ax1.twinx()
    ax2.plot(pcts, emissions_mt, 's--', color='sienna', label='Total emissions')
    ax2.set_ylabel('Total annual emissions (Mt CO₂)', color='sienna')
    ax2.tick_params(axis='y', labelcolor='sienna')

    ax1.set_title(f'CO₂ impact of {tech_name} penetration\n'
                  f'(Italian mix, Monte Carlo)')
    fig.legend(loc='upper right', bbox_to_anchor=(0.88, 0.88))
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_emissions_breakdown(results_list: list[dict], tech_name: str,
                             out_path: str) -> None:
    """Plot stacked bar chart of CO₂ emissions by technology across penetrations.

    Each bar represents a penetration level; segments show each technology's
    contribution to total annual emissions.

    Args:
        results_list: List of dicts from :func:`~energy_sim.simulation.sweep_technology`,
            each with keys ``'pct'`` and ``'mean_emissions_by_tech'``.
        tech_name: Technology name for axis labels and title.
        out_path: File path to save the figure (PNG).
    """
    fig, ax = plt.subplots(figsize=(10, 5))

    pcts = [r['pct'] for r in results_list]
    all_techs = set()
    for r in results_list:
        all_techs.update(r['mean_emissions_by_tech'].keys())
    # Only keep techs with non-zero emissions
    techs = sorted(t for t in all_techs
                   if any(r['mean_emissions_by_tech'].get(t, 0) > 0
                          for r in results_list))

    colors = {
        'gas': '#FF5722',
        'coal': '#795548',
        'nuclear': '#9C27B0',
        'hydro_mustrun': '#2196F3',
        'solar': '#FFC107',
        'wind': '#4CAF50',
    }

    bottom = np.zeros(len(pcts))
    x = np.arange(len(pcts))
    for tech in techs:
        vals = np.array([r['mean_emissions_by_tech'].get(tech, 0) / 1e6
                         for r in results_list])
        ax.bar(x, vals, bottom=bottom, label=tech,
               color=colors.get(tech, '#999'), alpha=0.85)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels([f'{p:.0f}%' for p in pcts])
    ax.set_xlabel(f'{tech_name} penetration (% of installed capacity)')
    ax.set_ylabel('Annual CO₂ emissions (Mt)')
    ax.set_title(f'CO₂ emissions breakdown by technology\n'
                 f'(varying {tech_name} penetration)')
    ax.legend(loc='upper right')
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_fuel_price_sensitivity(results_list: list[dict], fuel_name: str,
                                out_path: str) -> None:
    """Plot electricity price and carbon intensity vs fuel mean price.

    Dual-axis line plot: left axis shows mean electricity price with ±1σ band,
    right axis shows mean carbon intensity (gCO₂/kWh).

    Args:
        results_list: List of dicts from
            :func:`~energy_sim.simulation.sweep_fuel_price`, each with keys
            ``'fuel_mu'``, ``'mean_price'``, ``'std_price'``,
            ``'mean_carbon_intensity'``.
        fuel_name: Fuel name for labels and title (e.g. ``'Gas'``, ``'Coal'``).
        out_path: File path to save the figure (PNG).
    """
    fig, ax1 = plt.subplots(figsize=(10, 5))

    mus = [r['fuel_mu'] for r in results_list]
    means = [r['mean_price'] for r in results_list]
    stds = [r['std_price'] for r in results_list]
    ci = [r['mean_carbon_intensity'] for r in results_list]

    ax1.fill_between(mus,
                     np.array(means) - np.array(stds),
                     np.array(means) + np.array(stds),
                     alpha=0.3, color='steelblue')
    ax1.plot(mus, means, 'o-', color='steelblue', label='Elec. price ± σ')
    ax1.set_xlabel(f'{fuel_name} fuel price μ (EUR/MWh_th)')
    ax1.set_ylabel('Electricity price (EUR/MWh)', color='steelblue')
    ax1.tick_params(axis='y', labelcolor='steelblue')

    ax2 = ax1.twinx()
    ax2.plot(mus, ci, 's--', color='darkgreen', label='Carbon intensity')
    ax2.set_ylabel('Carbon intensity (gCO₂/kWh)', color='darkgreen')
    ax2.tick_params(axis='y', labelcolor='darkgreen')

    ax1.set_title(f'Electricity price sensitivity to {fuel_name} fuel price\n'
                  f'(fixed mix, Monte Carlo)')
    fig.legend(loc='upper left', bbox_to_anchor=(0.12, 0.88))
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_fuel_sensitivity_coefficient(results_list: list[dict], fuel_name: str,
                                      out_path: str) -> None:
    """Plot the sensitivity coefficient ∂(elec_price)/∂(fuel_price) vs fuel μ.

    Uses central finite differences to approximate the derivative at each
    operating point. Higher values indicate greater exposure to fuel price
    shocks.

    Args:
        results_list: List of dicts from
            :func:`~energy_sim.simulation.sweep_fuel_price` (must have ≥2
            points), each with keys ``'fuel_mu'`` and ``'mean_price'``.
        fuel_name: Fuel name for labels and title.
        out_path: File path to save the figure (PNG).
    """
    mus = np.array([r['fuel_mu'] for r in results_list])
    prices = np.array([r['mean_price'] for r in results_list])

    # Central differences (forward/backward at endpoints)
    coeffs = np.gradient(prices, mus)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(mus, coeffs, 'o-', color='crimson', linewidth=2)
    ax.axhline(y=0, color='grey', linestyle=':', alpha=0.5)
    ax.set_xlabel(f'{fuel_name} fuel price μ (EUR/MWh_th)')
    ax.set_ylabel('∂(elec. price) / ∂(fuel price)')
    ax.set_title(f'Fuel price sensitivity coefficient — {fuel_name}\n'
                 f'(higher = more exposed to price shocks)')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_fuel_price_heatmap_2d(price_matrix: np.ndarray,
                               gas_mu_range: np.ndarray,
                               coal_mu_range: np.ndarray,
                               out_path: str) -> None:
    """Plot a 2D heatmap of electricity price vs (gas μ, coal μ).

    Rows are gas mean prices, columns are coal mean prices. Cell annotations
    show the electricity price. Reveals fuel-switching dynamics: at high gas
    prices the system dispatches more coal (and vice versa).

    Args:
        price_matrix: Mean electricity price matrix of shape
            ``(len(gas_mu_range), len(coal_mu_range))`` in EUR/MWh.
        gas_mu_range: Array of gas mean prices (EUR/MWh_th).
        coal_mu_range: Array of coal mean prices (EUR/MWh_th).
        out_path: File path to save the figure (PNG).
    """
    fig, ax = plt.subplots(figsize=(10, 7))

    im = ax.imshow(price_matrix, aspect='auto', cmap='YlOrRd',
                   origin='lower',
                   extent=[coal_mu_range[0], coal_mu_range[-1],
                           gas_mu_range[0], gas_mu_range[-1]])

    ax.set_xlabel('Coal fuel price μ (EUR/MWh_th)')
    ax.set_ylabel('Gas fuel price μ (EUR/MWh_th)')
    ax.set_title('Electricity price vs fuel prices\n'
                 '(fixed mix, Monte Carlo)')

    # Annotate cells
    for i in range(len(gas_mu_range)):
        for j in range(len(coal_mu_range)):
            val = price_matrix[i, j]
            # Map indices to data coordinates
            x = coal_mu_range[j]
            y = gas_mu_range[i]
            ax.text(x, y, f'{val:.0f}',
                    ha='center', va='center', fontsize=8,
                    color='white' if val > price_matrix.mean() else 'black')

    plt.colorbar(im, ax=ax, label='Electricity price (EUR/MWh)')
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_dispatch_day(generators: list[Generator], time_grid: TimeGrid,
                      load: np.ndarray, day_of_year: int,
                      out_path: str, title_extra: str = "") -> None:
    """Plot a stacked-area dispatch chart for a single day.

    Shows each generator's output stacked as colored areas, with the load
    curve overlaid as a black line.

    Args:
        generators: List of Generator objects with ``prepare_run()`` already
            called.
        time_grid: Temporal backbone for the simulated year.
        load: Full-year load profile array of shape ``(35040,)`` in per-unit.
        day_of_year: Day index (0-364) to plot.
        out_path: File path to save the figure (PNG).
        title_extra: Optional string appended to the plot title.
    """
    start = day_of_year * QUARTERS_PER_DAY
    end = start + QUARTERS_PER_DAY
    hours = np.linspace(0, 24, QUARTERS_PER_DAY, endpoint=False)

    co2 = CarbonPriceModel()
    rng = np.random.default_rng(42)
    for g in generators:
        g.prepare_run(time_grid, rng, co2)

    result = dispatch_year(generators, load)

    fig, ax = plt.subplots(figsize=(12, 5))
    colors = {
        'hydro_mustrun': '#2196F3',
        'nuclear': '#9C27B0',
        'solar': '#FFC107',
        'wind': '#4CAF50',
        'gas': '#FF5722',
    }

    bottom = np.zeros(QUARTERS_PER_DAY)
    for i, g in enumerate(generators):
        p = result.power[i, start:end] * P_PEAK_GW  # Convert to GW
        ax.fill_between(hours, bottom, bottom + p,
                        label=g.name, color=colors.get(g.gen_type, '#999'),
                        alpha=0.8)
        bottom += p

    ax.plot(hours, load[start:end] * P_PEAK_GW, 'k-', lw=2, label='Load')
    ax.set_xlabel('Hour')
    ax.set_ylabel('Power (GW)')
    ax.set_title(f'Dispatch \u2014 Day {day_of_year} {title_extra}')
    ax.legend(loc='upper left')
    ax.set_xlim(0, 24)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


# ── Interconnection visualizations ──────────────────────────────────────


def plot_interconnection_flows_summary(mc_results: dict,
                                        out_path: str) -> None:
    """Summary bar chart of yearly cross-border flows per interconnection.

    Side-by-side bars per link show mean gross import, gross export and net
    import (positive = into domestic system) across the MC runs, with the
    standard deviation as error bar on the net flow. Also overlays the mean
    foreign price and the mean NTC saturation percentage on a secondary axis,
    which together explain *why* each border imports/exports at a given level.

    Args:
        mc_results: Output of :func:`~energy_sim.simulation.run_monte_carlo`
            when interconnections are active. Must contain the keys
            ``'interconnection_names'``, ``'net_import_twh'``,
            ``'import_gross_twh'``, ``'export_gross_twh'``,
            ``'foreign_price_mean'``, ``'ntc_import_saturation_pct'``.
        out_path: File path to save the figure (PNG).
    """
    names = mc_results['interconnection_names']
    if not names:
        print(f"No interconnections — skipping {out_path}")
        return

    n = len(names)
    x = np.arange(n)
    width = 0.27

    imp = mc_results['import_gross_twh'].mean(axis=0)
    exp = mc_results['export_gross_twh'].mean(axis=0)
    net = mc_results['net_import_twh'].mean(axis=0)
    net_std = mc_results['net_import_twh'].std(axis=0)
    fprice = mc_results['foreign_price_mean'].mean(axis=0)
    sat = mc_results['ntc_import_saturation_pct'].mean(axis=0)

    fig, ax1 = plt.subplots(figsize=(12, 5.5))

    ax1.bar(x - width, imp, width, label='Gross import', color='#2E7D32')
    ax1.bar(x, exp, width, label='Gross export', color='#C62828')
    ax1.bar(x + width, net, width, yerr=net_std, label='Net import \u00b1 \u03c3',
            color='#1565C0', capsize=3)
    ax1.axhline(0, color='black', lw=0.6)
    ax1.set_xticks(x)
    ax1.set_xticklabels(names)
    ax1.set_ylabel('Energy flow (TWh/yr)')
    ax1.legend(loc='upper left')
    ax1.grid(axis='y', alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(x, fprice, 'D--', color='#F57F17', label='Mean foreign price (\u20ac/MWh)')
    ax2.plot(x, sat, 's:', color='#6A1B9A', label='NTC import saturation (%)')
    ax2.set_ylabel('Foreign price (\u20ac/MWh) / NTC saturation (%)')
    ax2.legend(loc='upper right')

    ax1.set_title('Cross-border flows summary (Monte Carlo averages)')
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_flow_duration_curves(result, out_path: str) -> None:
    """Flow-duration curves per interconnection for a single dispatched year.

    For each link, sorts its net-import path (TWh-rate) in descending order
    and plots it against the percentile of time. The area above zero is
    energy imported; the area below is energy exported. Useful to see the
    asymmetry of a link (e.g. a border that imports most of the time with a
    small occasional export tail).

    Args:
        result: A :class:`~energy_sim.dispatch.DispatchResult` produced with
            non-empty ``interconnection_realizations``. The function reads
            :attr:`net_import_pu` and :attr:`interconnection_names`.
        out_path: File path to save the figure (PNG).
    """
    if result.net_import_pu.size == 0:
        print(f"No interconnections in DispatchResult — skipping {out_path}")
        return

    n_links, T = result.net_import_pu.shape
    # Convert p.u. to GW for readability
    flows_gw = result.net_import_pu * P_PEAK_GW
    pct = np.linspace(0, 100, T)

    fig, ax = plt.subplots(figsize=(11, 5))
    for i, name in enumerate(result.interconnection_names):
        sorted_flow = np.sort(flows_gw[i])[::-1]
        ax.plot(pct, sorted_flow, label=name, lw=1.3)

    ax.axhline(0, color='black', lw=0.6, alpha=0.7)
    ax.fill_between([0, 100], 0, ax.get_ylim()[1], color='#E8F5E9',
                    alpha=0.25, zorder=0)
    ax.fill_between([0, 100], ax.get_ylim()[0], 0, color='#FFEBEE',
                    alpha=0.25, zorder=0)
    ax.text(50, ax.get_ylim()[1] * 0.85, 'Import',
            ha='center', color='#2E7D32', fontsize=10)
    ax.text(50, ax.get_ylim()[0] * 0.85, 'Export',
            ha='center', color='#C62828', fontsize=10)

    ax.set_xlabel('Share of year (%)')
    ax.set_ylabel('Net import (GW, + = into domestic system)')
    ax.set_title('Flow-duration curves per interconnection (single year)')
    ax.legend(loc='upper right')
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_price_convergence(result, out_path: str,
                            n_points: int = 3000) -> None:
    """Scatter of domestic marginal price vs foreign price, per interconnection.

    For each link, plots the domestic price against its foreign price at the
    same timestep, overlaid with the no-arbitrage dead-band
    ``[foreign - τ, foreign + τ]``: above the upper line imports are
    profitable, below the lower line exports are profitable, and inside the
    band the dispatch is indifferent to the border. A sample of ``n_points``
    timesteps is shown per link to keep the figure readable.

    Args:
        result: A :class:`~energy_sim.dispatch.DispatchResult` produced with
            non-empty ``interconnection_realizations``. The function reads
            :attr:`marginal_price`, :attr:`foreign_prices`, and
            :attr:`interconnection_names`.
        out_path: File path to save the figure (PNG).
        n_points: Random subsample of timesteps to plot per link.
    """
    if result.foreign_prices.size == 0:
        print(f"No interconnections in DispatchResult — skipping {out_path}")
        return

    n_links, T = result.foreign_prices.shape
    rng = np.random.default_rng(0)
    idx = rng.choice(T, size=min(n_points, T), replace=False)

    n_cols = min(3, n_links)
    n_rows = int(np.ceil(n_links / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows),
                             squeeze=False)

    dom = result.marginal_price[idx]
    for i, name in enumerate(result.interconnection_names):
        ax = axes[i // n_cols][i % n_cols]
        foreign = result.foreign_prices[i, idx]
        ax.scatter(foreign, dom, s=6, alpha=0.35, color='#1565C0')

        lo, hi = float(np.min(foreign)), float(np.max(foreign))
        xs = np.linspace(lo, hi, 100)
        ax.plot(xs, xs, 'k-', lw=0.8, alpha=0.6, label='y = x')
        # Dead-band τ is NOT read from result directly (foreign ± τ) — we
        # approximate it from the typical transport cost via the spread of
        # the no-flow zone observed in the scatter. Safer: request it from
        # the caller if a precise line is needed. For now plot a light
        # reference band at ±5 EUR/MWh.
        ax.fill_between(xs, xs - 5, xs + 5, color='grey', alpha=0.15,
                        label='approx. \u00b15 \u20ac/MWh band')

        ax.set_title(name)
        ax.set_xlabel('Foreign price (\u20ac/MWh)')
        ax.set_ylabel('Domestic marginal price (\u20ac/MWh)')
        ax.grid(alpha=0.3)
        if i == 0:
            ax.legend(loc='upper left', fontsize=8)

    # Hide any unused subplot cells
    for j in range(n_links, n_rows * n_cols):
        axes[j // n_cols][j % n_cols].axis('off')

    fig.suptitle('Price convergence: domestic vs foreign per link', y=1.02)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_path}")


def plot_dispatch_with_imports(generators: list,
                                result,
                                load: np.ndarray,
                                day_of_year: int,
                                out_path: str,
                                title_extra: str = '') -> None:
    """Stacked dispatch plot for one day, including imports as a separate band.

    Variant of :func:`plot_dispatch_day` that accepts a pre-computed
    :class:`~energy_sim.dispatch.DispatchResult` (so that imports and
    exports are included) and draws an explicit ``import`` band on top of
    the domestic stack. A signed export trace is shown below the zero line
    to make the balance visible at a glance.

    Args:
        generators: Domestic generators (rows ``0..n_domestic-1`` of
            ``result.power``).
        result: :class:`DispatchResult` produced for the same ``generators``
            and ``load``, possibly with interconnections. Import rows are
            detected by ``gen_type == 'import'``.
        load: Full-year load array (p.u.), shape ``(T,)``.
        day_of_year: Day to plot (1-365).
        out_path: File path to save the figure (PNG).
        title_extra: Optional suffix for the chart title.
    """
    start = (day_of_year - 1) * QUARTERS_PER_DAY
    end = start + QUARTERS_PER_DAY
    hours = np.linspace(0, 24, QUARTERS_PER_DAY)

    fig, ax = plt.subplots(figsize=(12, 5.5))
    colors = {
        'hydro_mustrun': '#2196F3',
        'nuclear': '#9C27B0',
        'solar': '#FFC107',
        'wind': '#4CAF50',
        'gas': '#FF5722',
        'coal': '#4E342E',
        'import': '#00838F',
    }

    # Domestic stack
    bottom = np.zeros(QUARTERS_PER_DAY)
    for i, g in enumerate(generators):
        p = result.power[i, start:end] * P_PEAK_GW
        ax.fill_between(hours, bottom, bottom + p,
                        label=g.name, color=colors.get(g.gen_type, '#999'),
                        alpha=0.85)
        bottom += p

    # Import stack on top (aggregate across all import rows)
    import_rows = [i for i, t in enumerate(result.gen_types) if t == 'import']
    if import_rows:
        imp_total = result.power[import_rows, start:end].sum(axis=0) * P_PEAK_GW
        ax.fill_between(hours, bottom, bottom + imp_total,
                        label='net import', color=colors['import'],
                        alpha=0.85, hatch='//')
        bottom += imp_total

    # Signed export trace below zero (from net_import_pu negative part)
    if result.net_import_pu.size > 0:
        # Total export GW per quarter hour (sum over links, negative flow)
        daily_net = result.net_import_pu[:, start:end].sum(axis=0) * P_PEAK_GW
        export_gw = np.minimum(daily_net, 0.0)
        if export_gw.min() < -1e-6:
            ax.fill_between(hours, export_gw, 0.0, color='#C62828',
                            alpha=0.4, label='export (abroad)')

    ax.plot(hours, load[start:end] * P_PEAK_GW, 'k-', lw=2, label='Load')
    ax.axhline(0, color='black', lw=0.6)
    ax.set_xlabel('Hour')
    ax.set_ylabel('Power (GW, + = supply, \u2212 = export)')
    ax.set_title(f'Dispatch with interconnections \u2014 Day {day_of_year} {title_extra}')
    ax.legend(loc='upper left', ncol=2, fontsize=8)
    ax.set_xlim(0, 24)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_import_export_hours(mc_results: dict, out_path: str) -> None:
    """Horizontal bar chart of yearly import vs export hours per link.

    For each interconnection shows two stacked horizontal bars: blue for
    hours in net-import state, red for hours in net-export state. A
    reference vertical line at 8760 h makes it immediate to read the
    utilization factor. The complementary idle share (hours with neither
    import nor export, typically dominated by NTC faults) is shown as a
    translucent grey tail.

    Args:
        mc_results: Output of :func:`~energy_sim.simulation.run_monte_carlo`.
            Requires ``'interconnection_names'``, ``'import_hours'`` and
            ``'export_hours'``.
        out_path: File path to save the figure (PNG).
    """
    names = mc_results['interconnection_names']
    if not names:
        print(f"No interconnections — skipping {out_path}")
        return

    imp_h = mc_results['import_hours'].mean(axis=0)
    exp_h = mc_results['export_hours'].mean(axis=0)
    idle_h = np.maximum(8760.0 - imp_h - exp_h, 0.0)

    y = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(10, 0.6 * len(names) + 2))
    ax.barh(y, imp_h, color='#1565C0', label='Import hours')
    ax.barh(y, exp_h, left=imp_h, color='#C62828', label='Export hours')
    ax.barh(y, idle_h, left=imp_h + exp_h,
            color='#BDBDBD', alpha=0.5, label='Idle / faulted')
    ax.axvline(8760, color='black', lw=0.5, ls='--')
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlabel('Hours per year')
    ax.set_title('Cross-border utilisation \u2014 hours in import vs export state')
    ax.legend(loc='lower right')
    ax.grid(axis='x', alpha=0.3)

    for i, (ih, eh) in enumerate(zip(imp_h, exp_h)):
        total = ih + eh
        ax.text(total + 100, i, f'{total / 8760 * 100:.0f}% used',
                va='center', fontsize=8, color='#555555')

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_energy_bars_by_country(mc_results: dict, out_path: str) -> None:
    """Grouped bar chart of yearly import and export energy per link.

    Shows gross import (positive) and gross export (negative) per link in
    TWh, with error bars representing one standard deviation across MC
    runs. The net-import point (diamond) overlays the pair, making
    visually clear whether each link is structurally importing or
    exporting.

    Args:
        mc_results: Output of :func:`~energy_sim.simulation.run_monte_carlo`.
            Requires ``'interconnection_names'``, ``'import_energy_mwh'``
            and ``'export_energy_mwh'``. Values are expected in MWh and
            converted to TWh for plotting.
        out_path: File path to save the figure (PNG).
    """
    names = mc_results['interconnection_names']
    if not names:
        print(f"No interconnections — skipping {out_path}")
        return

    imp_twh = mc_results['import_energy_mwh'] / 1e6
    exp_twh = mc_results['export_energy_mwh'] / 1e6

    imp_mean = imp_twh.mean(axis=0)
    imp_std = imp_twh.std(axis=0)
    exp_mean = exp_twh.mean(axis=0)
    exp_std = exp_twh.std(axis=0)
    net_mean = imp_mean - exp_mean

    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x, imp_mean, yerr=imp_std, color='#1565C0',
           label='Gross import', capsize=4, alpha=0.85)
    ax.bar(x, -exp_mean, yerr=exp_std, color='#C62828',
           label='Gross export', capsize=4, alpha=0.85)
    ax.plot(x, net_mean, 'D', color='black',
            markersize=8, label='Net import')
    ax.axhline(0, color='black', lw=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel('Energy (TWh/yr)')
    ax.set_title('Annual energy exchanged by interconnection '
                 '(import up, export down)')
    ax.legend(loc='upper right')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_economic_benefit_monthly(mc_results: dict, out_path: str) -> None:
    """Monthly congestion-rent economic benefit stacked by interconnection.

    Sums the per-quarter-hour economic benefits into calendar months and
    stacks them link by link, so each bar shows both the total monthly
    benefit and the contribution of each border. The annual total per
    link is reported in the legend for reference.

    Args:
        mc_results: Output of :func:`~energy_sim.simulation.run_monte_carlo`.
            Requires ``'interconnection_names'``,
            ``'economic_benefit_monthly_eur'`` (shape ``(n_runs, n_links,
            12)``) and ``'total_economic_benefit_eur'``.
        out_path: File path to save the figure (PNG).
    """
    names = mc_results['interconnection_names']
    if not names:
        print(f"No interconnections — skipping {out_path}")
        return

    monthly = mc_results['economic_benefit_monthly_eur'].mean(axis=0) / 1e6
    totals = mc_results['total_economic_benefit_eur'].mean(axis=0) / 1e6

    months = np.arange(1, 13)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    bottom = np.zeros(12)
    cmap = plt.get_cmap('tab10')
    for i, name in enumerate(names):
        ax.bar(months, monthly[i], bottom=bottom, width=0.8,
               color=cmap(i % 10),
               label=f'{name} ({totals[i]:,.0f} M\u20ac/yr)')
        bottom += monthly[i]

    ax.set_xticks(months)
    ax.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
    ax.set_ylabel('Economic benefit (M\u20ac)')
    ax.set_title('Monthly congestion-rent economic benefit by interconnection')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_co2_benefit_monthly(mc_results: dict, out_path: str) -> None:
    """Monthly CO\u2082 benefit (signed) per interconnection as grouped bars.

    Groups (rather than stacks) because the metric is *signed*: stacking
    would hide the sign of individual links inside a net aggregate. Each
    month shows one bar per link, coloured green when the link reduced
    system emissions that month and red otherwise. A horizontal line at
    zero separates the two regimes; the annual total per link is in the
    legend.

    Args:
        mc_results: Output of :func:`~energy_sim.simulation.run_monte_carlo`.
            Requires ``'interconnection_names'``,
            ``'co2_benefit_monthly_tons'`` and ``'total_co2_benefit_tons'``.
        out_path: File path to save the figure (PNG).
    """
    names = mc_results['interconnection_names']
    if not names:
        print(f"No interconnections — skipping {out_path}")
        return

    monthly = mc_results['co2_benefit_monthly_tons'].mean(axis=0) / 1e3  # kt
    totals = mc_results['total_co2_benefit_tons'].mean(axis=0) / 1e3

    n_links = len(names)
    months = np.arange(12)
    group_w = 0.8
    bar_w = group_w / n_links

    fig, ax = plt.subplots(figsize=(12, 5.5))
    cmap = plt.get_cmap('tab10')
    for i, name in enumerate(names):
        offset = (i - (n_links - 1) / 2) * bar_w
        ax.bar(months + offset, monthly[i], bar_w,
               color=cmap(i % 10), edgecolor='black', linewidth=0.3,
               label=f'{name} ({totals[i]:+,.0f} kt/yr)')
    ax.axhline(0, color='black', lw=0.8)
    ax.set_xticks(months)
    ax.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
    ax.set_ylabel('CO\u2082 benefit (kt, + = avoided emissions)')
    ax.set_title('Monthly CO\u2082 benefit by interconnection '
                 '(+ = cleaner than domestic, \u2212 = dirtier)')
    ax.legend(loc='upper right', fontsize=8, ncol=min(n_links, 3))
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def plot_generation_mix_pie(mc_results: dict, mix_config: dict,
                            out_path: str) -> None:
    """Pie chart of the annual domestic energy generation by technology.

    Uses each emissive technology's annual emissions and the identity
    ``energy_e = emissions * eta / emission_factor`` to reconstruct the
    exact dispatched energy in MWh_e. For carbon-free technologies
    (solar, wind, hydro, nuclear) that mapping is undefined, so we fall
    back to a nameplate proxy ``capacity_gw * 8760 * nominal_cf`` and
    tag those slices as ``(est.)`` in the legend to keep the
    approximation transparent.

    Args:
        mc_results: Output of :func:`~energy_sim.simulation.run_monte_carlo`.
            Requires ``'emissions_by_tech'``.
        mix_config: Generation mix dictionary (same shape as
            :data:`~energy_sim.config.ITALIAN_MIX`). Used to size the
            zero-emission slices from nameplate capacity and nominal
            capacity factors.
        out_path: File path to save the figure (PNG).
    """
    # Nominal capacity factors per technology (used only for zero-carbon
    # slices; thermal slices are reconstructed exactly from emissions).
    NOMINAL_CF = {
        'solar': 0.18, 'wind': 0.28, 'hydro': 0.30,
        'nuclear': 0.90, 'geothermal': 0.85, 'biomass': 0.60,
    }

    emissions_by_tech = mc_results['emissions_by_tech']
    tech_twh: dict[str, float] = {}
    is_estimated: dict[str, bool] = {}

    for tech, cfg in mix_config.items():
        ef = cfg.get('emission_factor', 0.0)
        eta = cfg.get('efficiency', 1.0) or 1.0
        capacity_gw = cfg.get('capacity_gw', 0.0)
        if ef > 0 and tech in emissions_by_tech:
            # tons / (tCO\u2082/MWh_th) = MWh_th; MWh_th * \u03b7 = MWh_e;
            # MWh_e / 1e6 = TWh_e.
            tons = emissions_by_tech[tech].mean()
            twh = tons * eta / ef / 1e6
            tech_twh[tech] = twh
            is_estimated[tech] = False
        else:
            cf = NOMINAL_CF.get(tech, 0.5)
            tech_twh[tech] = capacity_gw * 8760 * cf / 1e3  # GW\u00b7h \u2192 TWh
            is_estimated[tech] = True

    # Sort for a stable, readable ordering (largest slices first).
    items = sorted(tech_twh.items(), key=lambda kv: -kv[1])
    labels = []
    values = []
    for name, v in items:
        if v <= 0:
            continue
        suffix = ' (est.)' if is_estimated[name] else ''
        labels.append(f'{name}{suffix}\n{v:.1f} TWh')
        values.append(v)

    fig, ax = plt.subplots(figsize=(8, 8))
    colors = plt.get_cmap('tab20').colors[:len(values)]
    _wedges, _texts, autotexts = ax.pie(
        values, labels=labels, colors=colors, autopct='%1.1f%%',
        startangle=90, pctdistance=0.78,
        wedgeprops={'linewidth': 0.5, 'edgecolor': 'white'},
    )
    for t in autotexts:
        t.set_fontsize(9)
        t.set_color('white')
        t.set_fontweight('bold')
    total = sum(values)
    ax.set_title(f'Annual domestic generation mix (total \u2248 {total:.0f} TWh)\n'
                 f'Emissive slices exact from CO\u2082; clean slices '
                 f'estimated from nameplate capacity factors')
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")
