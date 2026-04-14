"""Tests for energy_sim.price_areas (foreign price coupling).

Validates that :class:`PriceAreaCoupling` produces jointly correlated
shocks via Cholesky decomposition, that the marginal distributions of each
area's price process are preserved under correlation, that the PSD
validation rejects malformed correlation matrices, and that the
``correlated=False`` switch collapses the coupling to independent paths.
"""

import numpy as np
import pytest

from energy_sim.generators import FuelPriceModel
from energy_sim.models import TimeGrid
from energy_sim.price_areas import (
    PriceArea,
    PriceAreaCoupling,
    build_price_areas_from_config,
)


# ── Fixtures ────────────────────────────────────────────────────────────


def _area(name, mu=50.0, sigma=10.0, theta=0.05, ci=100.0):
    """Build a :class:`PriceArea` with an O-U price model for tests."""
    return PriceArea(
        name=name,
        price_model=FuelPriceModel(mu=mu, sigma=sigma, theta=theta),
        carbon_intensity_g_per_kwh=ci,
    )


@pytest.fixture
def coupling_two():
    """Two-area coupling with a single 0.7 correlation."""
    return PriceAreaCoupling(
        areas=[_area('A', mu=40), _area('B', mu=60)],
        correlations={('A', 'B'): 0.7},
    )


# ── Construction / validation ──────────────────────────────────────────


class TestPriceAreaCouplingConstruction:
    """Construction-time validation of the coupling dataclass."""

    def test_duplicate_area_names_rejected(self):
        """Two areas with the same name must be rejected at construction.

        Name is the lookup key in :meth:`realize`; duplicates would lead
        to silent last-wins overwrites in the returned mapping.
        """
        with pytest.raises(ValueError, match="Duplicate area names"):
            PriceAreaCoupling(areas=[_area('X'), _area('X')])

    def test_unknown_area_in_correlation_raises(self):
        """A correlation key referencing a non-existent area must raise.

        Detects user typos before they silently corrupt the matrix.
        """
        cpl = PriceAreaCoupling(
            areas=[_area('A'), _area('B')],
            correlations={('A', 'Z'): 0.5},
        )
        with pytest.raises(KeyError):
            cpl.build_correlation_matrix()

    def test_correlation_out_of_range_raises(self):
        """Correlation values outside ``[-1, 1]`` must be rejected.

        Any real correlation coefficient is in that range; larger values
        produce invalid (non-PSD) matrices.
        """
        cpl = PriceAreaCoupling(
            areas=[_area('A'), _area('B')],
            correlations={('A', 'B'): 1.5},
        )
        with pytest.raises(ValueError, match="outside"):
            cpl.build_correlation_matrix()

    def test_non_psd_correlation_matrix_rejected(self):
        """A materially indefinite correlation matrix must be rejected.

        We construct a 3×3 matrix with inconsistent pairwise correlations
        (impossible joint distribution) and check the validator catches it.
        """
        cpl = PriceAreaCoupling(
            areas=[_area('A'), _area('B'), _area('C')],
            correlations={
                ('A', 'B'): 0.9, ('B', 'C'): 0.9, ('A', 'C'): -0.9,
            },
        )
        with pytest.raises(ValueError, match="not positive semidefinite"):
            cpl.build_correlation_matrix()


# ── Correlation matrix assembly ─────────────────────────────────────────


class TestCorrelationMatrix:
    """Assembly of the symmetric K×K correlation matrix."""

    def test_matrix_is_symmetric_with_unit_diagonal(self, coupling_two):
        """build_correlation_matrix must enforce symmetry and unit diag."""
        rho = coupling_two.build_correlation_matrix()
        assert rho.shape == (2, 2)
        assert np.allclose(np.diag(rho), 1.0)
        assert np.allclose(rho, rho.T)
        assert rho[0, 1] == pytest.approx(0.7)

    def test_correlated_false_returns_identity(self):
        """Disabling correlation collapses the matrix to the identity.

        This is the entry point for ``PRICE_AREAS_CORRELATED = False``.
        """
        cpl = PriceAreaCoupling(
            areas=[_area('A'), _area('B'), _area('C')],
            correlations={('A', 'B'): 0.9},
            correlated=False,
        )
        rho = cpl.build_correlation_matrix()
        assert np.array_equal(rho, np.eye(3))


