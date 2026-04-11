"""Tests for energy_sim.dispatch (vectorized merit-order dispatch + inertia fix).

Validates the two-phase dispatch algorithm: Phase 1 (merit order) ensures
generators are stacked by SRMC, marginal pricing is correct, load is balanced,
and unserved energy appears when capacity is insufficient. Phase 2 (inertia
fix) ensures synchronous generators are forced online when system inertia is
too low and that excess supply is curtailed from non-synchronous sources.
"""

import numpy as np
import pytest

from energy_sim.config import P_PEAK_GW
from energy_sim.generators import (
    Generator,
    ConstantFuelPrice,
    CarbonPriceModel,
    DispatchableAvailability,
    MustRunAvailability,
)
from energy_sim.dispatch import dispatch_year
from energy_sim.models import TimeGrid


def _quick_gen(name, capacity_gw, vom, h_inertia=4.5,
               min_stable_pct=0.4, efficiency=1.0,
               emission_factor=0.0, fuel_price=None,
               availability_model=None):
    """Build a simplified Generator for dispatch tests.

    Creates a generator with zero CAPEX, zero FOM, zero emissions (unless
    overridden), and a constant fuel price. This isolates dispatch logic
    from economic complexity.

    Args:
        name: Generator name (also used as gen_type).
        capacity_gw: Installed capacity in GW.
        vom: Variable O&M cost in EUR/MWh (determines merit order position).
        h_inertia: Inertia constant H in seconds. Defaults to 4.5 (synchronous).
        min_stable_pct: Minimum stable generation fraction. Defaults to 0.4.
        efficiency: Thermal-to-electric efficiency. Defaults to 1.0.
        emission_factor: CO2 emission factor. Defaults to 0.0.
        fuel_price: Constant fuel price in EUR/MWh_th, or None for no fuel cost.
        availability_model: Custom availability model, or None for DispatchableAvailability.

    Returns:
        Generator: Ready for prepare_run() and dispatch.
    """
    fm = ConstantFuelPrice(fuel_price) if fuel_price is not None else None
    return Generator(
        name=name, gen_type=name, capacity_gw=capacity_gw,
        capex_per_kw=0, lifetime_years=30, vom_eur_mwh=vom,
        fom_eur_kw_yr=0, efficiency=efficiency,
        emission_factor=emission_factor, h_inertia=h_inertia,
        min_stable_pct=min_stable_pct,
        ramp_rate_pct_per_min=1.0, startup_cost_eur_mw=0,
        fuel_model=fm, availability_model=availability_model,
    )


@pytest.fixture
def tg():
    """Create a fresh TimeGrid for dispatch tests."""
    return TimeGrid()


@pytest.fixture
def co2():
    """Create a zero-CO2-price model to isolate dispatch logic from carbon costs."""
    return CarbonPriceModel(mu=0.0, sigma=0.0, theta=0.05)


class TestMeritOrder:
    """Verify that generators are dispatched in order of ascending SRMC."""

    def test_cheapest_dispatched_first(self, tg, co2):
        """When load can be fully met by the cheapest generator alone, the expensive
        generator must have zero dispatch at all timesteps.
        """
        cheap = _quick_gen("cheap", 30.0, vom=5.0)
        expensive = _quick_gen("expensive", 30.0, vom=50.0)
        rng = np.random.default_rng(0)
        for g in [cheap, expensive]:
            g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, cheap.capacity_pu * 0.5)
        result = dispatch_year([cheap, expensive], load)
        assert (result.power[0] > 0).all()
        assert (result.power[1] == 0).all()

    def test_marginal_price_is_last_dispatched(self, tg, co2):
        """When load exceeds the cheapest generator's capacity, the marginal price
        must equal the SRMC of the second generator (the marginal unit).
        """
        cheap = _quick_gen("cheap", 30.0, vom=5.0)
        mid = _quick_gen("mid", 30.0, vom=20.0)
        rng = np.random.default_rng(0)
        for g in [cheap, mid]:
            g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, cheap.capacity_pu + mid.capacity_pu * 0.1)
        result = dispatch_year([cheap, mid], load)
        np.testing.assert_allclose(result.marginal_price, 20.0, atol=0.01)


