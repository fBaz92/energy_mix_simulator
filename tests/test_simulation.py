"""Tests for energy_sim.simulation (run_monte_carlo with load profile
enhancements, sweep_technology, build_sensitivity_heatmap,
build_incremental_heatmap, sweep_fuel_price, sweep_fuel_prices_2d).

Validates the Monte Carlo runner for reproducibility, correct output shapes,
edge cases (single run), and price sanity. Validates sweep_technology for
correct result length and presence of all expected keys. Validates
build_sensitivity_heatmap for correct matrix shapes across gas scenarios
and penetration levels. Validates build_incremental_heatmap for correct
matrix shapes, marginal cost consistency, and expected price impact sign.
Validates sweep_fuel_price for correct result length, keys, monotonicity
(higher gas price → higher electricity price), and input validation.
Validates sweep_fuel_prices_2d for correct matrix shapes.
"""

import numpy as np
import pytest

from copy import deepcopy

from energy_sim.config import ITALIAN_MIX, GAS_SCENARIOS, COAL_SCENARIOS
from energy_sim.simulation import (
    run_monte_carlo,
    sweep_technology,
    build_sensitivity_heatmap,
    build_incremental_heatmap,
    sweep_fuel_price,
    sweep_fuel_prices_2d,
)


class TestRunMonteCarlo:
    """Verify the Monte Carlo simulation runner."""

    def test_reproducibility(self):
        """Two runs with the same seed must produce identical average prices,
        confirming deterministic RNG seeding per run.
        """
        r1 = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=2, seed=99)
        r2 = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=2, seed=99)
        np.testing.assert_array_equal(r1['avg_price'], r2['avg_price'])

    def test_output_shapes(self):
        """All output arrays must have correct shapes: avg_price (n_runs,),
        monthly_prices (n_runs, 12), curtailment (n_runs,), avg_inertia (n_runs,).
        """
        n = 3
        r = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=n, seed=0)
        assert r['avg_price'].shape == (n,)
        assert r['monthly_prices'].shape == (n, 12)
        assert r['curtailment'].shape == (n,)
        assert r['avg_inertia'].shape == (n,)

    def test_single_run(self):
        """n_runs=1 must work without errors and return arrays of shape (1,) / (1, 12)."""
        r = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=1, seed=0)
        assert r['avg_price'].shape == (1,)

    def test_prices_reasonable(self):
        """Mean electricity price for the Italian mix (base gas) must fall in a
        reasonable range of 10-500 EUR/MWh — sanity check against model errors.
        """
        r = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=2, seed=42)
        mean_price = r['avg_price'].mean()
        assert 10 < mean_price < 500

    def test_emissions_output_shapes(self):
        """Emissions outputs must have correct shapes: total_emissions (n_runs,),
        carbon_intensity (n_runs,), emissions_by_tech values (n_runs,).
        """
        n = 2
        r = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=n, seed=0)
        assert r['total_emissions'].shape == (n,)
        assert r['carbon_intensity'].shape == (n,)
        assert isinstance(r['emissions_by_tech'], dict)
        for v in r['emissions_by_tech'].values():
            assert v.shape == (n,)

    def test_emissions_positive(self):
        """Total emissions must be positive for the Italian mix which includes
        gas generation with non-zero emission factor.
        """
        r = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=2, seed=42)
        assert (r['total_emissions'] > 0).all()

    def test_carbon_intensity_reasonable(self):
        """Carbon intensity for the Italian mix (gas-heavy) should be in a
        reasonable range: 50-600 gCO₂/kWh.
        """
        r = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=2, seed=42)
        mean_ci = r['carbon_intensity'].mean()
        assert 50 < mean_ci < 600

    def test_only_gas_emits(self):
        """In the default Italian mix (no coal), only gas has emission_factor > 0.
        All other technologies must have zero (or near-zero) emissions.
        """
        r = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=2, seed=42)
        for tech, vals in r['emissions_by_tech'].items():
            if tech == 'gas':
                assert vals.mean() > 0
            else:
                np.testing.assert_allclose(vals, 0, atol=1e-10)

    def test_coal_increases_emissions(self):
        """Adding coal to the mix must increase total emissions compared to
        the base mix (gas-only fossil), since coal has a higher emission factor.
        """
        from copy import deepcopy
        mix_coal = deepcopy(ITALIAN_MIX)
        mix_coal['coal']['capacity_gw'] = 15.0
        r_base = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=2, seed=42)
        r_coal = run_monte_carlo(mix_coal, GAS_SCENARIOS['base'],
                                 COAL_SCENARIOS['base'], n_runs=2, seed=42)
        assert r_coal['total_emissions'].mean() > r_base['total_emissions'].mean()

    def test_coal_emits_in_mix(self):
        """When coal is present in the mix with non-zero capacity, it must
        produce positive emissions in the per-technology breakdown.
        """
        from copy import deepcopy
        mix_coal = deepcopy(ITALIAN_MIX)
        mix_coal['coal']['capacity_gw'] = 15.0
        r = run_monte_carlo(mix_coal, GAS_SCENARIOS['base'],
                            COAL_SCENARIOS['base'], n_runs=2, seed=42)
        assert 'coal' in r['emissions_by_tech']
        assert r['emissions_by_tech']['coal'].mean() > 0

    def test_weekday_holiday_active_by_default(self):
        """With default settings, weekday/holiday modulation should produce
        lower average load than without them. We verify by comparing runs
        with and without the enhancements.
        """
        r_with = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'],
                                 n_runs=2, seed=42)
        r_without = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'],
                                    n_runs=2, seed=42,
                                    weekday_factors=None,
                                    holiday_factor=None,
                                    holiday_calendar=None)
        # Weekday/holiday reduce load → lower prices on average
        assert r_with['avg_price'].mean() <= r_without['avg_price'].mean(), (
            "Weekday/holiday load reduction should lower or maintain average price"
        )

    def test_disable_load_enhancements(self):
        """Passing None for weekday/holiday/calendar must work without errors
        and produce valid results (backward compatibility).
        """
        r = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'],
                            n_runs=1, seed=0,
                            weekday_factors=None,
                            holiday_factor=None,
                            holiday_calendar=None,
                            load_noise=0.02)
        assert r['avg_price'].shape == (1,)
        assert r['avg_price'][0] > 0


