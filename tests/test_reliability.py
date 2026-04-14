"""Tests for energy_sim.reliability (two-state alternating renewal model).

Validates the reliability abstractions used by interconnections:
:class:`PerfectReliability` (null model), :class:`TwoStateMarkovReliability`
(exponential MTTF + lognormal MTTR), the alternative constructors
``from_availability`` / ``from_technology``, the preset dictionary, and
the :func:`build_reliability_model` factory.

Statistical assertions use loose tolerances because a single
35040-timestep path is a noisy estimator of the stationary availability;
multiple-run averaging is used where a tighter bound is asserted.
"""

import numpy as np
import pytest

from energy_sim.models import TimeGrid
from energy_sim.reliability import (
    PerfectReliability,
    TwoStateMarkovReliability,
    TECHNOLOGY_PRESETS,
    build_reliability_model,
)


# ── PerfectReliability ─────────────────────────────────────────────────


class TestPerfectReliability:
    """Null model that always returns ones."""

    def test_returns_ones_array(self, time_grid):
        """Every entry must be exactly 1.0 regardless of RNG input."""
        model = PerfectReliability()
        a = model.sample_availability_path(time_grid, np.random.default_rng(0))
        assert a.shape == (time_grid.n,)
        assert np.all(a == 1.0)

    def test_ignores_rng(self, time_grid):
        """Two different seeds must produce identical (ones) paths."""
        model = PerfectReliability()
        a1 = model.sample_availability_path(time_grid, np.random.default_rng(1))
        a2 = model.sample_availability_path(time_grid, np.random.default_rng(2))
        assert np.array_equal(a1, a2)


# ── TwoStateMarkovReliability validation ───────────────────────────────


class TestTwoStateValidation:
    """Parameter-range validation in __post_init__."""

    @pytest.mark.parametrize("field,value", [
        ('mttf_hours', 0),
        ('mttf_hours', -1),
        ('mttr_median_hours', 0),
        ('mttr_sigma_log', -0.1),
        ('total_fault_probability', -0.1),
        ('total_fault_probability', 1.1),
        ('partial_derate_factor', -0.1),
        ('partial_derate_factor', 1.1),
    ])
    def test_invalid_parameters_rejected(self, field, value):
        """Out-of-range values must raise ValueError at construction.

        Each parameter has a physically meaningful domain (positive
        mean times, probabilities in ``[0, 1]``, non-negative shape); the
        validator defends against accidental sign errors and typos.
        """
        kwargs = dict(mttf_hours=1000, mttr_median_hours=24,
                      mttr_sigma_log=1.0, total_fault_probability=0.5,
                      partial_derate_factor=0.5)
        kwargs[field] = value
        with pytest.raises(ValueError):
            TwoStateMarkovReliability(**kwargs)


# ── from_availability constructor ──────────────────────────────────────


class TestFromAvailability:
    """Derivation of MTTF from target availability + MTTR mean."""

    def test_availability_range_enforced(self):
        """``availability`` outside ``(0, 1)`` must raise."""
        with pytest.raises(ValueError):
            TwoStateMarkovReliability.from_availability(0.0, mttr_median_hours=10)
        with pytest.raises(ValueError):
            TwoStateMarkovReliability.from_availability(1.0, mttr_median_hours=10)

    def test_derived_mttf_matches_analytical_formula(self):
        """MTTF must equal ``MTTR_mean · A / (1 - A)`` with the
        ``MTTR_mean = median · exp(σ²/2)`` conversion applied.

        This is the core of the ``from_availability`` constructor and
        what makes it usable by operators who think in availability, not
        arrival rates.
        """
        A = 0.99
        median = 24.0
        sigma = 1.0
        mttr_mean = median * np.exp(sigma ** 2 / 2)
        expected_mttf = mttr_mean * A / (1 - A)

        m = TwoStateMarkovReliability.from_availability(
            availability=A, mttr_median_hours=median, mttr_sigma_log=sigma)
        assert m.mttf_hours == pytest.approx(expected_mttf)

    @pytest.mark.slow
    def test_empirical_availability_matches_target(self, time_grid):
        """Averaging many sample paths must recover the target availability.

        Generates 30 year-long paths and checks the mean availability is
        within ±0.01 of the target 0.98. Tight because we average over
        horizon × runs samples.
        """
        model = TwoStateMarkovReliability.from_availability(
            availability=0.98, mttr_median_hours=24.0, mttr_sigma_log=0.8,
            total_fault_probability=1.0)  # no partial → unambiguous
        rng = np.random.default_rng(2024)
        samples = [model.sample_availability_path(time_grid, rng).mean()
                   for _ in range(30)]
        assert abs(np.mean(samples) - 0.98) < 0.01


# ── from_technology constructor + presets ──────────────────────────────


