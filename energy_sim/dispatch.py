"""
Vectorized merit-order dispatch engine with inertia constraints.

Implements a three-phase dispatch algorithm:

1. **Merit-order dispatch** (vectorized): sorts generators by SRMC, stacks
   them in order of increasing cost, and dispatches to meet load. The marginal
   price is set by the most expensive dispatched generator at each timestep.
   Interconnection imports, if supplied, enter the merit order as virtual
   generators with time-varying SRMC and availability (NTC paths) — they
   clear naturally alongside domestic units with no special-casing.

2. **Inertia fix** (iterative): checks system inertia against the minimum
   threshold and forces the cheapest offline synchronous generator online if
   inertia is too low. Curtails non-synchronous generation if this causes
   oversupply. Imports do not contribute inertia and therefore do not help
   satisfy ``H_MIN_SECONDS`` — a realistic effect for HVDC links.

3. **Export adjustment** (per-interconnection, per-timestep): for each
   timestep where the domestic marginal price is below a link's export
   floor (``foreign_price - τ``) and the link has available export NTC,
   additional generation is dispatched (up to NTC) from the cheapest
   unused headroom with ``SRMC ≤ export_floor``. The marginal price is
   updated to the SRMC of the last-called unit.
"""

import numpy as np
from dataclasses import dataclass, field

from energy_sim.config import H_MIN_SECONDS, P_PEAK_GW, P_BASE, QUARTERS_PER_HOUR
from energy_sim.generators import Generator
from energy_sim.interconnections import (
    InterconnectionRealization, VirtualImportGenerator,
)


@dataclass
class DispatchResult:
    """Results of a full-year merit-order dispatch.

    All power arrays are in per-unit of system base. All prices are in
    EUR/MWh (electrical). All emissions are in physical units (kg CO₂
    per quarter-hour).

    Attributes:
        power (np.ndarray): Dispatched power matrix of shape
            ``(n_units, 35040)`` in per-unit. Rows follow :attr:`gen_names`;
            interconnection imports (if any) appear as additional rows
            with ``gen_type == 'import'``.
        marginal_price (np.ndarray): System marginal price array of shape
            ``(35040,)`` in EUR/MWh. Reflects both Phase 1 clearing, any
            inertia-fix adjustments, and the Phase 3 export re-dispatch.
        curtailment (np.ndarray): Curtailed energy array of shape ``(35040,)``
            in per-unit (energy curtailed due to inertia constraint).
        h_system (np.ndarray): System inertia constant array of shape
            ``(35040,)`` in seconds. Imports are not included in the
            weighted average (they do not provide synchronous inertia).
        unserved (np.ndarray): Unserved energy array of shape ``(35040,)``
            in per-unit (residual load after all dispatchable units and
            imports are exhausted).
        gen_names (list[str]): Names of generators and imports in the
            same order as the rows of :attr:`power`.
        gen_types (list[str]): Matching ``gen_type`` labels (``'gas'``,
            ``'solar'``, ``'import'``, …). Used by downstream aggregators
            to separate territorial from consumption-based accounting.
        emissions (np.ndarray): Territorial CO₂ emissions, shape
            ``(n_units, 35040)``, in kg CO₂ per quarter-hour. Rows for
            imports are zero under the IPCC territorial convention.
        net_import_pu (np.ndarray): Signed cross-border flow per
            interconnection, shape ``(n_interconnections, 35040)``.
            Positive values mean energy flowing *into* the domestic
            system; negative values mean export out. Zero-length array
            when no interconnections are supplied.
        interconnection_names (list[str]): Names matching the rows of
            :attr:`net_import_pu`. Empty when no interconnections.
        foreign_prices (np.ndarray): Foreign day-ahead price path per
            interconnection, shape ``(n_interconnections, 35040)`` in
            EUR/MWh. Useful for convergence analysis. Same ordering as
            :attr:`interconnection_names`.
        emissions_imported_tons (np.ndarray): Consumption-based emissions
            embedded in net imports, shape ``(n_interconnections, 35040)``
            in tonnes CO₂ per quarter-hour. Computed as
            ``max(net_import, 0) * P_BASE_GW * 0.25 * CI_g/kWh``, which
            collapses pu·GWh · (g/kWh) = pu·10⁶·g = pu·tons (the factor
            10⁶ kWh/GWh cancels the factor 10⁻⁶ ton/g). The export
            portion is not credited as a negative footprint.
    """

    power: np.ndarray
    marginal_price: np.ndarray
    curtailment: np.ndarray
    h_system: np.ndarray
    unserved: np.ndarray
    gen_names: list[str]
    emissions: np.ndarray
    gen_types: list[str] = field(default_factory=list)
    net_import_pu: np.ndarray = field(
        default_factory=lambda: np.zeros((0, 0)))
    interconnection_names: list[str] = field(default_factory=list)
    foreign_prices: np.ndarray = field(
        default_factory=lambda: np.zeros((0, 0)))
    emissions_imported_tons: np.ndarray = field(
        default_factory=lambda: np.zeros((0, 0)))


