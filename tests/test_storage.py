"""
Unit tests for :mod:`energy_sim.storage`.

Verifies construction-time parameter validation, derived unit conversions
(per-unit power, per-unit-hours energy, split efficiencies, compounded
self-discharge) and the SOC-gated synthetic-inertia contribution logic.
These tests exercise the :class:`~energy_sim.storage.StorageUnit` class in
isolation, before it is wired into the dispatch engine.
"""

import numpy as np
import pytest

from energy_sim.config import P_PEAK_GW, QUARTERS_PER_DAY
from energy_sim.storage import StorageUnit, build_storage_units


class TestStorageUnitValidation:
    """Construction-time parameter validation of :class:`StorageUnit`.

    The ``__post_init__`` hook must reject physically impossible or
    degenerate parameter combinations with :class:`ValueError`. Each test
    targets one failure mode so regressions point straight at the
    offending branch.
    """

    def test_valid_defaults_construct(self):
        """Default parameters must produce a valid instance.

        Guards against accidentally tightening the validation to reject
        the recommended defaults documented in ``config.py``.
        """
        u = StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0)
        assert u.name == 'b'
        assert u.efficiency_roundtrip == 0.88

    @pytest.mark.parametrize('bad_eff', [-0.1, 0.0, 1.5])
    def test_roundtrip_efficiency_bounds(self, bad_eff):
        """Round-trip efficiency must live in ``(0, 1]``.

        Zero or negative efficiency would make the SOC equations singular
        (division by ``eta_discharge`` on scale-down), and values above 1
        would violate energy conservation.
        """
        with pytest.raises(ValueError):
            StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0,
                        efficiency_roundtrip=bad_eff)

    @pytest.mark.parametrize('p', [0.0, -1.0])
    def test_non_positive_power_capacity_rejected(self, p):
        """Nameplate power must be strictly positive."""
        with pytest.raises(ValueError):
            StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=p)

    @pytest.mark.parametrize('e', [0.0, -1.0])
    def test_non_positive_energy_capacity_rejected(self, e):
        """Nameplate energy must be strictly positive."""
        with pytest.raises(ValueError):
            StorageUnit(name='b', energy_capacity_gwh=e,
                        power_capacity_gw=2.0)

    def test_soc_band_must_be_ordered(self):
        """``soc_min_frac`` must be strictly below ``soc_max_frac``.

        A degenerate band (min == max) would leave no room to store or
        release energy, making the unit inert.
        """
        with pytest.raises(ValueError):
            StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0,
                        soc_min_frac=0.5, soc_max_frac=0.5)

    def test_soc_band_must_be_inside_unit_interval(self):
        """Operational SOC band must sit inside [0, 1]."""
        with pytest.raises(ValueError):
            StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0,
                        soc_min_frac=-0.1, soc_max_frac=0.9)
        with pytest.raises(ValueError):
            StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0,
                        soc_min_frac=0.1, soc_max_frac=1.1)

    def test_initial_soc_must_be_inside_band(self):
        """Starting SOC outside the operational band is a configuration
        error — the very first quarter-hour would be clipped to the
        bound, which is never what the user intends."""
        with pytest.raises(ValueError):
            StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0,
                        soc_min_frac=0.1, soc_max_frac=0.9,
                        initial_soc_frac=0.95)

    def test_negative_self_discharge_rejected(self):
        """Negative self-discharge would mean the battery gains energy
        while idle, which is unphysical."""
        with pytest.raises(ValueError):
            StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0,
                        self_discharge_per_day=-0.01)

    def test_negative_h_synthetic_rejected(self):
        """Synthetic inertia must be non-negative; zero disables it."""
        with pytest.raises(ValueError):
            StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0, h_synthetic=-1.0)


class TestStorageUnitProperties:
    """Derived-quantity properties: unit conversions and compounded rates.

    These tests fix the numerical conventions used across the dispatch
    engine (per-unit power, per-unit-hour energy, 96-qh self-discharge
    compounding). Regressions here would silently break the SOC equation.
    """

    def test_power_capacity_pu(self):
        """``power_capacity_pu`` equals ``power_capacity_gw / P_PEAK_GW``
        to machine precision — the whole dispatch treats this as the
        dimensionless power reference.
        """
        u = StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0)
        assert u.power_capacity_pu == pytest.approx(2.0 / P_PEAK_GW)

    def test_energy_capacity_pu_h(self):
        """1 pu·h corresponds to :data:`P_PEAK_GW` GWh, so the per-unit
        energy capacity is ``energy_gwh / P_PEAK_GW``. Crucial for the
        SOC update equation which mixes p.u. power · 0.25 h with this
        denominator.
        """
        u = StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0)
        assert u.energy_capacity_pu_h == pytest.approx(4.0 / P_PEAK_GW)

    def test_eta_split_symmetric_and_matches_roundtrip(self):
        """``eta_charge × eta_discharge`` must reproduce the round-trip
        efficiency within machine precision, and the two legs must be
        equal (symmetric split convention).
        """
        u = StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0,
                        efficiency_roundtrip=0.85)
        assert u.eta_charge == pytest.approx(u.eta_discharge)
        assert (u.eta_charge * u.eta_discharge
                == pytest.approx(0.85, rel=1e-12))

    def test_self_discharge_compounds_to_daily_rate(self):
        """Per-qh self-discharge, compounded over 96 quarter-hours, must
        equal the configured per-day rate — this is the defining identity
        of the conversion formula.
        """
        u = StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0,
                        self_discharge_per_day=0.005)
        daily_from_qh = 1 - (1 - u.self_discharge_per_qh) ** QUARTERS_PER_DAY
        assert daily_from_qh == pytest.approx(0.005, rel=1e-12)

    def test_self_discharge_zero_when_disabled(self):
        """When the per-day rate is zero the per-qh rate must be exactly
        zero — avoids numerical drift from repeated (1 − ε)^(1/96).
        """
        u = StorageUnit(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0,
                        self_discharge_per_day=0.0)
        assert u.self_discharge_per_qh == 0.0


