"""Tests for energy_sim.simulation (run_monte_carlo, sweep_technology,
build_sensitivity_heatmap, build_incremental_heatmap).

Validates the Monte Carlo runner for reproducibility, correct output shapes,
edge cases (single run), and price sanity. Validates sweep_technology for
correct result length and presence of all expected keys. Validates
build_sensitivity_heatmap for correct matrix shapes across gas scenarios
and penetration levels. Validates build_incremental_heatmap for correct
matrix shapes, marginal cost consistency, and expected price impact sign.
"""

import numpy as np
import pytest

from energy_sim.config import ITALIAN_MIX, GAS_SCENARIOS
from energy_sim.simulation import (
    run_monte_carlo,
    sweep_technology,
    build_sensitivity_heatmap,
    build_incremental_heatmap,
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
                         'mean_curtailment', 'mean_inertia'}
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
