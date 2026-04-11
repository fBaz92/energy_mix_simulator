"""
Vectorized merit-order dispatch engine with inertia constraints.

Implements a two-phase dispatch algorithm:

1. **Merit-order dispatch** (vectorized): sorts generators by SRMC, stacks
   them in order of increasing cost, and dispatches to meet load. The marginal
   price is set by the most expensive dispatched generator at each timestep.

2. **Inertia fix** (iterative): checks system inertia against the minimum
   threshold and forces the cheapest offline synchronous generator online if
   inertia is too low. Curtails non-synchronous generation if this causes
   oversupply.
"""

import numpy as np
from dataclasses import dataclass

from energy_sim.config import H_MIN_SECONDS, P_PEAK_GW, P_BASE
from energy_sim.generators import Generator


@dataclass
class DispatchResult:
    """Results of a full-year merit-order dispatch.

    Attributes:
        power (np.ndarray): Dispatched power matrix of shape
            ``(n_generators, 35040)`` in per-unit of system base.
        marginal_price (np.ndarray): System marginal price array of shape
            ``(35040,)`` in EUR/MWh.
        curtailment (np.ndarray): Curtailed energy array of shape ``(35040,)``
            in per-unit (energy curtailed due to inertia constraint).
        h_system (np.ndarray): System inertia constant array of shape
            ``(35040,)`` in seconds.
        unserved (np.ndarray): Unserved energy array of shape ``(35040,)``
            in per-unit (load that could not be met).
        gen_names (list[str]): Names of generators in the same order as the
            rows of the ``power`` matrix.
        emissions (np.ndarray): CO₂ emissions matrix of shape
            ``(n_generators, 35040)`` in tons CO₂ per quarter-hour.
            Computed as ``power_pu * P_BASE * 0.25 * emission_factor / efficiency``.
    """

    power: np.ndarray
    marginal_price: np.ndarray
    curtailment: np.ndarray
    h_system: np.ndarray
    unserved: np.ndarray
    gen_names: list[str]
    emissions: np.ndarray


def dispatch_year(generators: list[Generator], load: np.ndarray) -> DispatchResult:
    """Run merit-order dispatch for one simulated year.

    Phase 1 (vectorized): For each timestep, generators are sorted by SRMC.
    Available capacity is stacked in merit order until load is met. The SRMC
    of the marginal (last dispatched) generator sets the system price.

    Phase 2 (iterative): Timesteps where the capacity-weighted average inertia
    of online synchronous generators falls below ``H_MIN_SECONDS`` are fixed
    by forcing the cheapest offline synchronous generator to its minimum stable
    generation. Excess supply is curtailed from non-synchronous generators
    in reverse merit order.

    Args:
        generators: List of :class:`~energy_sim.generators.Generator` objects
            with :meth:`~energy_sim.generators.Generator.prepare_run` already
            called.
        load: Load profile array of shape ``(35040,)`` in per-unit.

    Returns:
        DispatchResult: Aggregated dispatch results for the year.
    """
    n_gen = len(generators)
    n_t = len(load)

    srmc_all = np.array([g.srmc() for g in generators])
    avail_all = np.array([g.available_power_pu() for g in generators])
    h_values = np.array([g.h_inertia for g in generators])
    is_sync = np.array([g.is_synchronous for g in generators])
    min_stable = np.array([g.min_stable_power_pu() for g in generators])
    capacity_pu = np.array([g.capacity_pu for g in generators])

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

    # Phase 2: inertia fix
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

    # CO₂ emissions: tons per quarter-hour per generator
    # power_pu * P_BASE(GW) * 0.25(h) = energy in GWh
    # GWh * 1000 = MWh_e; MWh_e / efficiency = MWh_th; MWh_th * emission_factor = tCO₂
    emission_factors = np.array([g.emission_factor for g in generators])
    efficiencies = np.array([g.efficiency for g in generators])
    safe_eff = np.where(efficiencies > 0, efficiencies, 1.0)
    emissions = (power * P_BASE * 0.25 * 1000
                 * emission_factors[:, np.newaxis] / safe_eff[:, np.newaxis])

    return DispatchResult(
        power=power,
        marginal_price=marginal_price,
        curtailment=curtailment,
        h_system=h_system,
        unserved=unserved,
        gen_names=[g.name for g in generators],
        emissions=emissions,
    )
