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


class TestInterconnectionsInDispatch:
    """Behavior of dispatch_year when interconnection_realizations are passed.

    Validates the two integration points added for cross-border flows:
    Phase 1 — virtual imports clear through the merit order alongside
    domestic units; Phase 3 — export redispatch pushes headroom abroad
    when the domestic marginal price is below the export floor. Also
    verifies the dual emissions accounting (territorial vs consumption-based).
    """

    # A constant foreign price is enough to probe the economic logic; the
    # stochastic price path is tested in test_interconnections.py.
    def _make_realization(self, tg, foreign_price_eur_mwh, tau=2.0,
                           ntc_import_gw=10.0, ntc_export_gw=10.0,
                           ci=200.0):
        """Build a single-link realization with constant foreign price.

        Returns a 1-element list suitable to pass as
        ``interconnection_realizations``.
        """
        from energy_sim.interconnections import Interconnection
        from energy_sim.reliability import PerfectReliability
        link = Interconnection(
            name='IT-X', price_area_name='X',
            ntc_import_gw=ntc_import_gw, ntc_export_gw=ntc_export_gw,
            transport_cost_eur_mwh=tau,
            reliability_model=PerfectReliability(),
        )
        foreign = np.full(tg.n, float(foreign_price_eur_mwh))
        return [link.realize(foreign, ci, tg, np.random.default_rng(0))]

    def test_import_clears_when_cheaper_than_domestic(self, tg, co2):
        """A foreign market at 20 EUR/MWh must displace an expensive
        domestic unit (50 EUR/MWh) up to the NTC, without triggering the
        Phase-2 inertia fix.

        A cheap domestic sync generator is included to satisfy the
        H_MIN constraint regardless of dispatch — otherwise the lone
        expensive unit would be forced online at min stable generation
        just for inertia, and the expected balance would be confounded
        by the inertia-fix pathway (a separate concern, covered elsewhere).
        """
        cheap_base = _quick_gen("cheap", 30.0, vom=5.0)       # H-provider
        expensive = _quick_gen("expensive", 30.0, vom=50.0)   # displaced
        for g in [cheap_base, expensive]:
            g.prepare_run(tg, np.random.default_rng(0), co2)

        real = self._make_realization(
            tg, foreign_price_eur_mwh=20.0, tau=0.0, ntc_import_gw=20.0)
        # Load 0.7 p.u. (42 GW): 30 GW from cheap_base + residual 12 GW
        # must come from either expensive (50 €/MWh) or import (20 €/MWh).
        # Import is cheaper → must serve the residual.
        load = np.full(tg.n, 0.7)
        result = dispatch_year([cheap_base, expensive], load, real)

        # cheap_base fully used, expensive stays offline, import fills gap
        residual_pu = 0.7 - cheap_base.capacity_pu
        assert result.power[0].mean() == pytest.approx(cheap_base.capacity_pu,
                                                        rel=1e-6)
        assert result.power[1].mean() == pytest.approx(0.0, abs=1e-9)
        assert result.power[-1].mean() == pytest.approx(residual_pu, rel=1e-6)
        # Import is the marginal resource → price = 20 €/MWh
        assert result.marginal_price.max() == pytest.approx(20.0, rel=1e-6)

    def test_expensive_import_does_not_displace_domestic(self, tg, co2):
        """An import at 100 EUR/MWh against a domestic unit at 10 EUR/MWh
        must stay off — the merit order protects the cheaper resource.
        """
        cheap = _quick_gen("cheap", 60.0, vom=10.0)
        cheap.prepare_run(tg, np.random.default_rng(0), co2)
        real = self._make_realization(
            tg, foreign_price_eur_mwh=100.0, tau=0.0)
        load = np.full(tg.n, 0.5)
        result = dispatch_year([cheap], load, real)
        assert np.allclose(result.power[-1], 0.0)
        assert result.marginal_price.max() == pytest.approx(10.0)

    def test_export_triggers_when_floor_above_domestic(self, tg, co2):
        """When foreign − τ > domestic marginal cost and export NTC > 0,
        additional domestic dispatch must flow abroad.

        Uses a very cheap domestic generator with large headroom so that
        the Phase-3 redispatch has room to satisfy the export demand.
        """
        cheap = _quick_gen("cheap", 60.0, vom=5.0)
        cheap.prepare_run(tg, np.random.default_rng(0), co2)
        real = self._make_realization(
            tg, foreign_price_eur_mwh=60.0, tau=2.0,
            ntc_import_gw=0.0, ntc_export_gw=10.0)
        # Very low load: 0.05 p.u. (3 GW) leaves huge headroom on cheap
        load = np.full(tg.n, 0.05)
        result = dispatch_year([cheap], load, real)
        # Net import must be negative (we are exporting)
        assert result.net_import_pu[0].mean() < -1e-6
        # Marginal price should have risen to cheap's SRMC (since cheap was
        # dispatched further to export)
        assert result.marginal_price.max() >= 5.0

    def test_energy_balance_holds_with_interconnections(self, tg, co2):
        """Invariant: domestic_gen + import = load + export + curtailment +
        unserved (to machine precision) regardless of phase-3 activity.

        This is the master correctness check of the dispatch integration.
        """
        g_cheap = _quick_gen("c", 40.0, vom=5.0)
        g_exp = _quick_gen("e", 30.0, vom=60.0)
        for g in [g_cheap, g_exp]:
            g.prepare_run(tg, np.random.default_rng(0), co2)
        real = self._make_realization(
            tg, foreign_price_eur_mwh=30.0, tau=2.0,
            ntc_import_gw=6.0, ntc_export_gw=4.0)
        load = np.full(tg.n, 0.5)
        result = dispatch_year([g_cheap, g_exp], load, real)

        n_domestic = 2
        domestic_gen = result.power[:n_domestic, :].sum(axis=0)
        import_power = result.power[n_domestic:, :].sum(axis=0)
        export_power = np.maximum(
            import_power - result.net_import_pu.sum(axis=0), 0.0)
        residual = (domestic_gen + import_power
                    - load - export_power
                    - result.curtailment - result.unserved)
        assert np.max(np.abs(residual)) < 1e-10

    def test_imports_carry_no_territorial_emissions(self, tg, co2):
        """The import row in result.emissions must be identically zero.

        This is the IPCC convention: cross-border imports contribute to
        consumption-based emissions (``emissions_imported_tons``) but NOT
        to territorial emissions. Scenario: undersized domestic unit so
        net import is positive and consumption-based emissions are
        non-zero (ci=500 gCO₂/kWh).
        """
        # Small domestic (15 GW = 0.25 p.u.) paired with cheap import so
        # net flow is positive import at every timestep.
        small_dom = _quick_gen("dom", 15.0, vom=60.0, efficiency=0.5,
                                emission_factor=0.3)
        small_dom.prepare_run(tg, np.random.default_rng(0), co2)
        real = self._make_realization(
            tg, foreign_price_eur_mwh=20.0, tau=0.0,
            ntc_import_gw=20.0, ntc_export_gw=0.0, ci=500.0)
        # Load 0.4 p.u. (24 GW): domestic 15 GW + import 9 GW
        load = np.full(tg.n, 0.4)
        result = dispatch_year([small_dom], load, real)
        # Import row is the last; its territorial emissions must be 0
        assert np.all(result.emissions[-1] == 0.0)
        # But consumption-based emissions must be positive (CI = 500)
        assert result.emissions_imported_tons.sum() > 0
        # Sanity check on unit: ~9 GW import × 8760 h × 500 gCO₂/kWh
        # ≈ 39.4 Mt/year. Should be in the ballpark of 10⁷ tons.
        assert result.emissions_imported_tons.sum() > 1e7

    def test_no_realizations_is_backward_compatible(self, tg, co2):
        """Calling dispatch_year without interconnection_realizations or
        with an empty list must reproduce the legacy behavior exactly.

        Protects existing callers that pre-date the interconnection layer.
        """
        g = _quick_gen("g", 30.0, vom=10.0)
        g.prepare_run(tg, np.random.default_rng(0), co2)
        load = np.full(tg.n, 0.2)
        r_none = dispatch_year([g], load)
        r_empty = dispatch_year([g], load, [])
        assert np.array_equal(r_none.power, r_empty.power)
        assert np.array_equal(r_none.marginal_price, r_empty.marginal_price)
        # No interconnection metadata populated
        assert r_none.interconnection_names == []
        assert r_none.net_import_pu.shape == (0, tg.n)
        # InterconnectionMetrics must be None in the no-link case so
        # downstream callers can branch cleanly without a shape dance.
        assert r_none.ic_metrics is None