class TestDispatchShapes:
    """Verify the shapes and structure of DispatchResult arrays."""

    def test_output_shapes(self, tg, co2):
        """All DispatchResult arrays must have correct shapes:
        power (n_gen, n_t), marginal_price (n_t,), curtailment (n_t,),
        h_system (n_t,), unserved (n_t,), and gen_names must match.
        """
        g = _quick_gen("gen", 30.0, vom=10.0)
        rng = np.random.default_rng(0)
        g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, g.capacity_pu * 0.5)
        result = dispatch_year([g], load)
        assert result.power.shape == (1, tg.n)
        assert result.marginal_price.shape == (tg.n,)
        assert result.curtailment.shape == (tg.n,)
        assert result.h_system.shape == (tg.n,)
        assert result.unserved.shape == (tg.n,)
        assert result.gen_names == ["gen"]


class TestLoadBalance:
    """Verify that dispatched power + unserved energy equals load (energy conservation)."""

    def test_load_satisfied(self, tg, co2):
        """Total dispatched power plus unserved energy must equal load at every timestep
        (within floating-point tolerance).
        """
        g1 = _quick_gen("g1", 40.0, vom=5.0)
        g2 = _quick_gen("g2", 40.0, vom=10.0)
        rng = np.random.default_rng(0)
        for g in [g1, g2]:
            g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, (40.0 + 40.0) / P_PEAK_GW * 0.5)
        result = dispatch_year([g1, g2], load)
        total_supply = result.power.sum(axis=0) + result.unserved
        np.testing.assert_allclose(total_supply, load, atol=1e-8)

    def test_no_overgeneration_simple(self, tg, co2):
        """With a single synchronous generator (no inertia violations), total dispatch
        must not exceed load at any timestep.
        """
        g = _quick_gen("g", 60.0, vom=10.0, h_inertia=5.0)
        rng = np.random.default_rng(0)
        g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, g.capacity_pu * 0.5)
        result = dispatch_year([g], load)
        assert (result.power.sum(axis=0) <= load + 1e-10).all()


class TestUnservedEnergy:
    """Verify unserved energy appears when total capacity is insufficient."""

    def test_unserved_when_insufficient_capacity(self, tg, co2):
        """When load (30 GW) exceeds total installed capacity (10 GW), unserved
        energy must be positive at every timestep.
        """
        g = _quick_gen("small", 10.0, vom=5.0)
        rng = np.random.default_rng(0)
        g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, 30.0 / P_PEAK_GW)
        result = dispatch_year([g], load)
        assert (result.unserved > 0).all()


class TestInertiaConstraint:
    """Verify Phase 2 inertia fix: forcing synchronous units and curtailing renewables."""

    def test_inertia_fix_forces_synchronous(self, tg, co2):
        """When only non-synchronous generation (wind, h=0) is dispatched, system
        inertia falls below H_MIN. The inertia fix must force the synchronous
        generator (gas, h=5) online at some timesteps.
        """
        nonsync = _quick_gen("wind", 40.0, vom=1.0, h_inertia=0.0,
                             min_stable_pct=0.0)
        sync = _quick_gen("gas", 20.0, vom=50.0, h_inertia=5.0,
                          min_stable_pct=0.4)
        rng = np.random.default_rng(0)
        for g in [nonsync, sync]:
            g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, nonsync.capacity_pu * 0.5)
        result = dispatch_year([nonsync, sync], load)
        gas_idx = result.gen_names.index("gas")
        assert (result.power[gas_idx] > 0).any()

    def test_curtailment_from_inertia_fix(self, tg, co2):
        """When the inertia fix forces a synchronous generator to its minimum stable
        generation and total supply exceeds load, non-synchronous generation must
        be curtailed to balance the system.
        """
        nonsync = _quick_gen("wind", 40.0, vom=1.0, h_inertia=0.0,
                             min_stable_pct=0.0)
        sync = _quick_gen("gas", 20.0, vom=50.0, h_inertia=5.0,
                          min_stable_pct=0.4)
        rng = np.random.default_rng(0)
        for g in [nonsync, sync]:
            g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, nonsync.capacity_pu * 0.3)
        result = dispatch_year([nonsync, sync], load)
        assert result.curtailment.sum() > 0


