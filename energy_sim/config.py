"""
Global configuration and default parameters.

This module centralizes all constants, default scenarios, and system
coefficients used across the simulator. Parameters are organized by category:
time resolution, system base, Monte Carlo settings, dispatch constraints,
load/solar/wind profiles, gas scenarios, and the Italian generation mix.

All prices are in EUR/MWh (electrical) unless noted as EUR/MWh_th (thermal).
All powers are in per-unit of P_BASE (60 GW) internally; GW in config dicts.
Time resolution: quarter-hour (0.25 h). Index 0 = Jan 1 00:00.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Time resolution
# ---------------------------------------------------------------------------
QUARTERS_PER_HOUR: int = 4
"""Number of quarter-hour intervals per hour."""

HOURS_PER_DAY: int = 24
"""Number of hours per day."""

QUARTERS_PER_DAY: int = QUARTERS_PER_HOUR * HOURS_PER_DAY  # 96
"""Number of quarter-hour intervals per day (96)."""

DAYS_PER_YEAR: int = 365
"""Number of days per simulated year (non-leap)."""

QUARTERS_PER_YEAR: int = QUARTERS_PER_DAY * DAYS_PER_YEAR  # 35040
"""Total quarter-hour intervals per year (35 040)."""

# ---------------------------------------------------------------------------
# System base
# ---------------------------------------------------------------------------
P_PEAK_GW: float = 60.0
"""Italian peak load in GW, used as the per-unit base for all power values."""

P_BASE: float = P_PEAK_GW
"""Per-unit base power (alias for P_PEAK_GW)."""

# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------
N_MC_RUNS: int = 100
"""Default number of Monte Carlo runs for a full simulation."""

RANDOM_SEED: int = 42
"""Base random seed for reproducibility. Each MC run uses seed + run_index."""

# ---------------------------------------------------------------------------
# Dispatch constraints
# ---------------------------------------------------------------------------
H_MIN_SECONDS: float = 3.5
"""Minimum system inertia constant in seconds."""

RESERVE_FRACTION: float = 0.05
"""Spinning reserve requirement as fraction of load (5%)."""

CONTINGENCY_MW_PU: float = 1.8 / P_PEAK_GW
"""Largest credible generation loss (~1.8 GW) expressed in per-unit."""

# ---------------------------------------------------------------------------
# Economics
# ---------------------------------------------------------------------------
CO2_PRICE_DEFAULT: float = 65.0
"""Default EU ETS carbon price in EUR per ton of CO2."""

DISCOUNT_RATE: float = 0.07
"""Discount rate used for capital recovery factor (CRF) calculations."""

# ---------------------------------------------------------------------------
# Load profile factors
# ---------------------------------------------------------------------------
MONTHLY_LOAD_FACTORS: dict[int, float] = {
    1: 0.88, 2: 0.85, 3: 0.82, 4: 0.75, 5: 0.78, 6: 0.90,
    7: 1.00, 8: 0.95, 9: 0.88, 10: 0.80, 11: 0.85, 12: 0.90,
}
"""Monthly load factors (1.0 = peak month = July). Keys are 1-indexed months."""

HOURLY_LOAD_FACTORS: dict[int, float] = {
    0: 0.58, 1: 0.55, 2: 0.53, 3: 0.52, 4: 0.53, 5: 0.56,
    6: 0.62, 7: 0.72, 8: 0.82, 9: 0.90, 10: 0.95, 11: 0.97,
    12: 0.95, 13: 0.93, 14: 0.92, 15: 0.91, 16: 0.90, 17: 0.92,
    18: 0.96, 19: 1.00, 20: 0.98, 21: 0.93, 22: 0.82, 23: 0.70,
}
"""Hourly load factors (fraction of daily peak, 0-indexed hours)."""

# ---------------------------------------------------------------------------
# Solar profile parameters
# ---------------------------------------------------------------------------
MONTHLY_SOLAR_FACTORS: dict[int, float] = {
    1: 0.30, 2: 0.40, 3: 0.60, 4: 0.75, 5: 0.90, 6: 0.95,
    7: 1.00, 8: 0.95, 9: 0.75, 10: 0.55, 11: 0.35, 12: 0.28,
}
"""Monthly solar irradiance factors (1.0 = July). Keys are 1-indexed months."""


def _solar_envelope() -> dict[int, float]:
    """Compute hourly solar irradiance envelope using a Gaussian centered at 13:00.

    The envelope approximates Italian solar noon (~13:00 local time) with a
    standard deviation of 2.8 hours. Night hours (0-5 and 21-23) are hard-zeroed.

    Returns:
        dict[int, float]: Mapping from hour (0-23) to normalized irradiance
            factor (0.0 to 1.0).
    """
    hours = np.arange(24)
    envelope = np.exp(-0.5 * ((hours - 13.0) / 2.8) ** 2)
    envelope[0:6] = 0.0
    envelope[21:] = 0.0
    envelope /= envelope.max()
    return {h: float(envelope[h]) for h in range(24)}


HOURLY_SOLAR_ENVELOPE: dict[int, float] = _solar_envelope()
"""Hourly solar irradiance envelope (Gaussian, peak at 13:00, zero at night)."""

# ---------------------------------------------------------------------------
# Wind profile parameters
# ---------------------------------------------------------------------------
MONTHLY_WIND_LAMBDA: dict[int, float] = {
    1: 8.5, 2: 8.2, 3: 7.8, 4: 7.5, 5: 6.8, 6: 6.0,
    7: 5.5, 8: 5.8, 9: 6.5, 10: 7.0, 11: 7.8, 12: 8.3,
}
"""Monthly Weibull scale parameter (m/s) for Italian average onshore wind."""

WIND_WEIBULL_K: float = 2.0
"""Weibull shape parameter for wind speed distribution."""

WIND_CUT_IN: float = 3.0
"""Turbine cut-in wind speed (m/s)."""

WIND_RATED: float = 12.0
"""Turbine rated wind speed (m/s) at which full power is reached."""

WIND_CUT_OUT: float = 25.0
"""Turbine cut-out wind speed (m/s) above which turbine shuts down."""

# ---------------------------------------------------------------------------
# Cloud Markov chain
# ---------------------------------------------------------------------------
CLOUD_TRANSITION: dict[int, tuple[float, float]] = {
    1:  (0.40, 0.35),  2: (0.38, 0.37),  3: (0.30, 0.40),
    4:  (0.25, 0.45),  5: (0.20, 0.50),  6: (0.15, 0.55),
    7:  (0.10, 0.60),  8: (0.12, 0.58),  9: (0.20, 0.50),
    10: (0.30, 0.40), 11: (0.38, 0.35), 12: (0.42, 0.33),
}
"""Monthly cloud state transition probabilities.