class TestInterconnectionAggregates:
    """Monte-Carlo-level aggregates of the Phase 6 follow-up metrics.

    Exercises the per-link arrays that :func:`run_monte_carlo` fills in
    from each dispatched :class:`~energy_sim.dispatch.InterconnectionMetrics`
    and the consumption-based carbon-intensity series. Keeps the run
    count low (2 MC runs) so it executes in the fast test tier.
    """

    def _run_with_links(self, n_runs=2):
        """Run a short MC with the full Italian interconnection preset."""
        from energy_sim.config import (
            INTERCONNECTIONS, PRICE_AREAS, PRICE_AREA_CORRELATIONS,
            CO2_SCENARIOS,
        )
        return run_monte_carlo(
            ITALIAN_MIX, GAS_SCENARIOS['base'],
            coal_scenario=COAL_SCENARIOS['base'],
            co2_scenario=CO2_SCENARIOS['base'],
            n_runs=n_runs, seed=42,
            interconnections_cfg=INTERCONNECTIONS,
            price_areas_cfg=PRICE_AREAS,
            price_area_correlations=PRICE_AREA_CORRELATIONS,
        )

    def test_new_aggregates_shape(self):
        """All new per-link arrays must have shape ``(n_runs, n_links)``
        and monthly aggregates ``(n_runs, n_links, 12)``. Catches
        accidental row/column swaps or missing stacks.
        """
        r = self._run_with_links(n_runs=2)
        n_links = len(r['interconnection_names'])
        assert r['import_hours'].shape == (2, n_links)
        assert r['export_hours'].shape == (2, n_links)
        assert r['import_energy_mwh'].shape == (2, n_links)
        assert r['export_energy_mwh'].shape == (2, n_links)
        assert r['total_economic_benefit_eur'].shape == (2, n_links)
        assert r['total_co2_benefit_tons'].shape == (2, n_links)
        assert r['economic_benefit_monthly_eur'].shape == (2, n_links, 12)
        assert r['co2_benefit_monthly_tons'].shape == (2, n_links, 12)
        assert r['carbon_intensity_consumption'].shape == (2,)

    def test_monthly_sums_match_annual_totals(self):
        """Summing the 12 monthly slots must reproduce the annual totals
        to floating-point precision. Guards the aggregation bucketing
        against off-by-one in the month-mask loop.
        """
        r = self._run_with_links(n_runs=2)
        econ_from_monthly = r['economic_benefit_monthly_eur'].sum(axis=2)
        co2_from_monthly = r['co2_benefit_monthly_tons'].sum(axis=2)
        np.testing.assert_allclose(econ_from_monthly,
                                   r['total_economic_benefit_eur'],
                                   rtol=1e-10, atol=1e-3)
        np.testing.assert_allclose(co2_from_monthly,
                                   r['total_co2_benefit_tons'],
                                   rtol=1e-10, atol=1e-6)

    def test_economic_benefit_non_negative_annual(self):
        """Annual congestion-rent benefit per link per run must be
        non-negative, matching the per-qh invariant validated in the
        dispatch tests.
        """
        r = self._run_with_links(n_runs=2)
        assert (r['total_economic_benefit_eur'] >= -1e-6).all()

    def test_consumption_ci_defaults_to_territorial_without_links(self):
        """When no interconnections are active the consumption-based CI
        must coincide with the territorial one (equivalent to zero
        cross-border attribution).
        """
        r = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'],
                            n_runs=2, seed=42)
        np.testing.assert_allclose(r['carbon_intensity_consumption'],
                                   r['carbon_intensity'],
                                   rtol=1e-10, atol=1e-10)

    def test_consumption_ci_reasonable_with_links(self):
        """With the Italian preset (net importer of mixed-CI flows) the
        consumption-based CI must be finite, positive, and differ from
        the territorial figure by at most a physically plausible margin.
        """
        r = self._run_with_links(n_runs=2)
        ci_t = r['carbon_intensity']
        ci_c = r['carbon_intensity_consumption']
        assert np.all(np.isfinite(ci_c))
        assert np.all(ci_c > 0)
        # 100 g/kWh is a very loose envelope — real shift is ~20 g/kWh.
        # The bound catches unit-scale errors (e.g. kg/MWh vs g/kWh).
        assert np.all(np.abs(ci_c - ci_t) < 100)


