"""Sensitivity analysis: how much does Layer 1's hit rate depend on the
canonical Poisson constants?

We perturb three values that actually feed the Monte Carlo simulation in
the Elo-baseline backtest:

    POISSON_AVG_GOALS       (2.7 default)  — UCL knockout avg total goals
    UCL_HOME_ADVANTAGE_ELO  (65 default)   — home advantage in Elo points
    KNOCKOUT_PENALTY_ADVANTAGE (0.55)      — Bradley-Terry-style nudge
                                              toward stronger team in pens

These are canonical from football analytics literature, not fit from data.
If Layer 1's 63.9% is robust, hit rate should barely move across ±50%
perturbations. If it wobbles by >5pp, our "no tuning" claim is weaker.

The sweep monkey-patches the constant inside
``prediction.knockout_simulator`` for each run, then restores it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

import prediction.knockout_simulator as ks
import prediction.match_predictor as mp
from backtest.runner import run_backtest

log = logging.getLogger(__name__)


@dataclass
class SweepRow:
    param: str
    value: float
    n: int
    hit_rate: float
    brier: float
    delta_hit_rate: float


DEFAULT_GRIDS: dict[str, list[float]] = {
    "POISSON_AVG_GOALS": [2.3, 2.5, 2.7, 2.9, 3.1],
    "UCL_HOME_ADVANTAGE_ELO": [30, 50, 65, 80, 100],
    "KNOCKOUT_PENALTY_ADVANTAGE": [0.50, 0.525, 0.55, 0.575, 0.60],
}


def _baseline() -> tuple[float, float]:
    df = run_backtest(n_sims=3_000)
    return float(df["correct"].mean()), float(df["brier"].mean())


def _run_with_patch(param: str, value: float) -> tuple[float, float]:
    """Run the backtest with one knob temporarily overridden."""
    # Both modules import the constant by name. Patch wherever it is bound.
    targets = []
    for module in (ks, mp):
        if hasattr(module, param):
            targets.append(module)

    originals = {m: getattr(m, param) for m in targets}
    try:
        for m in targets:
            setattr(m, param, value)
        df = run_backtest(n_sims=3_000)
        return float(df["correct"].mean()), float(df["brier"].mean())
    finally:
        for m, v in originals.items():
            setattr(m, param, v)


def sweep_params(
    grids: dict[str, list[float]] | None = None,
) -> pd.DataFrame:
    if grids is None:
        grids = DEFAULT_GRIDS

    print("Running baseline …")
    base_hit, base_brier = _baseline()
    print(f"  baseline hit_rate = {base_hit:.3f}, brier = {base_brier:.3f}")

    rows: list[SweepRow] = []
    for param, grid in grids.items():
        print(f"\nSweeping {param} …")
        for v in grid:
            hr, br = _run_with_patch(param, v)
            delta = hr - base_hit
            print(f"  {param} = {v:>6}: hit_rate = {hr:.3f} "
                  f"(Δ {delta:+.3f}), brier = {br:.3f}")
            rows.append(
                SweepRow(
                    param=param, value=float(v),
                    n=83, hit_rate=round(hr, 4),
                    brier=round(br, 4),
                    delta_hit_rate=round(delta, 4),
                )
            )

    return pd.DataFrame([r.__dict__ for r in rows])