Each entry is ``(P(cloudy|sunny), P(sunny|cloudy))`` for the two-state
daily Markov chain used by :class:`~energy_sim.generators.SolarAvailability`.
"""

# ---------------------------------------------------------------------------
# Gas price scenarios (TTF EUR/MWh_th)
# ---------------------------------------------------------------------------
GAS_SCENARIOS: dict[str, dict[str, float]] = {
    'base':    {'mu': 35.0, 'sigma': 8.0,  'theta': 0.1},
    'tension': {'mu': 55.0, 'sigma': 15.0, 'theta': 0.1},
    'crisis':  {'mu': 90.0, 'sigma': 25.0, 'theta': 0.1},
}
"""Gas price scenario parameters for the Ornstein-Uhlenbeck fuel price model.

Keys:
    mu: Long-run mean price (EUR/MWh_th).
    sigma: Volatility.
    theta: Mean-reversion speed.
"""

# ---------------------------------------------------------------------------
# Coal price scenarios (EUR/MWh_th)
# ---------------------------------------------------------------------------
COAL_SCENARIOS: dict[str, dict[str, float]] = {
    'base':    {'mu': 12.0, 'sigma': 3.0, 'theta': 0.05},
    'tension': {'mu': 18.0, 'sigma': 5.0, 'theta': 0.05},
    'crisis':  {'mu': 25.0, 'sigma': 8.0, 'theta': 0.05},
}
"""Coal price scenario parameters for the Ornstein-Uhlenbeck fuel price model.

Coal is cheaper than gas per MWh_th but has lower volatility and slower
mean-reversion. With high CO₂ prices (>60 EUR/ton), coal SRMC can exceed
gas SRMC ("fuel switching").

Keys:
    mu: Long-run mean price (EUR/MWh_th).
    sigma: Volatility.
    theta: Mean-reversion speed.
"""

# ---------------------------------------------------------------------------
# CO2 price scenarios (EUR/ton)
# ---------------------------------------------------------------------------
CO2_SCENARIOS: dict[str, dict[str, float]] = {
    'base':    {'mu': 65.0, 'sigma': 10.0, 'theta': 0.05},
    'low':     {'mu': 40.0, 'sigma': 8.0,  'theta': 0.05},
    'high':    {'mu': 100.0, 'sigma': 15.0, 'theta': 0.05},
}
"""CO2 ETS price scenario parameters for the Ornstein-Uhlenbeck carbon price model.

