"""Tests for energy_sim.generators (price models, availability models, Generator, build_generators).

Validates the Ornstein-Uhlenbeck fuel price model, constant price models,
CO2 price model, all four availability models (Dispatchable, MustRun, Solar,
Wind), the Generator class (capacity conversion, SRMC, LCOE, prepare_run),
and the build_generators factory (routing logic, zero-capacity filtering).
"""

import numpy as np
import pytest

from energy_sim.config import CO2_PRICE_DEFAULT, ITALIAN_MIX, GAS_SCENARIOS, P_PEAK_GW
from energy_sim.generators import (
    FuelPriceModel,
    ConstantFuelPrice,
    CarbonPriceModel,
    DispatchableAvailability,
    MustRunAvailability,
    SolarAvailability,
    WindAvailability,
    Generator,
    build_generators,
)
from energy_sim.models import TimeGrid


# ── FuelPriceModel ──────────────────────────────────────────────────────


class TestFuelPriceModel:
    """Verify the Ornstein-Uhlenbeck mean-reverting fuel price process."""

    def test_output_shape(self, rng):
        """generate_path() must return an array of shape (n_steps,) matching the requested length."""
        model = FuelPriceModel(mu=35.0, sigma=8.0, theta=0.1)
        path = model.generate_path(35040, rng)
        assert path.shape == (35040,)

    def test_floor_at_1(self, rng):
        """All prices must be >= 1.0 EUR/MWh_th (hard floor in the O-U discretization)."""
        model = FuelPriceModel(mu=5.0, sigma=20.0, theta=0.01)
        path = model.generate_path(35040, rng)
        assert (path >= 1.0).all()

    def test_first_value_is_mu(self, rng):
        """The first element of the price path must equal the long-run mean mu (initial condition)."""
        model = FuelPriceModel(mu=42.0, sigma=8.0)
        path = model.generate_path(100, rng)
        assert path[0] == 42.0

    def test_mean_reversion(self):
        """With very high theta (fast mean-reversion), the price standard deviation
        must be smaller than sigma, confirming the process stays close to mu.
        """
        rng = np.random.default_rng(0)
        model = FuelPriceModel(mu=35.0, sigma=8.0, theta=10.0)
        path = model.generate_path(35040, rng)
        assert path.std() < 8.0

    def test_reproducibility(self):
        """Two paths generated with the same seed must be identical (deterministic RNG)."""
        m = FuelPriceModel(mu=35.0, sigma=8.0)
        p1 = m.generate_path(1000, np.random.default_rng(7))
        p2 = m.generate_path(1000, np.random.default_rng(7))
        np.testing.assert_array_equal(p1, p2)


# ── ConstantFuelPrice ───────────────────────────────────────────────────


class TestConstantFuelPrice:
    """Verify the constant fuel price model (e.g. uranium)."""

    def test_constant_output(self):
        """generate_path() must return a flat array filled with the configured price,
        and must accept rng=None and dt=None without error.
        """
        model = ConstantFuelPrice(price=3.0)
        path = model.generate_path(100, rng=None, dt=None)
        np.testing.assert_array_equal(path, np.full(100, 3.0))


# ── CarbonPriceModel ───────────────────────────────────────────────────


class TestCarbonPriceModel:
    """Verify the CO2 ETS price model (currently constant)."""

    def test_default_price(self):
        """Default constructor must use CO2_PRICE_DEFAULT (65.0 EUR/ton)."""
        model = CarbonPriceModel()
        assert model.price == CO2_PRICE_DEFAULT

    def test_constant_output(self):
        """generate_path() must return a flat array of CO2_PRICE_DEFAULT for all timesteps."""
        model = CarbonPriceModel()
        path = model.generate_path(100)
        np.testing.assert_array_equal(path, np.full(100, CO2_PRICE_DEFAULT))


# ── Availability models ────────────────────────────────────────────────


class TestDispatchableAvailability:
    """Verify the always-available model for dispatchable generators."""

    def test_all_ones(self, time_grid):
        """generate_profile() must return ones(35040) — fully available at all times."""
        avail = DispatchableAvailability()
        profile = avail.generate_profile(time_grid)
        np.testing.assert_array_equal(profile, np.ones(time_grid.n))


class TestMustRunAvailability:
    """Verify the constant must-run availability model."""

    def test_constant_cf(self, time_grid):
        """With cf=0.9, generate_profile() must return a flat array of 0.9 for all timesteps."""
        avail = MustRunAvailability(cf=0.9)
        profile = avail.generate_profile(time_grid)
        np.testing.assert_array_equal(profile, np.full(time_grid.n, 0.9))


