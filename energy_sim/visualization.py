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
