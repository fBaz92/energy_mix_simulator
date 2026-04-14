"""Tests for energy_sim.interconnections (cross-border abstraction).

Covers :class:`Interconnection` validation, :meth:`realize` (path
generation), :class:`VirtualImportGenerator` duck-typing to the dispatch
generator interface, the factory :func:`build_interconnections_from_config`,
and the end-to-end helper :func:`realize_interconnections` including RNG
independence and price-area sharing.
"""

import numpy as np
import pytest

from energy_sim.config import P_PEAK_GW
from energy_sim.generators import FuelPriceModel
from energy_sim.interconnections import (
    Interconnection,
    InterconnectionRealization,
    VirtualImportGenerator,
    build_coupling_for_interconnections,
    build_interconnections_from_config,
    realize_interconnections,
)
from energy_sim.models import TimeGrid
from energy_sim.price_areas import PriceArea, PriceAreaCoupling
from energy_sim.reliability import PerfectReliability, TwoStateMarkovReliability


# ── Helpers ────────────────────────────────────────────────────────────


def _basic_link(name='IT-FR', ntc_import=3.0, ntc_export=2.0, tau=3.0,
                rel=None, seasonal=None):
    """Compact factory for an :class:`Interconnection` in tests."""
    return Interconnection(
        name=name, price_area_name='FR',
        ntc_import_gw=ntc_import, ntc_export_gw=ntc_export,
        transport_cost_eur_mwh=tau,
        reliability_model=rel or PerfectReliability(),
        seasonal_ntc_factor_monthly=seasonal,
    )


# ── Interconnection validation ─────────────────────────────────────────


class TestInterconnectionValidation:
    """Construction-time guards on the static link definition."""

    @pytest.mark.parametrize("kwargs", [
        {'ntc_import_gw': -0.1},
        {'ntc_export_gw': -0.1},
        {'transport_cost_eur_mwh': -0.1},
    ])
    def test_negative_fields_rejected(self, kwargs):
        """Any negative physical parameter must raise at construction."""
        base = dict(name='L', price_area_name='FR', ntc_import_gw=1.0,
                    ntc_export_gw=1.0, transport_cost_eur_mwh=3.0)
        base.update(kwargs)
        with pytest.raises(ValueError):
            Interconnection(**base)

    def test_seasonal_profile_shape_validated(self):
        """Seasonal factor array must have length 12 (one per month)."""
        with pytest.raises(ValueError, match="length 12"):
            _basic_link(seasonal=np.ones(11))

    def test_seasonal_profile_negative_values_rejected(self):
        """Negative seasonal multipliers are nonsensical and must raise."""
        arr = np.ones(12)
        arr[0] = -0.1
        with pytest.raises(ValueError, match=">= 0"):
            _basic_link(seasonal=arr)


# ── Realization paths ──────────────────────────────────────────────────


class TestRealize:
    """Time-varying path generation in :meth:`Interconnection.realize`."""

    def test_srmc_and_export_floor_are_consistent_with_foreign_price(self,
                                                                      time_grid):
        """import_srmc = foreign+τ and export_floor = foreign-τ by identity."""
        link = _basic_link(tau=4.0)
        foreign = np.full(time_grid.n, 50.0)
        real = link.realize(foreign, 200.0, time_grid, np.random.default_rng(0))
        assert np.allclose(real.import_srmc_path, 54.0)
        assert np.allclose(real.export_floor_path, 46.0)

    def test_perfect_reliability_gives_flat_ntc(self, time_grid):
        """With PerfectReliability the NTC path is constant at the nominal
        per-unit value — no seasonal modulation, no outages.
        """
        link = _basic_link(ntc_import=6.0)
        real = link.realize(np.full(time_grid.n, 50.0), 0.0,
                            time_grid, np.random.default_rng(0))
        expected = 6.0 / P_PEAK_GW
        assert np.allclose(real.ntc_import_pu_path, expected)

    def test_seasonal_factor_applied_per_month(self, time_grid):
        """Quarter-hour NTC paths pick up the seasonal factor of their month.

        Uses a profile with distinct factors per month to verify the
        quarter-hour expansion follows ``time_grid.month - 1`` correctly.
        """
        seasonal = np.linspace(0.5, 1.5, 12)  # 12 distinct values
        link = _basic_link(seasonal=seasonal)
        real = link.realize(np.full(time_grid.n, 50.0), 0.0,
                            time_grid, np.random.default_rng(0))

        # Every quarter-hour's NTC must equal nominal · seasonal[month-1]
        nominal_pu = link.ntc_import_gw / P_PEAK_GW
        expected = nominal_pu * seasonal[time_grid.month - 1]
        assert np.allclose(real.ntc_import_pu_path, expected)

    def test_availability_multiplier_derates_ntc(self, time_grid):
        """A faulted path must produce NTC strictly below the nominal
        at least somewhere — otherwise the reliability model would be
        a no-op and the test infrastructure broken.
        """
        link = _basic_link(
            rel=TwoStateMarkovReliability(
                mttf_hours=50.0,   # frequent faults
                mttr_median_hours=24.0,
                total_fault_probability=1.0,  # total outage
            ),
        )
        real = link.realize(np.full(time_grid.n, 50.0), 0.0,
                            time_grid, np.random.default_rng(7))
        assert real.ntc_import_pu_path.min() < link.ntc_import_pu - 1e-9
        # At least some quarter-hour should have zero NTC
        assert (real.ntc_import_pu_path < 1e-9).any()


