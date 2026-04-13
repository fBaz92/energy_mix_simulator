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
    COAL_SCENARIOS,
    CO2_SCENARIOS,
    WEEKDAY_LOAD_FACTORS,
    HOLIDAY_LOAD_FACTOR,
    ITALIAN_HOLIDAYS_DOY,
    DEFAULT_LOAD_NOISE_SIGMA,
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


class TestWeekdayLoadFactors:
    """Verify structure and values of the WEEKDAY_LOAD_FACTORS dictionary."""

    def test_has_7_days(self):
        """WEEKDAY_LOAD_FACTORS must have entries for days 0 (Monday) through 6 (Sunday)."""
        assert set(WEEKDAY_LOAD_FACTORS.keys()) == set(range(7))

    def test_weekdays_are_one(self):
        """Monday through Friday must have load factor 1.0 (full working-day demand)."""
        for d in range(5):
            assert WEEKDAY_LOAD_FACTORS[d] == 1.0

    def test_weekend_reduced(self):
        """Saturday and Sunday must have load factors below 1.0 (reduced demand)."""
        assert WEEKDAY_LOAD_FACTORS[5] < 1.0, "Saturday must be < 1.0"
        assert WEEKDAY_LOAD_FACTORS[6] < 1.0, "Sunday must be < 1.0"

    def test_sunday_lower_than_saturday(self):
        """Sunday demand must be lower than Saturday (less commercial activity)."""
        assert WEEKDAY_LOAD_FACTORS[6] < WEEKDAY_LOAD_FACTORS[5]


class TestHolidayConfig:
    """Verify structure and values of Italian holiday configuration."""

    def test_holiday_factor_less_than_one(self):
        """HOLIDAY_LOAD_FACTOR must be less than 1.0 (holidays reduce demand)."""
        assert 0 < HOLIDAY_LOAD_FACTOR < 1.0

    def test_holidays_within_year(self):
        """All holiday day-of-year indices must be in valid range [0, 364]."""
        for doy in ITALIAN_HOLIDAYS_DOY:
            assert 0 <= doy <= 364, f"Holiday DOY {doy} out of range"

    def test_holidays_unique(self):
        """No duplicate entries in the holiday calendar."""
        assert len(ITALIAN_HOLIDAYS_DOY) == len(set(ITALIAN_HOLIDAYS_DOY))

    def test_contains_key_holidays(self):
        """Must include New Year (0), Christmas (358), and Ferragosto (226)."""
        assert 0 in ITALIAN_HOLIDAYS_DOY, "Missing New Year's Day"
        assert 358 in ITALIAN_HOLIDAYS_DOY, "Missing Christmas Day"
        assert 226 in ITALIAN_HOLIDAYS_DOY, "Missing Ferragosto"

    def test_at_least_8_holidays(self):
        """Italy has at least 8 fixed-date public holidays."""
        assert len(ITALIAN_HOLIDAYS_DOY) >= 8


class TestDefaultLoadNoise:
    """Verify the default load noise sigma constant."""

    def test_positive(self):
        """DEFAULT_LOAD_NOISE_SIGMA must be positive."""
        assert DEFAULT_LOAD_NOISE_SIGMA > 0

    def test_reasonable_range(self):
        """DEFAULT_LOAD_NOISE_SIGMA should be between 0.01 and 0.10 for realism."""
        assert 0.01 <= DEFAULT_LOAD_NOISE_SIGMA <= 0.10


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
        """ITALIAN_MIX must contain gas, coal, solar, wind, nuclear, and hydro_mustrun."""
        expected = {'gas', 'coal', 'solar', 'wind', 'nuclear', 'hydro_mustrun'}
        assert set(ITALIAN_MIX.keys()) == expected


class TestCoalScenarios:
    """Verify structural completeness of the COAL_SCENARIOS configuration."""

    def test_has_expected_scenarios(self):
        """COAL_SCENARIOS must contain base, tension, and crisis scenarios."""
        expected = {'base', 'tension', 'crisis'}
        assert set(COAL_SCENARIOS.keys()) == expected

    def test_scenario_keys(self):
        """Each coal scenario must have mu, sigma, and theta parameters."""
        for label, params in COAL_SCENARIOS.items():
            assert set(params.keys()) == {'mu', 'sigma', 'theta'}, (
                f"Coal scenario '{label}' has unexpected keys"
            )


class TestCO2Scenarios:
    """Verify structural completeness of the CO2_SCENARIOS configuration."""

    def test_has_expected_scenarios(self):
        """CO2_SCENARIOS must contain base, low, and high scenarios."""
        expected = {'base', 'low', 'high'}
        assert set(CO2_SCENARIOS.keys()) == expected

    def test_scenario_keys(self):
        """Each CO2 scenario must have mu, sigma, and theta parameters."""
        for label, params in CO2_SCENARIOS.items():
            assert set(params.keys()) == {'mu', 'sigma', 'theta'}, (
                f"CO2 scenario '{label}' has unexpected keys"
            )

    def test_base_mu_matches_default(self):
        """The base CO2 scenario mu must match CO2_PRICE_DEFAULT (65.0 EUR/ton)."""
        from energy_sim.config import CO2_PRICE_DEFAULT
        assert CO2_SCENARIOS['base']['mu'] == CO2_PRICE_DEFAULT