class TestStorageAggregates:
    """Monte-Carlo-level aggregates for battery storage (Phase 7).

    Exercises the per-unit arrays that :func:`run_monte_carlo` fills in
    when ``storage_cfg`` is supplied. Keeps the run count low (2 MC runs)
    so it executes in the fast test tier.
    """

    def _run_with_storage(self, n_runs=2):
        """Run a short MC with the default Italian mix + storage."""
        from energy_sim.config import STORAGE_UNITS
        return run_monte_carlo(
            ITALIAN_MIX, GAS_SCENARIOS['base'], n_runs=n_runs, seed=42,
            storage_cfg=STORAGE_UNITS,
        )

    def test_storage_aggregate_shapes(self):
        """All storage aggregates must have expected shapes."""
        r = self._run_with_storage(n_runs=2)
        n_s = len(r['storage_names'])
        assert n_s == 1
        assert r['storage_energy_cycled_mwh'].shape == (2, n_s)
        assert r['storage_revenue_eur'].shape == (2, n_s)
        assert r['storage_equivalent_cycles'].shape == (2, n_s)
        assert r['storage_avg_soc'].shape == (2, n_s)
        assert r['storage_monthly_avg_soc'].shape == (2, n_s, 12)

    def test_energy_cycled_positive(self):
        """Total energy discharged must be strictly positive — the battery
        should participate in arbitrage with any reasonable price spread.
        """
        r = self._run_with_storage(n_runs=2)
        assert (r['storage_energy_cycled_mwh'] > 0).all()

    def test_avg_soc_inside_band(self):
        """Time-average SOC must lie inside the operational band."""
        from energy_sim.config import STORAGE_UNITS
        cfg = list(STORAGE_UNITS.values())[0]
        r = self._run_with_storage(n_runs=2)
        assert (r['storage_avg_soc'] >= cfg['soc_min_frac']).all()
        assert (r['storage_avg_soc'] <= cfg['soc_max_frac']).all()

    def test_no_storage_returns_empty_arrays(self):
        """When ``storage_cfg=None``, storage arrays must be empty but
        present — callers can read them unconditionally.
        """
        r = run_monte_carlo(ITALIAN_MIX, GAS_SCENARIOS['base'],
                            n_runs=2, seed=42, storage_cfg=None)
        assert r['storage_names'] == []
        assert r['storage_energy_cycled_mwh'].shape == (2, 0)
        assert r['storage_monthly_avg_soc'].shape == (2, 0, 12)

    def test_equivalent_cycles_reasonable(self):
        """Equivalent full cycles per year should be in a physically
        plausible range (1–500 for daily cycling).
        """
        r = self._run_with_storage(n_runs=2)
        cycles = r['storage_equivalent_cycles']
        assert (cycles > 0).all()
        assert (cycles < 500).all()


