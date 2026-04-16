"""
Energy Mix Monte Carlo Simulator.

A Monte Carlo simulator for analyzing the impact of different energy generation
mixes on annualized electricity prices. Built around the Italian power system
as reference case (60 GW peak), but designed to be technology-agnostic and
extensible.

Modules:
    config: Global parameters, default scenarios, and system coefficients.
    models: Temporal backbone (TimeGrid) and load profile models.
    generators: Fuel/carbon price models, availability models, and Generator class.
    dispatch: Vectorized merit-order dispatch engine with inertia constraints.
    simulation: Monte Carlo runner and scenario sweep utilities.
    visualization: All plotting functions for results analysis.
"""

from energy_sim.config import ITALIAN_MIX, GAS_SCENARIOS, P_PEAK_GW, N_MC_RUNS
from energy_sim.models import TimeGrid, LoadProfile
from energy_sim.generators import Generator, build_generators
from energy_sim.dispatch import dispatch_year, DispatchResult
from energy_sim.simulation import (
    SimulationConfig, MonteCarloResult,
    run_monte_carlo, sweep_technology, build_sensitivity_heatmap,
)