def dispatch_year(
    generators: list[Generator],
    load: np.ndarray,
    interconnection_realizations: list[InterconnectionRealization] | None = None,
) -> DispatchResult:
    """Run merit-order dispatch for one simulated year.

    The dispatch proceeds in three phases described in the module
    docstring. When ``interconnection_realizations`` is ``None`` (or
    empty), Phase 3 is skipped and the result is identical to a
    dispatch without cross-border exchanges — preserving full
    backward compatibility with existing callers.

    Args:
        generators: List of :class:`~energy_sim.generators.Generator` objects
            with :meth:`~energy_sim.generators.Generator.prepare_run`
            already called.
        load: Load profile array of shape ``(35040,)`` in per-unit.
        interconnection_realizations: Optional list of realized
            interconnections. Each is wrapped in a
            :class:`~energy_sim.interconnections.VirtualImportGenerator`
            and appended to the merit-order stack; its export path is
            consumed by Phase 3.

    Returns:
        DispatchResult: Aggregated dispatch results for the year,
            including cross-border flows when interconnections are
            supplied.
    """
    interconnection_realizations = interconnection_realizations or []
    n_domestic = len(generators)
    n_ic = len(interconnection_realizations)

    # Build the full merit-order stack: domestic first, then virtual imports.
    # The ordering is purely a convention — the merit-order algorithm is
    # invariant to the initial ordering (it sorts by SRMC).
    virtual_imports = [r.as_virtual_import_generator()
                       for r in interconnection_realizations]
    units: list = list(generators) + list(virtual_imports)

    n_units = len(units)
    n_t = len(load)

    srmc_all = np.array([u.srmc() for u in units])
    avail_all = np.array([u.available_power_pu() for u in units])
    h_values = np.array([u.h_inertia for u in units])
    is_sync = np.array([u.is_synchronous for u in units])
    min_stable = np.array([u.min_stable_power_pu() for u in units])
    capacity_pu = np.array([u.capacity_pu for u in units])

    # Phase 1: vectorized merit order
    order = np.argsort(srmc_all, axis=0)
    avail_sorted = np.take_along_axis(avail_all, order, axis=0)
    cum_before = np.vstack([np.zeros((1, n_t)), np.cumsum(avail_sorted, axis=0)[:-1]])
    remaining = np.maximum(load[np.newaxis, :] - cum_before, 0)
    dispatched_sorted = np.minimum(avail_sorted, remaining)
    inv_order = np.argsort(order, axis=0)
    power = np.take_along_axis(dispatched_sorted, inv_order, axis=0)

    unserved = np.maximum(load - power.sum(axis=0), 0)

    srmc_dispatched = np.where(power > 0, srmc_all, -np.inf)
    marginal_price = np.maximum(srmc_dispatched.max(axis=0), 0)

    # Phase 2: inertia fix. Imports contribute no synchronous inertia and
    # cannot be used to satisfy H_MIN — the existing algorithm already
    # respects this because it only considers is_sync == True units.
    sync_online = (power > 0) & is_sync[:, np.newaxis]
    wh = (h_values[:, np.newaxis] * capacity_pu[:, np.newaxis]) * sync_online
    tc = np.maximum((capacity_pu[:, np.newaxis] * sync_online).sum(axis=0), 1e-10)
    h_system = wh.sum(axis=0) / tc
    h_system[tc < 1e-9] = 0

    curtailment = np.zeros(n_t)
    violation_mask = h_system < H_MIN_SECONDS

    if violation_mask.any():
        sync_indices = np.where(is_sync)[0]
        if len(sync_indices) > 0:
            avg_srmc_sync = srmc_all[sync_indices].mean(axis=1)
            sync_sorted = sync_indices[np.argsort(avg_srmc_sync)]

            viol_indices = np.where(violation_mask)[0]
            for t in viol_indices:
                for si in sync_sorted:
                    if power[si, t] > 0 or avail_all[si, t] <= 0:
                        continue
                    power[si, t] = min(min_stable[si], avail_all[si, t])
                    if power[si, t] <= 0:
                        power[si, t] = avail_all[si, t] * 0.4
                    sm = (power[:, t] > 0) & is_sync
                    if sm.any():
                        h_system[t] = ((h_values[sm] * capacity_pu[sm]).sum()
                                       / capacity_pu[sm].sum())
                    if h_system[t] >= H_MIN_SECONDS:
                        break

                excess = power[:, t].sum() - load[t]
                if excess > 0:
                    nonsync = np.where(~is_sync & (power[:, t] > 0))[0]
                    if len(nonsync) > 0:
                        for ni in nonsync[np.argsort(-srmc_all[nonsync, t])]:
                            cut = min(power[ni, t], excess)
                            power[ni, t] -= cut
                            curtailment[t] += cut
                            excess -= cut
                            if excess <= 0:
                                break

                dm = power[:, t] > 0
                if dm.any():
                    marginal_price[t] = srmc_all[dm, t].max()

    # ── Phase 3: export adjustment ──────────────────────────────────────
    #
    # For each interconnection, at each timestep where the current
    # marginal price is below the link's export floor and export NTC is
    # available, dispatch additional headroom from units with
    # SRMC <= export_floor until the floor is reached or NTC is saturated.
    # Interconnections are processed in order of decreasing export floor
    # so that the most lucrative destination is served first. Domestic
    # units are called upon greedily in merit order; virtual imports do
    # NOT serve export (they are a separate commercial flow on the same
    # physical link's opposite direction — modelling them as an export
    # source would be economically incoherent). Imports already
    # dispatched in Phase 1 are unaffected.
    export_power = np.zeros((n_ic, n_t))

    if n_ic > 0:
        # Domestic-only slice for headroom accounting
        domestic_mask = np.zeros(n_units, dtype=bool)
        domestic_mask[:n_domestic] = True

        # Build export metadata arrays
        export_floor = np.array(
            [r.export_floor_path for r in interconnection_realizations])   # (n_ic, T)
        ntc_export_pu = np.array(
            [r.ntc_export_pu_path for r in interconnection_realizations])  # (n_ic, T)

        # For each timestep, find links with profitable export opportunity
        # and available NTC. Vectorized candidate mask:
        candidate_mask = (ntc_export_pu > 1e-12) & (
            export_floor > marginal_price[np.newaxis, :])

        active_t = np.where(candidate_mask.any(axis=0))[0]

        for t in active_t:
            # Links active at this timestep, sorted by floor descending
            ic_at_t = np.where(candidate_mask[:, t])[0]
            if ic_at_t.size == 0:
                continue
            ic_at_t = ic_at_t[np.argsort(-export_floor[ic_at_t, t])]

            # Current per-unit headroom, by unit, domestic only
            headroom = np.where(
                domestic_mask,
                avail_all[:, t] - power[:, t],
                0.0,
            )
            headroom = np.maximum(headroom, 0.0)

            for k in ic_at_t:
                floor_k = float(export_floor[k, t])
                ntc_k = float(ntc_export_pu[k, t])

                # Merit-order over domestic units with SRMC <= floor_k
                eligible = np.where(
                    domestic_mask & (srmc_all[:, t] <= floor_k) & (headroom > 0)
                )[0]
                if eligible.size == 0:
                    continue
                # Call units by increasing SRMC
                eligible = eligible[np.argsort(srmc_all[eligible, t])]

                remaining_demand = ntc_k
                last_srmc_called = marginal_price[t]
                for ui in eligible:
                    if remaining_demand <= 1e-12:
                        break
                    take = min(headroom[ui], remaining_demand)
                    if take <= 0:
                        continue
                    power[ui, t] += take
                    headroom[ui] -= take
                    export_power[k, t] += take
                    remaining_demand -= take
                    last_srmc_called = float(srmc_all[ui, t])

                # Marginal price rises to the SRMC of the last unit called
                # (if any was called for this link).
                if export_power[k, t] > 0:
                    marginal_price[t] = max(marginal_price[t], last_srmc_called)

    # Net import = import_dispatched - export_power (per interconnection).
    # Import-dispatched is the dispatched power of each virtual import
    # generator, which lives in rows [n_domestic : n_units] of `power`.
    if n_ic > 0:
        import_power = power[n_domestic:n_units, :]           # shape (n_ic, T)
        net_import_pu = import_power - export_power
        foreign_prices = np.array(
            [r.foreign_price for r in interconnection_realizations])
        ci_g_per_kwh = np.array(
            [r.carbon_intensity_g_per_kwh
             for r in interconnection_realizations])
        # Consumption-based emissions: only when net flow is into IT (import).
        # Dimensional analysis: pos_net[pu] · P_BASE[GW] · 0.25[h] gives
        # energy in pu·GWh; multiplying by CI[g/kWh] yields
        # pu · GWh · g/kWh = pu · 10⁶ kWh · g/kWh = pu · 10⁶ g = pu · tons.
        # So the product below is already in tonnes of CO₂ per quarter-hour —
        # no further scaling needed.
        pos_net = np.maximum(net_import_pu, 0.0)
        emissions_imported_tons = (
            pos_net * P_BASE * 0.25 * ci_g_per_kwh[:, np.newaxis])
    else:
        net_import_pu = np.zeros((0, n_t))
        foreign_prices = np.zeros((0, n_t))
        emissions_imported_tons = np.zeros((0, n_t))

    # Territorial CO₂ emissions: kg per quarter-hour per unit.
    # power_pu * P_BASE(GW) * 0.25(h) = energy in GWh
    # GWh * 1000 = MWh_e; MWh_e / efficiency = MWh_th; MWh_th * emission_factor(tCO₂/MWh_th) = tCO₂
    # tCO₂ * 1000 = kgCO₂
    emission_factors = np.array([u.emission_factor for u in units])
    efficiencies = np.array([u.efficiency for u in units])
    safe_eff = np.where(efficiencies > 0, efficiencies, 1.0)
    emissions = (power * P_BASE * 0.25 * 1000
                 * emission_factors[:, np.newaxis] / safe_eff[:, np.newaxis])

    gen_names = [u.name for u in units]
    gen_types = [getattr(u, 'gen_type', 'unknown') for u in units]

    return DispatchResult(
        power=power,
        marginal_price=marginal_price,
        curtailment=curtailment,
        h_system=h_system,
        unserved=unserved,
        gen_names=gen_names,
        gen_types=gen_types,
        emissions=emissions,
        net_import_pu=net_import_pu,
        interconnection_names=[r.name for r in interconnection_realizations],
        foreign_prices=foreign_prices,
        emissions_imported_tons=emissions_imported_tons,
    )