Slower mean-reversion than gas (theta=0.05) reflects the ETS market's
structural inertia. A volatile CO₂ price creates timesteps where coal is
cheaper than gas and vice versa, producing realistic fuel-switching behavior.

Keys:
    mu: Long-run mean CO2 price (EUR/ton).
    sigma: Volatility.
    theta: Mean-reversion speed.
"""

# ---------------------------------------------------------------------------
# Italian generation mix defaults
# ---------------------------------------------------------------------------
ITALIAN_MIX: dict[str, dict] = {
    'gas': {
        'capacity_gw': 45.0,
        'capex_per_kw': 900,
        'lifetime_years': 27,
        'vom_eur_mwh': 3.0,
        'fom_eur_kw_yr': 20.0,
        'efficiency': 0.58,
        'emission_factor': 0.20,
        'h_inertia': 4.5,
        'min_stable_pct': 0.40,
        'ramp_rate_pct_per_min': 0.06,
        'startup_cost_eur_mw': 50.0,
    },
    'solar': {
        'capacity_gw': 30.0,
        'capex_per_kw': 550,
        'lifetime_years': 28,
        'vom_eur_mwh': 0.5,
        'fom_eur_kw_yr': 10.0,
        'efficiency': 1.0,
        'emission_factor': 0.0,
        'h_inertia': 0.0,
        'min_stable_pct': 0.0,
        'ramp_rate_pct_per_min': 1.0,
        'startup_cost_eur_mw': 0.0,
    },
    'wind': {
        'capacity_gw': 13.0,
        'capex_per_kw': 1250,
        'lifetime_years': 22,
        'vom_eur_mwh': 1.5,
        'fom_eur_kw_yr': 32.0,
        'efficiency': 1.0,
        'emission_factor': 0.0,
        'h_inertia': 0.0,
        'min_stable_pct': 0.0,
        'ramp_rate_pct_per_min': 1.0,
        'startup_cost_eur_mw': 0.0,
    },
    'nuclear': {
        'capacity_gw': 0.0,
        'capex_per_kw': 5500,
        'lifetime_years': 60,
        'vom_eur_mwh': 2.5,
        'fom_eur_kw_yr': 80.0,
        'efficiency': 0.33,
        'emission_factor': 0.0,
        'h_inertia': 6.0,
        'min_stable_pct': 0.50,
        'ramp_rate_pct_per_min': 0.03,
        'startup_cost_eur_mw': 200.0,
        'fuel_cost_eur_mwh_th': 3.0,
    },
    'coal': {
        'capacity_gw': 0.0,
        'capex_per_kw': 1500,
        'lifetime_years': 40,
        'vom_eur_mwh': 4.0,
        'fom_eur_kw_yr': 35.0,
        'efficiency': 0.40,
        'emission_factor': 0.34,
        'h_inertia': 5.0,
        'min_stable_pct': 0.45,
        'ramp_rate_pct_per_min': 0.02,
        'startup_cost_eur_mw': 80.0,
    },
    'hydro_mustrun': {
        'capacity_gw': 8.0,
        'capex_per_kw': 0,
        'lifetime_years': 80,
        'vom_eur_mwh': 0.0,
        'fom_eur_kw_yr': 0.0,
        'efficiency': 1.0,
        'emission_factor': 0.0,
        'h_inertia': 3.5,
        'min_stable_pct': 1.0,
        'ramp_rate_pct_per_min': 0.0,
        'startup_cost_eur_mw': 0.0,
    },
}
"""Default Italian generation mix parameters.

Each generator type maps to a dict with:
    capacity_gw (float): Installed capacity in GW.
    capex_per_kw (float): Capital expenditure in EUR per kW.
    lifetime_years (float): Economic lifetime in years.
    vom_eur_mwh (float): Variable O&M cost in EUR/MWh.
    fom_eur_kw_yr (float): Fixed O&M cost in EUR per kW per year.
    efficiency (float): Thermal-to-electric efficiency (1.0 for renewables).
    emission_factor (float): CO2 emissions in tCO2/MWh_th.
    h_inertia (float): Inertia constant H in seconds (0 for non-synchronous).
    min_stable_pct (float): Minimum stable generation as fraction of capacity.
    ramp_rate_pct_per_min (float): Ramp rate as fraction of capacity per minute.
    startup_cost_eur_mw (float): Start-up cost in EUR per MW.
"""