@pytest.mark.slow
class TestSweepTechnology:
    """Verify the technology penetration sweep utility."""

    def test_result_length(self):
        """sweep_technology must return one result dict per penetration level."""
        pcts = np.array([0, 10, 20])
        results = sweep_technology(ITALIAN_MIX, 'nuclear', pcts,
                                   GAS_SCENARIOS['base'], n_runs=2, seed=0)
        assert len(results) == len(pcts)

    def test_result_keys(self):
        """Each result dict must contain all expected keys: pct, mean_price,
        std_price, monthly_mean, mean_curtailment, mean_inertia.
        """
        pcts = np.array([0, 10])
        results = sweep_technology(ITALIAN_MIX, 'nuclear', pcts,
                                   GAS_SCENARIOS['base'], n_runs=2, seed=0)
        expected_keys = {'pct', 'mean_price', 'std_price', 'monthly_mean',
                         'mean_curtailment', 'mean_inertia',
                         'mean_emissions', 'mean_carbon_intensity',
                         'mean_emissions_by_tech'}
        for r in results:
            assert set(r.keys()) == expected_keys


@pytest.mark.slow
class TestBuildSensitivityHeatmap:
    """Verify the 2D sensitivity heatmap builder (tech penetration x gas scenario)."""

    def test_shapes(self):
        """Output matrices must have shape (n_gas_scenarios, n_penetrations) and
        gas_labels must have length n_gas_scenarios.
        """
        pcts = np.array([0, 10])
        scenarios = {'base': GAS_SCENARIOS['base'], 'tension': GAS_SCENARIOS['tension']}
        price_mat, inertia_mat, labels = build_sensitivity_heatmap(
            ITALIAN_MIX, 'nuclear', scenarios, pcts, n_runs=2, seed=0)
        assert price_mat.shape == (2, 2)
        assert inertia_mat.shape == (2, 2)
        assert len(labels) == 2


@pytest.mark.slow
class TestBuildIncrementalHeatmap:
    """Verify the incremental sensitivity heatmap builder.

    Tests that build_incremental_heatmap correctly computes finite-difference
    price impacts (Δ price and marginal cost per %) for a technology at
    different base penetration levels.
    """

    def test_shapes(self):
        """Output matrices must have shape (len(base_pcts), len(increments))."""
        base_pcts = np.array([0, 10])
        increments = np.array([2, 5])
        delta_mat, marginal_mat = build_incremental_heatmap(
            ITALIAN_MIX, 'nuclear', base_pcts, increments,
            GAS_SCENARIOS['base'], n_runs=2, seed=0)
        assert delta_mat.shape == (2, 2)
        assert marginal_mat.shape == (2, 2)

    def test_marginal_cost_consistent_with_delta(self):
        """marginal_cost[i,j] must equal delta_price[i,j] / increment[j]."""
        base_pcts = np.array([0, 10])
        increments = np.array([2, 5])
        delta_mat, marginal_mat = build_incremental_heatmap(
            ITALIAN_MIX, 'nuclear', base_pcts, increments,
            GAS_SCENARIOS['base'], n_runs=2, seed=0)
        expected = delta_mat / increments[np.newaxis, :]
        np.testing.assert_allclose(marginal_mat, expected)

    def test_nuclear_lowers_price(self):
        """Adding nuclear to the Italian mix should reduce the electricity price
        (negative delta), since nuclear has lower SRMC than gas.
        """
        base_pcts = np.array([0, 10])
        increments = np.array([5])
        delta_mat, _ = build_incremental_heatmap(
            ITALIAN_MIX, 'nuclear', base_pcts, increments,
            GAS_SCENARIOS['base'], n_runs=3, seed=42)
        # At least the first row (base=0%) should show a price decrease
        assert delta_mat[0, 0] < 0, (
            "Adding 5% nuclear from 0% base should lower the price"
        )