class TestEmissions:
    """Verify CO₂ emissions computation in dispatch results."""

    def test_emissions_shape(self, tg, co2):
        """Emissions array must have shape (n_gen, n_t), matching the power array."""
        g1 = _quick_gen("gas", 30.0, vom=5.0, efficiency=0.58,
                         emission_factor=0.20, fuel_price=35.0)
        g2 = _quick_gen("wind", 30.0, vom=1.0, h_inertia=0.0,
                         emission_factor=0.0)
        rng = np.random.default_rng(0)
        for g in [g1, g2]:
            g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, g1.capacity_pu * 0.5)
        result = dispatch_year([g1, g2], load)
        assert result.emissions.shape == (2, tg.n)

    def test_zero_emission_generator(self, tg, co2):
        """A generator with emission_factor=0 must produce zero emissions at all
        timesteps, regardless of dispatch level.
        """
        g = _quick_gen("wind", 30.0, vom=1.0, h_inertia=0.0,
                        emission_factor=0.0)
        rng = np.random.default_rng(0)
        g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, g.capacity_pu * 0.5)
        result = dispatch_year([g], load)
        assert (result.emissions[0] == 0).all()

    def test_positive_emissions_for_fossil(self, tg, co2):
        """A dispatched gas generator with emission_factor>0 must produce positive
        emissions wherever it has positive dispatch.
        """
        g = _quick_gen("gas", 60.0, vom=5.0, efficiency=0.58,
                        emission_factor=0.20, fuel_price=35.0)
        rng = np.random.default_rng(0)
        g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, g.capacity_pu * 0.5)
        result = dispatch_year([g], load)
        dispatched_mask = result.power[0] > 0
        assert (result.emissions[0, dispatched_mask] > 0).all()

    def test_emissions_formula(self, tg, co2):
        """Emissions must follow the formula:
        power_pu * P_BASE * 0.25 * 1000 * emission_factor / efficiency.
        Verified for a single generator with constant values.
        """
        g = _quick_gen("gas", 60.0, vom=5.0, efficiency=0.50,
                        emission_factor=0.20, fuel_price=35.0)
        rng = np.random.default_rng(0)
        g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, g.capacity_pu * 0.3)
        result = dispatch_year([g], load)
        expected = result.power[0] * P_PEAK_GW * 0.25 * 1000 * 0.20 / 0.50
        np.testing.assert_allclose(result.emissions[0], expected, rtol=1e-10)


class TestSingleGenerator:
    """Verify dispatch behavior with a single generator (trivial case)."""

    def test_single_gen_dispatch(self, tg, co2):
        """With one generator, marginal price must equal its SRMC and dispatched
        power must exactly match load at every timestep.
        """
        g = _quick_gen("solo", 60.0, vom=15.0)
        rng = np.random.default_rng(0)
        g.prepare_run(tg, rng, co2)
        load = np.full(tg.n, g.capacity_pu * 0.5)
        result = dispatch_year([g], load)
        np.testing.assert_allclose(result.marginal_price, 15.0, atol=0.01)
        np.testing.assert_allclose(result.power[0], load, atol=1e-10)


class TestAllDispatched:
    """Verify that all generators contribute when load equals total capacity."""

    def test_all_contribute(self, tg, co2):
        """When load equals the sum of all generators' capacities, every generator
        must have positive dispatch at every timestep.
        """
        g1 = _quick_gen("g1", 20.0, vom=5.0)
        g2 = _quick_gen("g2", 20.0, vom=10.0)
        g3 = _quick_gen("g3", 20.0, vom=15.0)
        rng = np.random.default_rng(0)
        for g in [g1, g2, g3]:
            g.prepare_run(tg, rng, co2)
        total_cap = g1.capacity_pu + g2.capacity_pu + g3.capacity_pu
        load = np.full(tg.n, total_cap)
        result = dispatch_year([g1, g2, g3], load)
        for i in range(3):
            assert (result.power[i] > 0).all()