class TestInertiaContribution:
    """SOC-gated synthetic inertia contribution.

    Covers the three regimes: h_synthetic disabled, SOC in the
    operational band, and SOC at one of the bounds. Ensures the return
    tuple has the documented ``(H·S, S)`` shape so the dispatch loop
    can add it to the running sums without special-casing.
    """

    def _unit(self, **kwargs):
        defaults = dict(name='b', energy_capacity_gwh=4.0,
                        power_capacity_gw=2.0,
                        soc_min_frac=0.1, soc_max_frac=0.9,
                        inertia_soc_margin=0.02)
        defaults.update(kwargs)
        return StorageUnit(**defaults)

    def test_zero_when_h_synthetic_disabled(self):
        """A BESS with ``h_synthetic = 0`` (pure grid-following inverter)
        must contribute nothing to system inertia at any SOC.
        """
        u = self._unit(h_synthetic=0.0)
        assert u.inertia_contribution(0.5) == (0.0, 0.0)
        assert u.inertia_contribution(0.8) == (0.0, 0.0)

    def test_in_band_returns_full_contribution(self):
        """Inside the admissible band the pair must be exactly
        ``(h_synthetic × power_capacity_pu, power_capacity_pu)``.
        """
        u = self._unit(h_synthetic=4.0)
        wh, w = u.inertia_contribution(0.5)
        assert wh == pytest.approx(4.0 * u.power_capacity_pu)
        assert w == pytest.approx(u.power_capacity_pu)

    def test_zero_near_lower_bound(self):
        """Below ``soc_min_frac + inertia_soc_margin`` the BESS cannot
        respond downward (can't absorb), so no inertia credit.
        """
        u = self._unit(h_synthetic=4.0)
        # soc_min=0.1 + margin=0.02 = 0.12 is the boundary (inclusive).
        assert u.inertia_contribution(0.13) != (0.0, 0.0)
        assert u.inertia_contribution(0.11) == (0.0, 0.0)

    def test_zero_near_upper_bound(self):
        """Symmetric test on the upper bound: cannot respond upward."""
        u = self._unit(h_synthetic=4.0)
        assert u.inertia_contribution(0.88) != (0.0, 0.0)
        assert u.inertia_contribution(0.89) == (0.0, 0.0)

    def test_weight_matches_power_capacity_exactly(self):
        """The weight returned (second tuple element) must equal
        :attr:`power_capacity_pu` exactly — the dispatch adds it to the
        sum over synchronous capacities, which would be skewed by any
        scaling factor.
        """
        u = self._unit(h_synthetic=4.0, power_capacity_gw=3.0)
        _, w = u.inertia_contribution(0.5)
        assert w == pytest.approx(3.0 / P_PEAK_GW)


class TestBuildStorageUnits:
    """Factory :func:`build_storage_units` — filtering and passthrough.

    Ensures the factory cleanly handles the three configuration states
    used across the codebase: ``None``, empty dict, and populated dict.
    Zero-capacity entries must be skipped so that operators can disable
    a unit by zeroing one field without restructuring the config tree.
    """

    def test_none_returns_empty_list(self):
        """``None`` is the sentinel for 'no storage' and must return an
        empty list, not raise — matches the convention for other optional
        subsystems (interconnections, coal scenarios).
        """
        assert build_storage_units(None) == []

    def test_empty_dict_returns_empty_list(self):
        """Explicit empty dict also yields empty list."""
        assert build_storage_units({}) == []

    def test_populated_dict_builds_units_in_order(self):
        """Stable iteration order of the config dict must be reflected in
        the output list — downstream arrays index into this order.
        """
        cfg = {
            'short_duration': {'energy_capacity_gwh': 1.0,
                               'power_capacity_gw': 1.0},
            'long_duration': {'energy_capacity_gwh': 10.0,
                              'power_capacity_gw': 1.0},
        }
        units = build_storage_units(cfg)
        assert [u.name for u in units] == ['short_duration', 'long_duration']

    def test_zero_capacity_entries_skipped(self):
        """Either zero energy or zero power disables the unit cleanly."""
        cfg = {
            'ok': {'energy_capacity_gwh': 4.0, 'power_capacity_gw': 2.0},
            'no_energy': {'energy_capacity_gwh': 0.0,
                          'power_capacity_gw': 2.0},
            'no_power': {'energy_capacity_gwh': 4.0,
                         'power_capacity_gw': 0.0},
        }
        units = build_storage_units(cfg)
        assert [u.name for u in units] == ['ok']