class TestFromTechnology:
    """Preset lookup and override mechanism."""

    def test_preset_fields_copied(self):
        """The returned instance must have the preset's parameter values."""
        m = TwoStateMarkovReliability.from_technology('overhead_ac')
        preset = TECHNOLOGY_PRESETS['overhead_ac']
        assert m.mttf_hours == preset['mttf_hours']
        assert m.mttr_median_hours == preset['mttr_median_hours']

    def test_overrides_replace_preset_values(self):
        """Keyword overrides must take precedence over preset defaults."""
        m = TwoStateMarkovReliability.from_technology(
            'overhead_ac', mttr_median_hours=999.0)
        assert m.mttr_median_hours == 999.0
        # Untouched fields still follow the preset
        assert m.mttf_hours == TECHNOLOGY_PRESETS['overhead_ac']['mttf_hours']

    def test_unknown_technology_raises(self):
        """Unknown preset key must raise with the list of valid keys."""
        with pytest.raises(ValueError, match="Unknown technology preset"):
            TwoStateMarkovReliability.from_technology('unobtanium_cable')


# ── sample_availability_path behavior ──────────────────────────────────


class TestSamplePath:
    """Outcomes of the alternating renewal simulation."""

    def test_path_values_in_unit_interval(self, time_grid):
        """All values in the returned path must be in ``[0, 1]``."""
        model = TwoStateMarkovReliability.from_technology('submarine_cable_hvdc')
        a = model.sample_availability_path(time_grid, np.random.default_rng(0))
        assert a.min() >= 0.0
        assert a.max() <= 1.0

    def test_no_faults_when_mttf_much_larger_than_horizon(self, time_grid):
        """An MTTF several orders of magnitude above the horizon must
        produce a (nearly always) ones path — validates the arrival
        process doesn't fire spuriously.
        """
        model = TwoStateMarkovReliability(
            mttf_hours=1e9, mttr_median_hours=10.0)
        a = model.sample_availability_path(time_grid, np.random.default_rng(1))
        # Allow at most one brief outage from the first exponential draw
        assert (a == 1.0).mean() > 0.999

    def test_partial_derate_value_is_used(self, time_grid):
        """When every fault is partial, the derate factor must appear in
        the path as a distinct (non-zero, non-one) level.
        """
        model = TwoStateMarkovReliability(
            mttf_hours=100, mttr_median_hours=10.0,
            total_fault_probability=0.0,  # always partial
            partial_derate_factor=0.5)
        a = model.sample_availability_path(time_grid, np.random.default_rng(3))
        unique = set(np.round(a, 3))
        assert 0.5 in unique
        # No total outage should have been used
        assert 0.0 not in unique


# ── Factory ────────────────────────────────────────────────────────────


class TestFactory:
    """Dispatch on the ``type`` key of the config dict."""

    def test_perfect_type_returns_perfect(self):
        """``type='perfect'`` returns a :class:`PerfectReliability`."""
        m = build_reliability_model({'type': 'perfect'})
        assert isinstance(m, PerfectReliability)

    def test_perfect_rejects_extra_keys(self):
        """``type='perfect'`` with stray parameters must raise to catch typos."""
        with pytest.raises(ValueError):
            build_reliability_model({'type': 'perfect', 'mttf_hours': 100})

    def test_explicit_type_forwards_params(self):
        """``type='explicit'`` forwards keys to the direct constructor."""
        m = build_reliability_model({
            'type': 'explicit', 'mttf_hours': 1000, 'mttr_median_hours': 24})
        assert m.mttf_hours == 1000
        assert m.mttr_median_hours == 24

    def test_availability_type_dispatches_correctly(self):
        """``type='availability'`` calls the mean-MTTR derivation path."""
        m = build_reliability_model({
            'type': 'availability', 'availability': 0.99,
            'mttr_median_hours': 24})
        # For σ_log=1.0, mean = 24·exp(0.5) ≈ 39.58; MTTF = mean·99
        assert m.mttf_hours == pytest.approx(24 * np.exp(0.5) * 99, rel=1e-6)

    def test_technology_type_dispatches_correctly(self):
        """``type='technology'`` uses the preset lookup path."""
        m = build_reliability_model({
            'type': 'technology', 'tech': 'overhead_ac'})
        assert m.mttf_hours == TECHNOLOGY_PRESETS['overhead_ac']['mttf_hours']

    def test_missing_type_raises(self):
        """Config without a ``type`` key must raise."""
        with pytest.raises(ValueError, match="missing 'type'"):
            build_reliability_model({'availability': 0.99, 'mttr_median_hours': 24})

    def test_unknown_type_raises(self):
        """Unknown ``type`` value must raise with the list of valid options."""
        with pytest.raises(ValueError, match="Unknown reliability type"):
            build_reliability_model({'type': 'quantum'})