# ── End-to-end realization ─────────────────────────────────────────────


class TestRealize:
    """Joint stochastic simulation through :meth:`realize`."""

    def test_paths_have_expected_shape_and_keys(self, coupling_two):
        """realize must return one path per area, each of length ``time_grid.n``."""
        tg = TimeGrid()
        out = coupling_two.realize(tg, np.random.default_rng(0))
        assert set(out.keys()) == {'A', 'B'}
        assert out['A'].shape == (tg.n,)
        assert out['B'].shape == (tg.n,)

    def test_correlation_is_recovered_empirically(self):
        """Empirical correlation of the realized shocks must match the target.

        We measure correlation on the *first differences* of the two price
        paths rather than on the levels: the O-U integrator mixes each
        shock with the entire history of the past shocks, so level
        correlations drift with the slow mean-reversion dynamics and are
        noisy estimators of the Cholesky-applied shock correlation. First
        differences ``Δp ≈ θ·(μ-p)·dt + σ·√dt·Z`` are dominated by the
        driving shock Z, so their correlation recovers the target
        tightly (±0.05 over 35040 samples).
        """
        cpl = PriceAreaCoupling(
            areas=[_area('A', mu=50, sigma=10),
                   _area('B', mu=50, sigma=10)],
            correlations={('A', 'B'): 0.8},
        )
        tg = TimeGrid()
        out = cpl.realize(tg, np.random.default_rng(123))
        rho_diff = np.corrcoef(np.diff(out['A']), np.diff(out['B']))[0, 1]
        assert abs(rho_diff - 0.8) < 0.05

    def test_independent_mode_produces_uncorrelated_paths(self):
        """With ``correlated=False``, empirical shock correlation tends to zero.

        A non-zero target in ``correlations`` is ignored; the Cholesky
        factor collapses to the identity. Uses first differences for the
        same reason as the previous test.
        """
        cpl = PriceAreaCoupling(
            areas=[_area('A'), _area('B')],
            correlations={('A', 'B'): 0.9},
            correlated=False,
        )
        tg = TimeGrid()
        out = cpl.realize(tg, np.random.default_rng(7))
        rho_diff = np.corrcoef(np.diff(out['A']), np.diff(out['B']))[0, 1]
        assert abs(rho_diff) < 0.03


# ── Factory ────────────────────────────────────────────────────────────


class TestFactory:
    """Build a coupling from plain-dict config, including subset filtering."""

    def test_subset_filters_areas_and_correlations(self):
        """Only requested areas survive, and correlations involving dropped
        areas are silently removed.
        """
        areas_cfg = {
            'FR': {'mu': 45, 'sigma': 12, 'theta': 0.05, 'carbon_intensity_g_per_kwh': 50},
            'CH': {'mu': 50, 'sigma': 10, 'theta': 0.05, 'carbon_intensity_g_per_kwh': 30},
            'AT': {'mu': 55, 'sigma': 14, 'theta': 0.05, 'carbon_intensity_g_per_kwh': 200},
        }
        cors_cfg = {('FR', 'CH'): 0.8, ('FR', 'AT'): 0.6, ('CH', 'AT'): 0.7}
        cpl = build_price_areas_from_config(
            areas_cfg, cors_cfg, subset=['FR', 'CH'])
        names = [a.name for a in cpl.areas]
        assert names == ['FR', 'CH']
        # Only the FR-CH correlation survives
        assert list(cpl.correlations.keys()) == [('FR', 'CH')]

    def test_subset_with_unknown_area_raises(self):
        """Asking for an area absent from the config must raise ``KeyError``."""
        areas_cfg = {'A': {'mu': 50, 'sigma': 10, 'theta': 0.05}}
        with pytest.raises(KeyError, match="Unknown price areas"):
            build_price_areas_from_config(areas_cfg, subset=['B'])

    def test_carbon_intensity_defaults_to_zero(self):
        """Areas without ``carbon_intensity_g_per_kwh`` key default to 0.

        Ensures the optional field does not require every caller to
        specify it explicitly.
        """
        areas_cfg = {'X': {'mu': 50, 'sigma': 10, 'theta': 0.05}}
        cpl = build_price_areas_from_config(areas_cfg)
        assert cpl.areas[0].carbon_intensity_g_per_kwh == 0.0
