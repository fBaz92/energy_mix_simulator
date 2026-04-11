"""Tests for energy_sim.models (TimeGrid and LoadProfile).

Validates the temporal backbone (TimeGrid) for correct length, calendar
metadata ranges, and holiday management. Validates the multiplicative load
model (LoadProfile) for output shape, determinism, noise behavior, weekday
and holiday modifiers, peak scaling, and noise clipping bounds.
"""

import numpy as np
import pytest

from energy_sim.models import TimeGrid, LoadProfile


class TestTimeGrid:
    """Verify TimeGrid produces correct calendar metadata for 35 040 quarter-hours."""

    def test_length(self, time_grid):
        """TimeGrid must contain exactly 35 040 quarter-hour intervals (365 days)."""
        assert time_grid.n == 35040

    def test_month_range(self, time_grid):
        """Month values must span from 1 (January) to 12 (December)."""
        assert time_grid.month.min() == 1
        assert time_grid.month.max() == 12

    def test_hour_range(self, time_grid):
        """Hour values must span from 0 (midnight) to 23."""
        assert time_grid.hour.min() == 0
        assert time_grid.hour.max() == 23

    def test_day_of_year_range(self, time_grid):
        """Day-of-year values must span from 0 (Jan 1) to 364 (Dec 31)."""
        assert time_grid.day_of_year.min() == 0
        assert time_grid.day_of_year.max() == 364

    def test_first_quarter(self, time_grid):
        """The first quarter-hour (index 0) must be January 1st at midnight (month=1, hour=0, day=0)."""
        assert time_grid.month[0] == 1
        assert time_grid.hour[0] == 0
        assert time_grid.day_of_year[0] == 0

    def test_last_quarter(self, time_grid):
        """The last quarter-hour (index 35039) must be December 31st at hour 23 (month=12, hour=23, day=364)."""
        assert time_grid.month[-1] == 12
        assert time_grid.hour[-1] == 23
        assert time_grid.day_of_year[-1] == 364

    def test_set_holiday_calendar(self, time_grid):
        """Setting holidays on days 0 and 100 must mark all their quarter-hours as True
        and leave other days as False.
        """
        time_grid.set_holiday_calendar([0, 100])
        assert time_grid.is_holiday[0:96].all()  # day 0, 96 quarters
        day100_mask = time_grid.day_of_year == 100
        assert time_grid.is_holiday[day100_mask].all()
        # Non-holiday day should be False
        day50_mask = time_grid.day_of_year == 50
        assert not time_grid.is_holiday[day50_mask].any()

    def test_set_holiday_calendar_empty(self, time_grid):
        """Calling set_holiday_calendar with an empty list must clear all holiday flags,
        even if holidays were previously set.
        """
        time_grid.set_holiday_calendar([0, 100])
        time_grid.set_holiday_calendar([])
        assert not time_grid.is_holiday.any()


class TestLoadProfile:
    """Verify the multiplicative load model produces correct shapes, scaling, and noise behavior."""

    def test_output_shape(self, time_grid, rng):
        """generate() must return a 1D array of shape (35040,) matching the TimeGrid length."""
        lp = LoadProfile(time_grid)
        load = lp.generate(rng, noise_sigma=0.0)
        assert load.shape == (35040,)

    def test_deterministic_reproducible(self, time_grid):
        """With noise_sigma=0, two calls to generate() must return identical arrays
        (purely deterministic profile).
        """
        lp = LoadProfile(time_grid)
        load1 = lp.generate(noise_sigma=0.0)
        load2 = lp.generate(noise_sigma=0.0)
        np.testing.assert_array_equal(load1, load2)

    def test_noise_changes_output(self, time_grid):
        """With noise_sigma > 0, the output must differ from the deterministic profile
        due to multiplicative Gaussian noise.
        """
        lp = LoadProfile(time_grid)
        det = lp.generate(noise_sigma=0.0)
        noisy = lp.generate(np.random.default_rng(42), noise_sigma=0.05)
        assert not np.array_equal(det, noisy)

    def test_weekday_factors_modify_profile(self, time_grid):
        """Setting reduced weekday factors for Saturday (5) and Sunday (6) must change
        the load values on weekend quarter-hours compared to the base profile.
        """
        lp = LoadProfile(time_grid)
        base = lp.generate(noise_sigma=0.0)
        lp.set_weekday_factors({5: 0.7, 6: 0.6})  # Sat/Sun
        modified = lp.generate(noise_sigma=0.0)
        weekend_mask = time_grid.day_of_week >= 5
        assert not np.array_equal(base[weekend_mask], modified[weekend_mask])

    def test_holiday_factor_reduces_load(self, time_grid):
        """A holiday_factor of 0.80 must multiply load on holiday quarter-hours by exactly 0.80,
        leaving non-holiday hours unchanged.
        """
        time_grid.set_holiday_calendar([0])
        lp = LoadProfile(time_grid)
        base = lp.generate(noise_sigma=0.0)
        lp.set_holiday_factor(0.80)
        reduced = lp.generate(noise_sigma=0.0)
        day0_mask = time_grid.day_of_year == 0
        np.testing.assert_allclose(reduced[day0_mask], base[day0_mask] * 0.80)

    def test_peak_scaling(self, time_grid):
        """With p_peak_pu=0.5, no load value should exceed 0.5 p.u. since all monthly
        and hourly factors are <= 1.0.
        """
        lp = LoadProfile(time_grid, p_peak_pu=0.5)
        load = lp.generate(noise_sigma=0.0)
        assert load.max() <= 0.5 + 1e-10

    def test_noise_clipping(self, time_grid):
        """Multiplicative noise is clipped to [0.5, 1.5], so the noisy profile must
        stay within [0.5*deterministic, 1.5*deterministic] at every quarter-hour.
        """
        lp = LoadProfile(time_grid)
        det = lp.generate(noise_sigma=0.0)
        rng = np.random.default_rng(99)
        noisy = lp.generate(rng, noise_sigma=0.3)
        assert (noisy >= det * 0.5 - 1e-10).all()
        assert (noisy <= det * 1.5 + 1e-10).all()
