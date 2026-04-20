"""Parameter sweep engine.

Runs a 1D curve or 2D heatmap over one or two parameters of an existing
scenario. Each grid point executes ``n_runs_per_point`` Monte Carlo
simulations with the target parameter(s) overridden, aggregates the
scalar metrics, and returns a :class:`SweepResultPoint`. The heavy
per-run time-series arrays are *not* persisted — the sweep output is
orders of magnitude lighter than a full simulation.

Parameter overrides use dotted paths applied to a deep-copied
:class:`SimulationConfig`:

- ``mix.<tech>.capacity_gw`` — vary a technology's capacity in the mix.
- ``mix.<tech>.efficiency`` — vary thermal efficiency (0–1).
- ``gas.mu`` / ``gas.sigma`` / ``gas.theta`` — gas O-U parameters.
- ``coal.mu`` / ``coal.sigma`` / ``coal.theta`` — coal O-U parameters.
- ``co2.mu`` / ``co2.sigma`` / ``co2.theta`` — CO₂ O-U parameters.
- ``load_noise`` — Gaussian noise σ on the load profile.

Adding a new override path is a matter of extending the
``_APPLY_OVERRIDE`` dispatch table below.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import replace
from typing import Any, Callable

import numpy as np

from energy_sim.simulation import SimulationConfig, run_monte_carlo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Override dispatch table
# ---------------------------------------------------------------------------

def _set_mix_field(cfg: SimulationConfig, tech: str, field: str,
                   value: float) -> SimulationConfig:
    """Return a new SimulationConfig with ``mix_config[tech][field]``
    replaced.

    Args:
        cfg: Source config (untouched — deep copy of mix_config is made).
        tech: Technology key (e.g. ``'nuclear'``).
        field: Per-generator field (e.g. ``'capacity_gw'``).
        value: New scalar value.

    Raises:
        KeyError: If ``tech`` is not present in ``cfg.mix_config``.
    """
    if tech not in cfg.mix_config:
        raise KeyError(f"mix does not contain technology '{tech}'")
    new_mix = copy.deepcopy(cfg.mix_config)
    new_mix[tech][field] = float(value)
    return replace(cfg, mix_config=new_mix)


def _set_fuel_field(cfg: SimulationConfig, which: str, field: str,
                    value: float) -> SimulationConfig:
    """Return a new SimulationConfig with a fuel scenario field replaced.

    ``which`` selects ``gas_scenario`` / ``coal_scenario`` /
    ``co2_scenario``; the scenario dict is copied before mutation. If
    the target attribute is ``None`` (no scenario configured), a fresh
    dict with default O-U parameters is created first — this makes
    sweeps of, e.g., ``co2.mu`` work on scenarios that inherited the
    default ``CO2_SCENARIOS['base']``.

    Args:
        cfg: Source config.
        which: Attribute name on ``SimulationConfig`` (e.g.
            ``'gas_scenario'``).
        field: Field on the scenario dict (``mu``, ``sigma``, ``theta``).
        value: New scalar value.
    """
    current = getattr(cfg, which)
    if current is None:
        # Instantiate a minimal O-U dict; the value about to be applied
        # will override the requested field anyway.
        current = {"mu": 50.0, "sigma": 10.0, "theta": 0.05}
    new_scenario = dict(current)
    new_scenario[field] = float(value)
    return replace(cfg, **{which: new_scenario})


def _apply_override(
    cfg: SimulationConfig,
    path: str,
    value: float,
) -> SimulationConfig:
    """Apply a single dotted override to ``cfg``.

    Implemented as a dispatch-by-prefix rather than a generic recursive
    setattr because the override surface is small and must be
    whitelisted — we do not want users to rewrite arbitrary internals
    of the config through the REST endpoint.

    Args:
        cfg: Source config.
        path: Dotted path, e.g. ``mix.nuclear.capacity_gw``.
        value: New scalar value.

    Returns:
        A fresh ``SimulationConfig`` with the override applied.

    Raises:
        ValueError: If ``path`` is not recognised.
    """
    parts = path.split(".")
    if parts[0] == "mix":
        if len(parts) != 3:
            raise ValueError(
                f"mix overrides need exactly 3 components; got '{path}'")
        return _set_mix_field(cfg, parts[1], parts[2], value)
    if parts[0] in ("gas", "coal", "co2"):
        if len(parts) != 2:
            raise ValueError(
                f"fuel overrides need exactly 2 components; got '{path}'")
        which = {"gas": "gas_scenario",
                 "coal": "coal_scenario",
                 "co2": "co2_scenario"}[parts[0]]
        return _set_fuel_field(cfg, which, parts[1], value)
    if path == "load_noise":
        return replace(cfg, load_noise=float(value))
    raise ValueError(f"unknown override path: '{path}'")


# ---------------------------------------------------------------------------
# Grid + runner
# ---------------------------------------------------------------------------

def build_grid(
    sweep_type: str,
    values_a: list[float],
    values_b: list[float] | None,
) -> list[tuple[float, float | None]]:
    """Enumerate the (a, b) grid points in row-major order.

    The frontend relies on row-major ordering (``a`` slow, ``b`` fast)
    to reshape ``points`` into a 2D matrix for the heatmap chart.

    Args:
        sweep_type: ``'1d'`` or ``'2d'``.
        values_a: Grid values for parameter A.
        values_b: Grid values for parameter B (required if 2D).

    Returns:
        List of ``(a, b)`` pairs. For 1D sweeps ``b`` is always ``None``.

    Raises:
        ValueError: On an unknown ``sweep_type`` or missing 2D values.
    """
    if sweep_type == "1d":
        return [(float(a), None) for a in values_a]
    if sweep_type == "2d":
        if not values_b:
            raise ValueError("2d sweep requires values_b")
        return [
            (float(a), float(b))
            for a in values_a
            for b in values_b
        ]
    raise ValueError(f"unknown sweep_type: '{sweep_type}'")


def run_sweep_point(
    base_cfg: SimulationConfig,
    parameter_a: str,
    value_a: float,
    parameter_b: str | None,
    value_b: float | None,
    n_runs: int,
    seed: int,
) -> dict[str, float]:
    """Execute one grid point and return its aggregate scalar metrics.

    Applies the two overrides (A always, B when 2D), runs
    ``n_runs`` Monte Carlo simulations, and returns a dict with the
    aggregated statistics that the heatmap / line-chart charts display.

    Args:
        base_cfg: Base scenario config (never mutated).
        parameter_a: Override path for axis A.
        value_a: Current grid value for A.
        parameter_b: Override path for axis B (``None`` for 1D).
        value_b: Current grid value for B (``None`` for 1D).
        n_runs: Monte Carlo runs to execute at this point.
        seed: RNG seed. Offset per-point by the caller so that two
            adjacent grid points do not reuse the same fuel-price path.

    Returns:
        Dict with keys ``avg_price_mean``, ``avg_price_std``,
        ``carbon_intensity_mean``, ``avg_inertia_mean``,
        ``curtailment_mean`` — all floats.
    """
    cfg = _apply_override(base_cfg, parameter_a, value_a)
    if parameter_b is not None and value_b is not None:
        cfg = _apply_override(cfg, parameter_b, value_b)
    cfg = replace(cfg, n_runs=n_runs, seed=seed)

    mc = run_monte_carlo(cfg)
    return {
        "avg_price_mean": float(np.mean(mc.avg_price)),
        "avg_price_std": float(np.std(mc.avg_price)),
        "carbon_intensity_mean": float(np.mean(mc.carbon_intensity)),
        "avg_inertia_mean": float(np.mean(mc.avg_inertia)),
        "curtailment_mean": float(np.mean(mc.curtailment)),
    }


def run_sweep(
    base_cfg: SimulationConfig,
    sweep_type: str,
    parameter_a: str,
    values_a: list[float],
    parameter_b: str | None,
    values_b: list[float] | None,
    n_runs_per_point: int,
    seed: int = 42,
    progress_cb: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Execute the full grid and return the ordered list of points.

    Each grid point reseeds the Monte Carlo engine with ``seed + point_idx``
    so adjacent points exercise independent stochastic paths. Progress
    is reported after every point completes, which is fine-grained
    enough for the frontend to render a smooth progress bar.

    Args:
        base_cfg: Base scenario config.
        sweep_type: ``'1d'`` or ``'2d'``.
        parameter_a: Override path for axis A.
        values_a: Grid values for axis A.
        parameter_b: Override path for axis B (``None`` for 1D).
        values_b: Grid values for axis B (``None`` for 1D).
        n_runs_per_point: MC runs per grid point.
        seed: Base RNG seed.
        progress_cb: Optional callback ``(current, total)`` invoked
            after each grid point completes. Used by the background
            worker to persist progress to SQLite.

    Returns:
        List of dicts, one per grid point in row-major order. Each dict
        has the axis values (``a`` always, ``b`` when 2D) and the
        aggregate metric fields — ready to serialise into
        :class:`SweepResultPoint` objects on the route layer.
    """
    grid = build_grid(sweep_type, values_a, values_b)
    total = len(grid)
    results: list[dict[str, Any]] = []
    for i, (a, b) in enumerate(grid):
        metrics = run_sweep_point(
            base_cfg,
            parameter_a, a,
            parameter_b, b,
            n_runs=n_runs_per_point,
            seed=seed + i,
        )
        point: dict[str, Any] = {"a": a, **metrics}
        if b is not None:
            point["b"] = b
        results.append(point)
        if progress_cb is not None:
            progress_cb(i + 1, total)
    return results