# ── VirtualImportGenerator duck-typing ─────────────────────────────────


class TestVirtualImportGenerator:
    """The dispatch-facing adapter over a realization."""

    def _make(self, time_grid):
        foreign = np.full(time_grid.n, 60.0)
        link = _basic_link(ntc_import=3.0, tau=2.0)
        return link.realize(foreign, 100.0, time_grid,
                            np.random.default_rng(0)).as_virtual_import_generator()

    def test_exposes_expected_interface(self, time_grid):
        """The adapter must expose every attribute read by dispatch_year.

        Keeping this test ensures future refactors of the dispatch engine
        don't silently skip one of the duck-typed access points.
        """
        vg = self._make(time_grid)
        # Attributes
        assert isinstance(vg.name, str) and vg.name.startswith('import_')
        assert vg.gen_type == 'import'
        assert vg.h_inertia == 0.0
        assert vg.is_synchronous is False
        assert vg.emission_factor == 0.0
        assert vg.efficiency == 1.0
        assert vg.capacity_pu == pytest.approx(3.0 / P_PEAK_GW)
        # Methods
        assert vg.min_stable_power_pu() == 0.0
        assert vg.srmc().shape == (time_grid.n,)
        assert vg.available_power_pu().shape == (time_grid.n,)

    def test_srmc_equals_foreign_price_plus_tau(self, time_grid):
        """The SRMC path is ``foreign + τ`` — the price at which the link
        competes in the merit order.
        """
        vg = self._make(time_grid)
        assert np.allclose(vg.srmc(), 60.0 + 2.0)


# ── Factory from config ────────────────────────────────────────────────


class TestFactory:
    """Build links and couplings from plain-dict configs."""

    CFG = {
        'IT-FR': {
            'price_area': 'FR', 'ntc_import_gw': 3.0, 'ntc_export_gw': 2.0,
            'transport_cost_eur_mwh': 3.0,
            'seasonal_ntc_factor_monthly': None,
            'reliability': {'type': 'perfect'},
        },
        'IT-GR': {
            'price_area': 'GR', 'ntc_import_gw': 0.5, 'ntc_export_gw': 0.5,
            'transport_cost_eur_mwh': 5.0,
            'seasonal_ntc_factor_monthly': None,
            'reliability': {'type': 'technology',
                             'tech': 'submarine_cable_hvdc'},
        },
    }

    AREAS_CFG = {
        'FR': {'mu': 45, 'sigma': 12, 'theta': 0.05,
               'carbon_intensity_g_per_kwh': 50},
        'GR': {'mu': 70, 'sigma': 18, 'theta': 0.05,
               'carbon_intensity_g_per_kwh': 430},
        'AT': {'mu': 55, 'sigma': 14, 'theta': 0.05,
               'carbon_intensity_g_per_kwh': 200},  # unreferenced on purpose
    }

    def test_build_links_preserves_order_and_parameters(self):
        """Links are built in insertion order and parameters are copied."""
        links = build_interconnections_from_config(self.CFG)
        names = [l.name for l in links]
        assert names == ['IT-FR', 'IT-GR']
        assert links[0].ntc_import_gw == 3.0
        assert links[1].transport_cost_eur_mwh == 5.0

    def test_enable_faults_false_forces_perfect_reliability(self):
        """With ``enable_faults=False`` every link uses PerfectReliability
        regardless of its config entry — this is the master switch.
        """
        links = build_interconnections_from_config(self.CFG, enable_faults=False)
        for l in links:
            assert isinstance(l.reliability_model, PerfectReliability)

    def test_coupling_covers_only_referenced_areas(self):
        """The subset-aware helper must exclude areas no link references."""
        links = build_interconnections_from_config(self.CFG)
        cpl = build_coupling_for_interconnections(
            links, price_areas_cfg=self.AREAS_CFG)
        names = sorted(a.name for a in cpl.areas)
        assert names == ['FR', 'GR']      # AT intentionally dropped


