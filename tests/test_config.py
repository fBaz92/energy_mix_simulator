"""Tests for energy_sim.config constants, helper functions, and data dictionaries.

Validates that derived constants are computed correctly, that the solar
envelope function produces a physically sensible irradiance profile, that
all lookup dictionaries have the expected keys (12 months, 24 hours), and
that the ITALIAN_MIX configuration contains all required parameters for
every technology.
"""

from energy_sim.config import (
    QUARTERS_PER_DAY,
    QUARTERS_PER_YEAR,
    MONTHLY_LOAD_FACTORS,
    HOURLY_LOAD_FACTORS,
    MONTHLY_SOLAR_FACTORS,
    HOURLY_SOLAR_ENVELOPE,
    MONTHLY_WIND_LAMBDA,
    CLOUD_TRANSITION,
    ITALIAN_MIX,
    _solar_envelope,
)


class TestDerivedConstants:
    """Verify that time-resolution constants derived from base values are correct."""

    def test_quarters_per_day(self):
        """QUARTERS_PER_DAY must equal 4 quarters/hour * 24 hours = 96."""
        assert QUARTERS_PER_DAY == 96

    def test_quarters_per_year(self):
        """QUARTERS_PER_YEAR must equal 96 quarters/day * 365 days = 35040."""
        assert QUARTERS_PER_YEAR == 35040


class TestSolarEnvelope:
    """Verify _solar_envelope() produces a physically correct irradiance shape.

    The envelope is a Gaussian centered at hour 13 (Italian solar noon),
    hard-zeroed during night hours, and normalized to peak at 1.0.
    """

    def test_peak_at_hour_13(self):
        """The maximum irradiance must occur at hour 13 (solar noon) with value 1.0."""
        env = _solar_envelope()
        assert env[13] == 1.0

    def test_night_hours_zero(self):
        """Hours 0-5 and 21-23 must have zero irradiance (hard-zeroed night)."""
        env = _solar_envelope()
        for h in [0, 1, 2, 3, 4, 5, 21, 22, 23]:
            assert env[h] == 0.0

    def test_values_in_0_1(self):
        """All hourly irradiance values must lie in the [0, 1] range."""
        env = _solar_envelope()
        for h in range(24):
            assert 0.0 <= env[h] <= 1.0

    def test_has_24_hours(self):
        """The envelope dictionary must contain exactly keys 0 through 23."""
        env = _solar_envelope()
        assert set(env.keys()) == set(range(24))


class TestFactorDicts:
    """Verify completeness of all time-indexed lookup dictionaries.

    Each dictionary must have entries for every expected key (12 months
    1-indexed, or 24 hours 0-indexed) to avoid KeyError at runtime.
    """

    def test_monthly_load_factors_12_months(self):
        """MONTHLY_LOAD_FACTORS must have entries for months 1 through 12."""
        assert set(MONTHLY_LOAD_FACTORS.keys()) == set(range(1, 13))

    def test_hourly_load_factors_24_hours(self):
        """HOURLY_LOAD_FACTORS must have entries for hours 0 through 23."""
        assert set(HOURLY_LOAD_FACTORS.keys()) == set(range(24))

    def test_monthly_solar_factors_12_months(self):
        """MONTHLY_SOLAR_FACTORS must have entries for months 1 through 12."""
        assert set(MONTHLY_SOLAR_FACTORS.keys()) == set(range(1, 13))

    def test_hourly_solar_envelope_24_hours(self):
        """HOURLY_SOLAR_ENVELOPE must have entries for hours 0 through 23."""
        assert set(HOURLY_SOLAR_ENVELOPE.keys()) == set(range(24))

    def test_monthly_wind_lambda_12_months(self):
        """MONTHLY_WIND_LAMBDA (Weibull scale) must have entries for months 1-12."""
        assert set(MONTHLY_WIND_LAMBDA.keys()) == set(range(1, 13))

    def test_cloud_transition_12_months(self):
        """CLOUD_TRANSITION (Markov chain probabilities) must have entries for months 1-12."""
        assert set(CLOUD_TRANSITION.keys()) == set(range(1, 13))


class TestItalianMix:
    """Verify structural completeness of the ITALIAN_MIX configuration.

    Every technology must include all parameters required by the Generator
    constructor, and the expected set of technologies must be present.
    """

    REQUIRED_KEYS = {
        'capacity_gw', 'capex_per_kw', 'lifetime_years', 'vom_eur_mwh',
        'fom_eur_kw_yr', 'efficiency', 'emission_factor', 'h_inertia',
        'min_stable_pct', 'ramp_rate_pct_per_min', 'startup_cost_eur_mw',
    }

    def test_all_techs_have_required_keys(self):
        """Each technology in ITALIAN_MIX must contain all keys needed by Generator.__init__."""
        for tech, params in ITALIAN_MIX.items():
            missing = self.REQUIRED_KEYS - set(params.keys())
            assert not missing, f"{tech} missing keys: {missing}"

    def test_has_expected_technologies(self):
        """ITALIAN_MIX must contain gas, solar, wind, nuclear, and hydro_mustrun."""
        expected = {'gas', 'solar', 'wind', 'nuclear', 'hydro_mustrun'}
        assert set(ITALIAN_MIX.keys()) == expected