@pytest.mark.slow
class TestSweepFuelPrice:
    """Verify the single-fuel price sweep utility.

    Tests that sweep_fuel_price correctly iterates over fuel mean prices,
    returns properly structured results, and produces monotonically increasing
    electricity prices when gas price increases (all else equal).
    """

    def test_result_length(self):
        """sweep_fuel_price must return one result dict per μ value."""
        mu_range = np.array([25, 50, 75])
        results = sweep_fuel_price(
            ITALIAN_MIX, 'gas', mu_range,
            GAS_SCENARIOS['base'], n_runs=2, seed=0)
        assert len(results) == len(mu_range)

    def test_result_keys(self):
        """Each result dict must contain all expected keys: fuel_mu,
        mean_price, std_price, mean_emissions, mean_carbon_intensity,
        mean_emissions_by_tech.
        """
        mu_range = np.array([30, 50])
        results = sweep_fuel_price(
            ITALIAN_MIX, 'gas', mu_range,
            GAS_SCENARIOS['base'], n_runs=2, seed=0)
        expected_keys = {'fuel_mu', 'mean_price', 'std_price',
                         'mean_emissions', 'mean_carbon_intensity',
                         'mean_emissions_by_tech'}
        for r in results:
            assert set(r.keys()) == expected_keys

    def test_gas_price_monotonicity(self):
        """Higher gas fuel price must produce higher electricity price when
        gas is the dominant dispatchable generator in the mix.
        """
        mu_range = np.array([20, 60, 100])
        results = sweep_fuel_price(
            ITALIAN_MIX, 'gas', mu_range,
            GAS_SCENARIOS['base'], n_runs=3, seed=42)
        prices = [r['mean_price'] for r in results]
        assert prices[0] < prices[1] < prices[2], (
            f"Electricity prices should increase with gas price: {prices}"
        )

    def test_invalid_fuel_type(self):
        """Passing a fuel_type other than 'gas' or 'coal' must raise ValueError."""
        with pytest.raises(ValueError, match="fuel_type must be"):
            sweep_fuel_price(
                ITALIAN_MIX, 'nuclear', np.array([10, 20]),
                GAS_SCENARIOS['base'], n_runs=2, seed=0)

    def test_coal_sweep_with_coal_in_mix(self):
        """Sweeping coal price with coal in the mix must produce results where
        electricity price responds to coal price changes.
        """
        mix_coal = deepcopy(ITALIAN_MIX)
        mix_coal['coal']['capacity_gw'] = 15.0
        mu_range = np.array([8, 20])
        results = sweep_fuel_price(
            mix_coal, 'coal', mu_range,
            GAS_SCENARIOS['base'], COAL_SCENARIOS['base'],
            n_runs=2, seed=42)
        assert len(results) == 2
        # Higher coal price should not decrease electricity price
        assert results[1]['mean_price'] >= results[0]['mean_price'] - 5.0


@pytest.mark.slow
class TestSweepFuelPrices2d:
    """Verify the 2D fuel price sweep (gas × coal) utility.

    Tests that sweep_fuel_prices_2d returns matrices with correct shapes
    matching the input ranges and that prices are reasonable.
    """

    def test_shapes(self):
        """Output matrices must have shape (len(gas_mu_range), len(coal_mu_range))."""
        mix_coal = deepcopy(ITALIAN_MIX)
        mix_coal['coal']['capacity_gw'] = 15.0
        gas_mus = np.array([30, 60])
        coal_mus = np.array([10, 20])
        price_mat, ci_mat = sweep_fuel_prices_2d(
            mix_coal, gas_mus, coal_mus,
            GAS_SCENARIOS['base'], COAL_SCENARIOS['base'],
            n_runs=2, seed=0)
        assert price_mat.shape == (2, 2)
        assert ci_mat.shape == (2, 2)

    def test_prices_positive(self):
        """All electricity prices in the 2D matrix must be positive."""
        mix_coal = deepcopy(ITALIAN_MIX)
        mix_coal['coal']['capacity_gw'] = 15.0
        gas_mus = np.array([30, 60])
        coal_mus = np.array([10, 20])
        price_mat, _ = sweep_fuel_prices_2d(
            mix_coal, gas_mus, coal_mus,
            GAS_SCENARIOS['base'], COAL_SCENARIOS['base'],
            n_runs=2, seed=0)
        assert (price_mat > 0).all()

    def test_higher_gas_higher_price(self):
        """Within each coal price column, higher gas price must produce
        higher or equal electricity price.
        """
        mix_coal = deepcopy(ITALIAN_MIX)
        mix_coal['coal']['capacity_gw'] = 15.0
        gas_mus = np.array([25, 80])
        coal_mus = np.array([12])
        price_mat, _ = sweep_fuel_prices_2d(
            mix_coal, gas_mus, coal_mus,
            GAS_SCENARIOS['base'], COAL_SCENARIOS['base'],
            n_runs=3, seed=42)
        assert price_mat[1, 0] > price_mat[0, 0], (
            "Higher gas price should produce higher electricity price"
        )