# ── realize_interconnections end-to-end ────────────────────────────────


class TestRealizeInterconnections:
    """End-to-end resolution of the per-MC-run state."""

    def _coupling_and_links(self):
        area_fr = PriceArea(
            name='FR', price_model=FuelPriceModel(mu=45, sigma=12, theta=0.05),
            carbon_intensity_g_per_kwh=50.0)
        area_ch = PriceArea(
            name='CH', price_model=FuelPriceModel(mu=50, sigma=10, theta=0.05),
            carbon_intensity_g_per_kwh=30.0)
        cpl = PriceAreaCoupling(
            areas=[area_fr, area_ch],
            correlations={('FR', 'CH'): 0.7},
        )
        links = [
            Interconnection(name='A', price_area_name='FR',
                            ntc_import_gw=3.0, ntc_export_gw=2.0,
                            transport_cost_eur_mwh=3.0),
            Interconnection(name='B', price_area_name='FR',     # same area
                            ntc_import_gw=1.0, ntc_export_gw=1.0,
                            transport_cost_eur_mwh=2.0),
            Interconnection(name='C', price_area_name='CH',
                            ntc_import_gw=6.0, ntc_export_gw=3.0,
                            transport_cost_eur_mwh=2.5),
        ]
        return cpl, links

    def test_links_sharing_an_area_see_identical_foreign_price(self, time_grid):
        """Two interconnections pointing to the same PriceArea must share
        the exact same realized foreign price path — otherwise we would
        be modelling two independent samples of the same market.
        """
        cpl, links = self._coupling_and_links()
        reals = realize_interconnections(
            links, cpl, time_grid,
            np.random.default_rng(1), np.random.default_rng(2))
        assert np.array_equal(reals[0].foreign_price, reals[1].foreign_price)
        # ... and different from the other area
        assert not np.array_equal(reals[0].foreign_price, reals[2].foreign_price)

    def test_rng_separation_is_honoured(self, time_grid):
        """Swapping the faults RNG must change the availability path but
        NOT the foreign price path — the two stochastic sources must be
        independent, enabling clean sensitivity studies.
        """
        cpl, links = self._coupling_and_links()
        # Use a reliability with faults so availability varies
        link = Interconnection(
            name='L', price_area_name='FR', ntc_import_gw=3.0,
            ntc_export_gw=2.0, transport_cost_eur_mwh=3.0,
            reliability_model=TwoStateMarkovReliability(
                mttf_hours=100.0, mttr_median_hours=24.0),
        )
        reals_a = realize_interconnections(
            [link], cpl, time_grid,
            np.random.default_rng(10), np.random.default_rng(100))
        reals_b = realize_interconnections(
            [link], cpl, time_grid,
            np.random.default_rng(10), np.random.default_rng(999))
        assert np.array_equal(reals_a[0].foreign_price,
                              reals_b[0].foreign_price)
        assert not np.array_equal(reals_a[0].availability,
                                   reals_b[0].availability)

    def test_unknown_price_area_raises(self, time_grid):
        """A link pointing to an area not present in the coupling must raise."""
        cpl, _ = self._coupling_and_links()
        bad_link = Interconnection(
            name='X', price_area_name='ZZ',
            ntc_import_gw=1.0, ntc_export_gw=1.0,
            transport_cost_eur_mwh=0.0)
        with pytest.raises(KeyError, match="unknown"):
            realize_interconnections(
                [bad_link], cpl, time_grid,
                np.random.default_rng(0), np.random.default_rng(1))