class TestInterconnectionMetrics:
    """Invariants of :class:`~energy_sim.dispatch.InterconnectionMetrics`.

    Validates that the congestion-rent economic benefit is non-negative
    by construction, that the CO\u2082 benefit carries the correct sign
    under well-defined CI differentials, that hour/energy aggregates are
    consistent with the underlying power matrix, and that the load-weighted
    marginal CI stays inside the physically admissible envelope set by
    the domestic fleet.
    """

    def _make_realization(self, tg, foreign_price_eur_mwh, tau=2.0,
                          ntc_import_gw=10.0, ntc_export_gw=10.0,
                          ci=200.0):
        """Build a single-link realization with constant foreign price."""
        from energy_sim.interconnections import Interconnection
        from energy_sim.reliability import PerfectReliability
        link = Interconnection(
            name='IT-X', price_area_name='X',
            ntc_import_gw=ntc_import_gw, ntc_export_gw=ntc_export_gw,
            transport_cost_eur_mwh=tau,
            reliability_model=PerfectReliability(),
        )
        foreign = np.full(tg.n, float(foreign_price_eur_mwh))
        return [link.realize(foreign, ci, tg, np.random.default_rng(0))]

    def test_economic_benefit_non_negative(self, tg, co2):
        """Congestion-rent benefit must be \u2265 0 at every quarter-hour.

        The merit order only dispatches imports when they are at most as
        expensive as the marginal domestic unit, so (clearing \u2212 SRMC)
        is non-negative by construction. The metric clips residual
        floating-point slack; asserting on the raw array catches
        regressions in that clipping step or in the ordering logic.
        """
        g = _quick_gen("dom", 40.0, vom=50.0)
        g.prepare_run(tg, np.random.default_rng(0), co2)
        real = self._make_realization(
            tg, foreign_price_eur_mwh=20.0, tau=0.0,
            ntc_import_gw=20.0, ntc_export_gw=10.0)
        load = np.full(tg.n, 0.6)
        result = dispatch_year([g], load, real)

        m = result.ic_metrics
        assert m is not None
        assert m.economic_benefit_eur_qh.min() >= -1e-12
        annual_reconstructed = m.economic_benefit_eur_qh.sum(axis=1)
        assert np.allclose(m.total_economic_benefit_eur,
                           annual_reconstructed, rtol=1e-12, atol=1e-6)

    def test_co2_benefit_positive_when_import_is_cleaner(self, tg, co2):
        """Importing from a CI=50 g/kWh market against a domestic marginal
        mix at \u2248850 g/kWh must yield a positive CO\u2082 benefit
        — the import displaces dirtier domestic generation.
        """
        dirty = _quick_gen("coal", 40.0, vom=30.0,
                           efficiency=0.40, emission_factor=0.34)
        dirty.prepare_run(tg, np.random.default_rng(0), co2)
        real = self._make_realization(
            tg, foreign_price_eur_mwh=20.0, tau=0.0,
            ntc_import_gw=20.0, ntc_export_gw=0.0, ci=50.0)
        load = np.full(tg.n, 0.6)
        result = dispatch_year([dirty], load, real)
        m = result.ic_metrics
        assert m.total_co2_benefit_tons[0] > 0
        assert m.co2_benefit_tons_qh[0].min() >= -1e-9

    def test_co2_benefit_negative_when_import_is_dirtier(self, tg, co2):
        """Mirror case: importing from a CI=900 g/kWh market against a
        cleaner domestic mix (gas at \u2248364 g/kWh) must give a
        negative total benefit — net emissions increase.
        """
        gas_like = _quick_gen("gas", 40.0, vom=30.0,
                              efficiency=0.55, emission_factor=0.20)
        gas_like.prepare_run(tg, np.random.default_rng(0), co2)
        real = self._make_realization(
            tg, foreign_price_eur_mwh=10.0, tau=0.0,
            ntc_import_gw=20.0, ntc_export_gw=0.0, ci=900.0)
        load = np.full(tg.n, 0.6)
        result = dispatch_year([gas_like], load, real)
        assert result.ic_metrics.total_co2_benefit_tons[0] < 0

    def test_hours_and_energy_aggregates_consistent(self, tg, co2):
        """``import_hours + export_hours <= 8760`` and
        ``import_energy_mwh`` matches the manual sum of the import power
        row (in MWh). Exposes integration bugs in the aggregation block.
        """
        g = _quick_gen("g", 40.0, vom=30.0)
        g.prepare_run(tg, np.random.default_rng(0), co2)
        real = self._make_realization(
            tg, foreign_price_eur_mwh=25.0, tau=0.0,
            ntc_import_gw=20.0, ntc_export_gw=10.0)
        load = np.full(tg.n, 0.3)
        result = dispatch_year([g], load, real)
        m = result.ic_metrics
        assert m.import_hours[0] + m.export_hours[0] <= 8760.0 + 1e-9

        from energy_sim.config import P_BASE
        import_row = result.power[-1]
        expected_mwh = import_row.sum() * P_BASE * 1000.0 * 0.25
        assert m.import_energy_mwh[0] == pytest.approx(expected_mwh,
                                                        rel=1e-9)

    def test_marginal_ci_inside_fleet_envelope(self, tg, co2):
        """Load-weighted marginal CI must lie between 0 and the dirtiest
        unit's CI at every quarter-hour where the fleet is online.

        A weighted mean of non-negative values with non-negative weights
        cannot exceed the maximum component CI, nor drop below zero.
        Violating this invariant would signal a shape mismatch in the
        vectorised computation.
        """
        clean = _quick_gen("clean", 20.0, vom=10.0,
                           efficiency=1.0, emission_factor=0.0)
        dirty = _quick_gen("dirty", 20.0, vom=60.0,
                           efficiency=0.40, emission_factor=0.34)
        for g in [clean, dirty]:
            g.prepare_run(tg, np.random.default_rng(0), co2)
        real = self._make_realization(
            tg, foreign_price_eur_mwh=30.0, tau=0.0,
            ntc_import_gw=5.0, ntc_export_gw=0.0, ci=200.0)
        load = np.full(tg.n, 0.5)
        result = dispatch_year([clean, dirty], load, real)
        ci = result.ic_metrics.domestic_marginal_ci_g_per_kwh
        assert ci.min() >= -1e-9
        # Dirtiest unit: 0.34/0.40 * 1000 = 850 gCO\u2082/kWh_e.
        assert ci.max() <= 850.0 + 1e-6


