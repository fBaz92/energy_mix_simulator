"""Tests for the parameter-sweep engine.

Exercises the override dispatch table (which keeps scenario mutation
confined to a whitelisted surface) and a small end-to-end 2×2 sweep to
make sure the runner wires up correctly and returns metric dicts with
the expected keys.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from energy_sim.config import GAS_SCENARIOS, ITALIAN_MIX
from energy_sim.simulation import SimulationConfig
from webapp.backend.sweeps import (
    _apply_override,
    build_grid,
    run_sweep,
    run_sweep_point,
)


@pytest.fixture
def base_cfg() -> SimulationConfig:
    """Minimal base config shared by every override / sweep test."""
    return SimulationConfig(
        mix_config=ITALIAN_MIX,
        gas_scenario=GAS_SCENARIOS["base"],
        n_runs=2,
        seed=42,
    )


class TestApplyOverride:
    """``_apply_override`` must update the targeted field and leave the
    source config untouched.
    """

    def test_mix_capacity_override(self, base_cfg):
        """``mix.<tech>.capacity_gw`` path replaces the capacity value."""
        new_cfg = _apply_override(base_cfg, "mix.gas.capacity_gw", 20.0)
        assert new_cfg.mix_config["gas"]["capacity_gw"] == 20.0
        # Source config must NOT be mutated — copy semantics.
        assert base_cfg.mix_config["gas"]["capacity_gw"] != 20.0

    def test_fuel_mu_override_creates_dict_when_missing(self, base_cfg):
        """Sweeping ``co2.mu`` on a scenario without a co2_scenario must
        create a fresh dict rather than raise.
        """
        assert base_cfg.co2_scenario is None
        new_cfg = _apply_override(base_cfg, "co2.mu", 80.0)
        assert new_cfg.co2_scenario is not None
        assert new_cfg.co2_scenario["mu"] == 80.0

    def test_gas_mu_override(self, base_cfg):
        """``gas.mu`` path touches only ``mu`` of the gas scenario dict."""
        new_cfg = _apply_override(base_cfg, "gas.mu", 90.0)
        assert new_cfg.gas_scenario["mu"] == 90.0
        # Other fields preserved.
        assert (new_cfg.gas_scenario["sigma"]
                == base_cfg.gas_scenario["sigma"])

    def test_load_noise_override(self, base_cfg):
        """``load_noise`` is a scalar attribute on the SimulationConfig."""
        new_cfg = _apply_override(base_cfg, "load_noise", 0.05)
        assert new_cfg.load_noise == 0.05

    @pytest.mark.parametrize("bad_path", [
        "unknown",
        "mix.gas",               # missing field
        "mix.gas.capacity_gw.x",  # too many components
        "foo.bar",
    ])
    def test_unknown_path_raises(self, base_cfg, bad_path):
        """Only whitelisted override paths are allowed — a strict guard
        against letting REST clients mutate internal config fields.
        """
        with pytest.raises(ValueError):
            _apply_override(base_cfg, bad_path, 1.0)

    def test_unknown_mix_tech_raises(self, base_cfg):
        """A typo in the tech name is loud — we'd rather fail the sweep
        up front than produce 30 points of "gas capacity = 0" silently.
        """
        with pytest.raises(KeyError):
            _apply_override(base_cfg, "mix.typo.capacity_gw", 10.0)


class TestBuildGrid:
    """The grid enumerator must produce points in row-major order so the
    frontend heatmap can reshape by ``len(values_b)`` columns.
    """

    def test_1d_grid(self):
        """1D sweeps produce one tuple per value, B always ``None``."""
        g = build_grid("1d", [1.0, 2.0, 3.0], None)
        assert g == [(1.0, None), (2.0, None), (3.0, None)]

    def test_2d_grid_row_major(self):
        """A slows, B fast — so ``(a0,b0), (a0,b1), (a1,b0), (a1,b1)``."""
        g = build_grid("2d", [10.0, 20.0], [1.0, 2.0])
        assert g == [
            (10.0, 1.0), (10.0, 2.0),
            (20.0, 1.0), (20.0, 2.0),
        ]

    def test_2d_requires_values_b(self):
        """A ``sweep_type='2d'`` without B values is a client bug."""
        with pytest.raises(ValueError):
            build_grid("2d", [1.0], None)

    def test_unknown_sweep_type(self):
        """Defensive — the REST layer already validates this, but the
        engine asserts the contract too.
        """
        with pytest.raises(ValueError):
            build_grid("3d", [1.0], [1.0])


class TestRunSweepPoint:
    """A single grid-point execution returns the aggregate metrics
    with the expected keys.
    """

    def test_metric_shape(self, base_cfg):
        """The returned dict must carry the five metric keys consumed by
        :class:`SweepResultPoint`.
        """
        metrics = run_sweep_point(
            base_cfg, "mix.gas.capacity_gw", 30.0,
            None, None,
            n_runs=2, seed=7,
        )
        assert set(metrics.keys()) == {
            "avg_price_mean", "avg_price_std",
            "carbon_intensity_mean", "avg_inertia_mean",
            "curtailment_mean",
        }
        # All metrics should be finite floats (sanity on the MC output).
        for k, v in metrics.items():
            assert np.isfinite(v), f"{k} = {v}"


@pytest.mark.slow
class TestEndToEndSweep:
    """End-to-end 2×2 sweep to verify that the grid, override, and
    Monte Carlo engine wire up correctly. Marked ``slow`` because even
    at ``n_runs=2`` the four grid points take ~15 s.
    """

    def test_2d_small_sweep(self, base_cfg):
        """A 2×2 ``(gas capacity × gas μ)`` sweep produces four points
        with B values preserved alongside A values.
        """
        progress_seen: list[tuple[int, int]] = []
        points = run_sweep(
            base_cfg,
            sweep_type="2d",
            parameter_a="mix.gas.capacity_gw",
            values_a=[30.0, 45.0],
            parameter_b="gas.mu",
            values_b=[40.0, 80.0],
            n_runs_per_point=2,
            seed=42,
            progress_cb=lambda c, t: progress_seen.append((c, t)),
        )
        assert len(points) == 4
        for p in points:
            assert "a" in p and "b" in p
            assert "avg_price_mean" in p
        # Progress callback fires once per completed point with total=4.
        assert progress_seen == [(1, 4), (2, 4), (3, 4), (4, 4)]

    def test_1d_small_sweep(self, base_cfg):
        """A 1D sweep on gas μ returns monotonic-ish price points
        (higher μ → higher expected electricity price).
        """
        points = run_sweep(
            replace(base_cfg, n_runs=3),
            sweep_type="1d",
            parameter_a="gas.mu",
            values_a=[20.0, 60.0, 100.0],
            parameter_b=None, values_b=None,
            n_runs_per_point=3, seed=42,
        )
        assert len(points) == 3
        prices = [p["avg_price_mean"] for p in points]
        # Loose monotonicity — the MC noise at n_runs=3 is large but
        # gas μ 20→100 should push the mean electricity price upward.
        assert prices[-1] > prices[0]
