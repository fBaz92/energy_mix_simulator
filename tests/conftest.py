"""Shared pytest fixtures for the energy_sim test suite.

Provides reusable test infrastructure: a pre-built TimeGrid, a seeded
random generator for reproducibility, a default CO2 price model, and a
factory fixture to create Generator instances with sensible defaults
without repeating boilerplate in every test module.
"""

import numpy as np
import pytest

from energy_sim.models import TimeGrid
from energy_sim.generators import (
    CarbonPriceModel,
    ConstantFuelPrice,
    DispatchableAvailability,
    Generator,
)


@pytest.fixture
def time_grid():
    """Create a fresh TimeGrid instance (35 040 quarter-hours, one year).

    Returns:
        TimeGrid: Fully initialized temporal backbone with month, hour,
        day_of_year, day_of_week, and is_holiday arrays.
    """
    return TimeGrid()


@pytest.fixture
def rng():
    """Create a reproducible NumPy random generator seeded at 42.

    Returns:
        np.random.Generator: Deterministic RNG for tests that need
        stochastic inputs but must remain reproducible.
    """
    return np.random.default_rng(42)


@pytest.fixture
def co2_model():
    """Create a CarbonPriceModel with the default CO2 price (65 EUR/ton).

    Returns:
        CarbonPriceModel: Constant CO2 price model used to call
        ``Generator.prepare_run()``.
    """
    return CarbonPriceModel()


@pytest.fixture
def make_generator():
    """Factory fixture to create Generator instances with sensible defaults.

    Returns a callable that accepts any subset of Generator constructor
    parameters and fills in the rest with gas-like defaults (10 GW,
    efficiency 0.58, H=4.5 s, constant fuel price 35 EUR/MWh_th).

    Returns:
        Callable[..., Generator]: A factory function ``_make(**kwargs)``
        that returns a configured Generator.
    """

    def _make(name="test_gen", gen_type="gas", capacity_gw=10.0,
              capex_per_kw=900, lifetime_years=27, vom_eur_mwh=3.0,
              fom_eur_kw_yr=20.0, efficiency=0.58, emission_factor=0.20,
              h_inertia=4.5, min_stable_pct=0.40,
              ramp_rate_pct_per_min=0.06, startup_cost_eur_mw=50.0,
              fuel_model=None, availability_model=None):
        """Build a Generator with the given overrides, defaulting the rest.

        Args:
            name: Human-readable generator name.
            gen_type: Technology type identifier.
            capacity_gw: Installed capacity in GW.
            capex_per_kw: Capital expenditure in EUR/kW.
            lifetime_years: Economic lifetime in years.
            vom_eur_mwh: Variable O&M in EUR/MWh.
            fom_eur_kw_yr: Fixed O&M in EUR/kW/year.
            efficiency: Thermal-to-electric efficiency.
            emission_factor: CO2 emission factor (tCO2/MWh_th).
            h_inertia: Inertia constant H in seconds.
            min_stable_pct: Minimum stable generation fraction.
            ramp_rate_pct_per_min: Ramp rate fraction per minute.
            startup_cost_eur_mw: Start-up cost EUR/MW.
            fuel_model: Fuel price model (defaults to ConstantFuelPrice(35)).
            availability_model: Availability model (defaults to Dispatchable).

        Returns:
            Generator: Fully initialized generator ready for prepare_run().
        """
        if fuel_model is None:
            fuel_model = ConstantFuelPrice(35.0)
        return Generator(
            name=name,
            gen_type=gen_type,
            capacity_gw=capacity_gw,
            capex_per_kw=capex_per_kw,
            lifetime_years=lifetime_years,
            vom_eur_mwh=vom_eur_mwh,
            fom_eur_kw_yr=fom_eur_kw_yr,
            efficiency=efficiency,
            emission_factor=emission_factor,
            h_inertia=h_inertia,
            min_stable_pct=min_stable_pct,
            ramp_rate_pct_per_min=ramp_rate_pct_per_min,
            startup_cost_eur_mw=startup_cost_eur_mw,
            fuel_model=fuel_model,
            availability_model=availability_model,
        )

    return _make