class TestStorageDispatch:
    """Invariants of the Phase 4 battery storage dispatch.

    Validates SOC bounds, power limits, energy conservation (modulo
    round-trip losses and self-discharge), backward compatibility when
    no storage is supplied, and the sign convention for revenue under
    a clear price spread.
    """

    def _bess(self, **kwargs):
        """Build a minimal :class:`StorageUnit` with overridable defaults."""
        from energy_sim.storage import StorageUnit
        defaults = dict(
            name='bess', energy_capacity_gwh=4.0, power_capacity_gw=2.0,
            efficiency_roundtrip=0.88, soc_min_frac=0.1, soc_max_frac=0.9,
            initial_soc_frac=0.5, self_discharge_per_day=0.0,
            h_synthetic=4.0, inertia_soc_margin=0.02,
        )
        defaults.update(kwargs)
        return StorageUnit(**defaults)

    def test_no_storage_is_backward_compatible(self, tg, co2):
        """Dispatch with ``storage_units=None`` (or ``[]``) must be
        byte-identical to the previous three-phase dispatch. This is the
        primary backward-compatibility contract.
        """
        g = _quick_gen("g", 40.0, vom=50.0)
        g.prepare_run(tg, np.random.default_rng(0), co2)
        load = np.full(tg.n, 0.5)
        r1 = dispatch_year([g], load, storage_units=None)
        r2 = dispatch_year([g], load, storage_units=[])
        np.testing.assert_array_equal(r1.marginal_price, r2.marginal_price)
        np.testing.assert_array_equal(r1.power, r2.power)
        assert r1.storage_power_pu.shape == (0, tg.n)
        assert r1.storage_soc.shape == (0, tg.n)
        assert r1.storage_names == []

    def test_soc_stays_inside_operational_band(self, tg, co2):
        """SOC must never leave ``[soc_min_frac, soc_max_frac]`` at any
        timestep, regardless of the price signal. Overshooting the upper
        bound or diving below the lower bound indicates a bug in the
        power-clipping logic.
        """
        g = _quick_gen("g", 40.0, vom=50.0)
        g.prepare_run(tg, np.random.default_rng(0), co2)
        load = np.full(tg.n, 0.5)
        b = self._bess()
        result = dispatch_year([g], load, storage_units=[b])
        soc = result.storage_soc[0]
        assert soc.min() >= b.soc_min_frac - 1e-9
        assert soc.max() <= b.soc_max_frac + 1e-9

    def test_power_within_rated_capacity(self, tg, co2):
        """Absolute value of storage AC power must not exceed
        ``power_capacity_pu`` at any timestep. Positive = discharge,
        negative = charge; both must be capped.
        """
        g = _quick_gen("g", 40.0, vom=50.0)
        g.prepare_run(tg, np.random.default_rng(0), co2)
        load = np.full(tg.n, 0.5)
        b = self._bess()
        result = dispatch_year([g], load, storage_units=[b])
        abs_pwr = np.abs(result.storage_power_pu[0])
        assert abs_pwr.max() <= b.power_capacity_pu + 1e-9

    def test_energy_conservation(self, tg, co2):
        """Total energy balance: energy charged in × eta_charge should
        equal energy discharged out / eta_discharge plus the net SOC
        change plus losses. Self-discharge is disabled here so the only
        losses are round-trip.
        """
        g = _quick_gen("g", 40.0, vom=50.0)
        g.prepare_run(tg, np.random.default_rng(0), co2)
        load = np.full(tg.n, 0.5)
        b = self._bess(self_discharge_per_day=0.0)
        result = dispatch_year([g], load, storage_units=[b])
        sp = result.storage_power_pu[0]  # + discharge, - charge
        soc = result.storage_soc[0]

        charge_energy_pu_h = (-sp[sp < 0]).sum() * 0.25
        discharge_energy_pu_h = sp[sp > 0].sum() * 0.25
        soc_change_pu_h = (soc[-1] - b.initial_soc_frac) * b.energy_capacity_pu_h
        stored_in = charge_energy_pu_h * b.eta_charge
        taken_out = discharge_energy_pu_h / b.eta_discharge
        # stored_in = taken_out + soc_change (what's left in the battery)
        assert stored_in == pytest.approx(
            taken_out + soc_change_pu_h, rel=0.02, abs=1e-6)

    def test_storage_changes_marginal_price(self, tg, co2):
        """With a non-trivial price spread, the battery must alter at
        least some marginal prices — otherwise Phase 4 had no effect.

        The load alternates near the boundary where the cheap generator
        saturates (20 GW / 60 GW = 0.333 pu). Storage power (2 GW =
        0.033 pu) is enough to push some timesteps across the threshold:
        charging at 0.31 pu raises effective load above 0.333 (price
        jumps from 20 to 100), discharging at 0.36 pu reduces it below
        0.333 (price drops from 100 to 20).
        """
        cheap = _quick_gen("cheap", 20.0, vom=20.0)
        expensive = _quick_gen("expensive", 40.0, vom=100.0)
        for g in [cheap, expensive]:
            g.prepare_run(tg, np.random.default_rng(0), co2)
        # Load oscillates near the threshold.
        load = np.where(np.arange(tg.n) % 2 == 0, 0.31, 0.36)
        r_no_batt = dispatch_year([cheap, expensive], load)
        b = self._bess()
        r_batt = dispatch_year([cheap, expensive], load, storage_units=[b])
        # At least some timesteps must differ.
        diff = r_no_batt.marginal_price - r_batt.marginal_price
        assert np.count_nonzero(np.abs(diff) > 0.01) > 0

    def test_synthetic_inertia_improves_h_system(self, tg, co2):
        """A BESS with h_synthetic > 0 should increase h_system on at
        least some timesteps (those where SOC is inside the band),
        compared to a dispatch without storage.
        """
        # Only non-synchronous generators → h_system will be 0 without BESS.
        solar = _quick_gen("solar", 40.0, vom=0.0, h_inertia=0.0,
                           min_stable_pct=0.0)
        solar.prepare_run(tg, np.random.default_rng(0), co2)
        load = np.full(tg.n, 0.3)
        r_no = dispatch_year([solar], load)
        b = self._bess(h_synthetic=5.0)
        r_batt = dispatch_year([solar], load, storage_units=[b])
        # Without storage, h_system is all zeros (no sync gen).
        assert r_no.h_system.max() < 0.01
        # With storage, some timesteps should show synthetic inertia.
        assert r_batt.h_system.max() > 0.1

    def test_result_shapes(self, tg, co2):
        """Storage output arrays must have expected shapes."""
        g = _quick_gen("g", 40.0, vom=50.0)
        g.prepare_run(tg, np.random.default_rng(0), co2)
        load = np.full(tg.n, 0.5)
        b = self._bess()
        result = dispatch_year([g], load, storage_units=[b])
        assert result.storage_power_pu.shape == (1, tg.n)
        assert result.storage_soc.shape == (1, tg.n)
        assert result.storage_names == ['bess']