class TestSolarAvailability:
    """Verify the solar availability model (deterministic envelope + Markov cloud chain)."""

    def test_shape(self, time_grid, rng):
        """generate_profile() must return an array of shape (35040,)."""
        avail = SolarAvailability()
        profile = avail.generate_profile(time_grid, rng)
        assert profile.shape == (35040,)

    def test_values_in_0_1(self, time_grid, rng):
        """All capacity factor values must lie in [0.0, 1.0]."""
        avail = SolarAvailability()
        profile = avail.generate_profile(time_grid, rng)
        assert (profile >= 0.0).all()
        assert (profile <= 1.0).all()

    def test_night_hours_zero(self, time_grid, rng):
        """Night hours (0-5) must have exactly zero solar output due to the
        hard-zeroed envelope.
        """
        avail = SolarAvailability()
        profile = avail.generate_profile(time_grid, rng)
        night_mask = (time_grid.hour <= 5)
        assert (profile[night_mask] == 0.0).all()

    def test_summer_gt_winter(self, time_grid, rng):
        """Mean solar CF in July must exceed mean CF in December, reflecting
        the monthly irradiance seasonality.
        """
        avail = SolarAvailability()
        profile = avail.generate_profile(time_grid, rng)
        july_mean = profile[time_grid.month == 7].mean()
        dec_mean = profile[time_grid.month == 12].mean()
        assert july_mean > dec_mean

    def test_reproducibility(self, time_grid):
        """Two profiles generated with the same seed must be identical."""
        avail = SolarAvailability()
        p1 = avail.generate_profile(time_grid, np.random.default_rng(0))
        p2 = avail.generate_profile(time_grid, np.random.default_rng(0))
        np.testing.assert_array_equal(p1, p2)


class TestWindAvailability:
    """Verify the wind availability model (AR(1) + Weibull + power curve)."""

    def test_shape(self, time_grid, rng):
        """generate_profile() must return an array of shape (35040,)."""
        avail = WindAvailability()
        profile = avail.generate_profile(time_grid, rng)
        assert profile.shape == (35040,)

    def test_values_in_0_1(self, time_grid, rng):
        """All capacity factor values must lie in [0.0, 1.0]."""
        avail = WindAvailability()
        profile = avail.generate_profile(time_grid, rng)
        assert (profile >= 0.0).all()
        assert (profile <= 1.0).all()

    def test_power_curve_below_cut_in(self):
        """Wind speeds below cut-in (3 m/s) must produce zero power output."""
        avail = WindAvailability()
        v = np.array([0.0, 1.0, 2.9])
        np.testing.assert_array_equal(avail._power_curve(v), np.zeros(3))

    def test_power_curve_rated(self):
        """Wind speeds between rated (12 m/s) and cut-out (25 m/s) must produce
        full power (CF = 1.0).
        """
        avail = WindAvailability()
        v = np.array([12.0, 15.0, 25.0])
        np.testing.assert_array_equal(avail._power_curve(v), np.ones(3))

    def test_power_curve_above_cut_out(self):
        """Wind speeds above cut-out (25 m/s) must produce zero power (turbine shutdown)."""
        avail = WindAvailability()
        v = np.array([25.1, 30.0])
        np.testing.assert_array_equal(avail._power_curve(v), np.zeros(2))

    def test_reproducibility(self, time_grid):
        """Two profiles generated with the same seed must be identical."""
        avail = WindAvailability()
        p1 = avail.generate_profile(time_grid, np.random.default_rng(0))
        p2 = avail.generate_profile(time_grid, np.random.default_rng(0))
        np.testing.assert_array_equal(p1, p2)

    def test_autocorrelation(self, time_grid, rng):
        """The AR(1) process with coefficient 0.995 must produce lag-1 autocorrelation
        above 0.9, reflecting multi-day weather persistence.
        """
        avail = WindAvailability()
        profile = avail.generate_profile(time_grid, rng)
        corr = np.corrcoef(profile[:-1], profile[1:])[0, 1]
        assert corr > 0.9


# ── Generator ──────────────────────────────────────────────────────────


