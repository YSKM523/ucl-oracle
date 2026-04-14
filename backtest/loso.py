"""Leave-One-Season-Out (LOSO) validation framework.

For each season in turn, we treat it as the held-out test set and let the
caller "train" (i.e. select hyper-parameters) using only the other seasons.
This prevents silent in-sample tuning: if a new signal's hypers are fit on
every season's results, LOSO exposes the overfit by shrinking test-season
performance.

Layer 1 (pure Elo + canonical Poisson constants) has **no tunable
hyper-parameters** — the hit rate is invariant to the train/test split by
construction. That makes its 63.9% result effectively already OOS.

The framework here is designed for Layer 3+ where xG-blend α, first-leg
Elo K, residual CAP, and injury tiers would be fit on training seasons
and evaluated only on held-out ones.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Iterable

import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class LOSOResult:
    held_out_season: str
    hypers: dict
    n_test: int
    n_correct_test: int
    hit_rate_test: float
    brier_test: float
    log_loss_test: float
    train_seasons: tuple[str, ...]


SeasonPredictor = Callable[[list[dict], dict], pd.DataFrame]
"""A function (held_out_tie_dicts, hypers) -> DataFrame with columns
correct (bool), brier (float), log_loss (float). The hypers dict is
whatever the signal needs; LOSO never inspects it."""

HyperTuner = Callable[[list[dict]], dict]
"""A function training_tie_dicts -> best hypers. Called once per
held-out fold. For signals with no tunables, just return ``{}``."""


def run_loso(
    seasons_payload: list[dict],
    predictor: SeasonPredictor,
    tuner: HyperTuner,
) -> list[LOSOResult]:
    """For each season in turn, tune on the rest, evaluate on that one.

    Parameters
    ----------
    seasons_payload : list of {"season": str, "ties": list[tie_dict]}
    predictor       : callable run on held-out ties with tuned hypers
    tuner           : callable that fits hypers on training ties

    Returns
    -------
    list of LOSOResult, one per season.
    """
    results: list[LOSOResult] = []
    season_names = [s["season"] for s in seasons_payload]

    for i, held_out in enumerate(seasons_payload):
        name = held_out["season"]
        test_ties = held_out["ties"]
        train_ties: list[dict] = []
        for j, s in enumerate(seasons_payload):
            if j == i:
                continue
            train_ties.extend(s["ties"])

        hypers = tuner(train_ties)
        df = predictor(test_ties, hypers)

        if df.empty:
            log.warning("LOSO fold %s produced empty test output", name)
            continue

        n = len(df)
        n_correct = int(df["correct"].sum())
        results.append(
            LOSOResult(
                held_out_season=name,
                hypers=hypers,
                n_test=n,
                n_correct_test=n_correct,
                hit_rate_test=float(df["correct"].mean()),
                brier_test=float(df["brier"].mean()),
                log_loss_test=float(df["log_loss"].mean()),
                train_seasons=tuple(n for j, n in enumerate(season_names) if j != i),
            )
        )

    return results


def summarize_loso(results: list[LOSOResult]) -> pd.DataFrame:
    """Turn per-fold LOSOResult rows into a summary DataFrame."""
    if not results:
        return pd.DataFrame()
    rows = []
    for r in results:
        rows.append(
            {
                "held_out": r.held_out_season,
                "n_test": r.n_test,
                "hit_rate": round(r.hit_rate_test, 3),
                "brier": round(r.brier_test, 3),
                "log_loss": round(r.log_loss_test, 3),
                "hypers": ", ".join(f"{k}={v}" for k, v in r.hypers.items()) or "—",
            }
        )
    df = pd.DataFrame(rows)
    total_n = df["n_test"].sum()
    pooled = {
        "held_out": "POOLED (micro)",
        "n_test": total_n,
        "hit_rate": round(sum(r.n_correct_test for r in results) / total_n, 3),
        "brier": round(
            sum(r.brier_test * r.n_test for r in results) / total_n, 3
        ),
        "log_loss": round(
            sum(r.log_loss_test * r.n_test for r in results) / total_n, 3
        ),
        "hypers": "—",
    }
    return pd.concat([df, pd.DataFrame([pooled])], ignore_index=True)