class TestGenerator:
    """Verify Generator class: capacity conversion, SRMC, availability, LCOE."""

    def test_capacity_pu(self, make_generator):
        """capacity_pu must equal capacity_gw / P_PEAK_GW (per-unit conversion)."""
        g = make_generator(capacity_gw=12.0)
        assert g.capacity_pu == pytest.approx(12.0 / P_PEAK_GW)

    def test_is_synchronous_gas(self, make_generator):
        """A generator with h_inertia > 0 must report is_synchronous = True."""
        g = make_generator(h_inertia=4.5)
        assert g.is_synchronous is True

    def test_is_synchronous_solar(self, make_generator):
        """A generator with h_inertia = 0 must report is_synchronous = False."""
        g = make_generator(h_inertia=0.0)
        assert g.is_synchronous is False

    def test_prepare_run_populates(self, make_generator, time_grid, rng, co2_model):
        """After prepare_run(), the internal arrays _fuel_path, _co2_path, and
        _avail_profile must all be populated (not None).
        """
        g = make_generator()
        g.prepare_run(time_grid, rng, co2_model)
        assert g._fuel_path is not None
        assert g._co2_path is not None
        assert g._avail_profile is not None

    def test_srmc_shape(self, make_generator, time_grid, rng, co2_model):
        """srmc() must return an array of shape (35040,) with all values >= 0."""
        g = make_generator()
        g.prepare_run(time_grid, rng, co2_model)
        s = g.srmc()
        assert s.shape == (35040,)
        assert (s >= 0).all()

    def test_srmc_no_fuel(self, time_grid, rng, co2_model):
        """A generator with no fuel model (fuel_model=None) and zero emissions must
        have SRMC equal to its VOM cost only.
        """
        g = Generator(
            name="wind", gen_type="wind", capacity_gw=10.0,
            capex_per_kw=1250, lifetime_years=22, vom_eur_mwh=1.5,
            fom_eur_kw_yr=32.0, efficiency=1.0, emission_factor=0.0,
            h_inertia=0.0, min_stable_pct=0.0, ramp_rate_pct_per_min=1.0,
            startup_cost_eur_mw=0.0, fuel_model=None,
        )
        g.prepare_run(time_grid, rng, co2_model)
        s = g.srmc()
        np.testing.assert_allclose(s, 1.5)  # just VOM

    def test_available_power_pu_shape(self, make_generator, time_grid, rng, co2_model):
        """available_power_pu() must return shape (35040,) with values in [0, capacity_pu]."""
        g = make_generator(capacity_gw=6.0)
        g.prepare_run(time_grid, rng, co2_model)
        ap = g.available_power_pu()
        assert ap.shape == (35040,)
        assert (ap >= 0).all()
        assert (ap <= g.capacity_pu + 1e-10).all()

    def test_min_stable_power(self, make_generator):
        """min_stable_power_pu() must equal capacity_pu * min_stable_pct."""
        g = make_generator(capacity_gw=12.0, min_stable_pct=0.4)
        expected = (12.0 / P_PEAK_GW) * 0.4
        assert g.min_stable_power_pu() == pytest.approx(expected)

    def test_lcoe_positive(self, make_generator, time_grid, rng, co2_model):
        """LCOE must be strictly positive for a generator with non-zero CAPEX."""
        g = make_generator(capex_per_kw=900)
        g.prepare_run(time_grid, rng, co2_model)
        assert g.lcoe() > 0


# ── build_generators ───────────────────────────────────────────────────


class TestBuildGenerators:
    """Verify the factory function that routes technologies to correct models."""

    def test_zero_capacity_excluded(self):
        """Generators with capacity_gw == 0 (e.g. nuclear in base ITALIAN_MIX)
        must be excluded from the returned list.
        """
        gens = build_generators(ITALIAN_MIX, GAS_SCENARIOS['base'])
        names = [g.name for g in gens]
        assert 'nuclear' not in names

    def test_italian_mix_base_count(self):
        """The base ITALIAN_MIX (nuclear=0 GW) must produce exactly 4 generators:
        gas, solar, wind, hydro_mustrun.
        """
        gens = build_generators(ITALIAN_MIX, GAS_SCENARIOS['base'])
        assert len(gens) == 4

    def test_gas_has_fuel_price_model(self):
        """Gas generators must be assigned a FuelPriceModel (O-U stochastic process)."""
        gens = build_generators(ITALIAN_MIX, GAS_SCENARIOS['base'])
        gas = [g for g in gens if g.gen_type == 'gas'][0]
        assert isinstance(gas.fuel_model, FuelPriceModel)

    def test_solar_has_solar_availability(self):
        """Solar generators must be assigned a SolarAvailability model."""
        gens = build_generators(ITALIAN_MIX, GAS_SCENARIOS['base'])
        sol = [g for g in gens if g.gen_type == 'solar'][0]
        assert isinstance(sol.availability, SolarAvailability)

    def test_wind_has_wind_availability(self):
        """Wind generators must be assigned a WindAvailability model."""
        gens = build_generators(ITALIAN_MIX, GAS_SCENARIOS['base'])
        w = [g for g in gens if g.gen_type == 'wind'][0]
        assert isinstance(w.availability, WindAvailability)

    def test_nuclear_default_fuel_cost(self):
        """When nuclear lacks 'fuel_cost_eur_mwh_th', build_generators must default
        to ConstantFuelPrice(3.0) — the standard uranium fuel cost.
        """
        from copy import deepcopy
        mix = deepcopy(ITALIAN_MIX)
        mix['nuclear']['capacity_gw'] = 10.0
        mix['nuclear'].pop('fuel_cost_eur_mwh_th', None)
        gens = build_generators(mix, GAS_SCENARIOS['base'])
        nuc = [g for g in gens if g.gen_type == 'nuclear'][0]
        assert isinstance(nuc.fuel_model, ConstantFuelPrice)
        assert nuc.fuel_model.price == 3.0
