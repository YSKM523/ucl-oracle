"""Backtest runner: predict each historical tie using pre-tie Elos, compare to actual."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtest.data_loader import get_elos_at_date, load_seasons
from prediction.knockout_simulator import simulate_final, simulate_two_leg_tie

log = logging.getLogger(__name__)

DEFAULT_N_SIMS = 5_000


@dataclass
class TieResult:
    season: str
    stage: str
    home_team: str
    away_team: str
    actual_winner: str
    p_home_advances: float
    home_elo: float
    away_elo: float
    model_pick: str       # team predicted more likely to advance
    correct: bool         # did model pick the actual winner
    brier: float          # (p_pred_for_actual - 1)^2 contribution
    log_loss: float       # -log(p_pred_for_actual)
    prediction_date: str


def predict_tie(
    home_team: str,
    away_team: str,
    elos: dict[str, float],
    is_single_match: bool,
    n_sims: int,
    seed: int = 42,
) -> float:
    """Return P(home_team advances/wins) via Monte Carlo."""
    rng = np.random.default_rng(seed)
    home_wins = 0
    if is_single_match:
        for _ in range(n_sims):
            w = simulate_final(home_team, away_team, elos, rng)
            if w == home_team:
                home_wins += 1
    else:
        for _ in range(n_sims):
            w = simulate_two_leg_tie(home_team, away_team, elos, rng)
            if w == home_team:
                home_wins += 1
    return home_wins / n_sims


def run_backtest(n_sims: int = DEFAULT_N_SIMS) -> pd.DataFrame:
    """Loop over all seasons × ties, predict using pre-tie Elos, record scores."""
    rows: list[TieResult] = []
    seasons = load_seasons()
    total = sum(len(s["ties"]) for s in seasons)
    idx = 0

    for season_obj in seasons:
        season = season_obj["season"]
        for tie in season_obj["ties"]:
            idx += 1
            home = tie["home_team"]
            away = tie["away_team"]
            actual = tie["winner"]
            date = tie["first_leg_date"]
            is_single = tie.get("is_single_match", False)

            # Fetch Elos at the day before first leg to avoid leakage
            try:
                elos = get_elos_at_date([home, away], date)
            except Exception as exc:
                log.warning("Elo fetch failed for %s (%s): %s", date, season, exc)
                continue

            if elos.get(home) is None or elos.get(away) is None:
                missing = [t for t in (home, away) if elos.get(t) is None]
                log.warning("Skipping tie (missing Elo for %s): %s vs %s on %s",
                            missing, home, away, date)
                continue

            p_home = predict_tie(home, away, elos, is_single, n_sims=n_sims)

            # Model pick = whichever team has >50% chance to advance
            model_pick = home if p_home >= 0.5 else away
            correct = model_pick == actual

            # Brier & log loss — use home-advances probability vs indicator
            actual_home_wins = 1.0 if actual == home else 0.0
            brier = (p_home - actual_home_wins) ** 2
            p_pred_for_actual = p_home if actual_home_wins == 1 else (1 - p_home)
            eps = 1e-9
            log_loss = -np.log(max(p_pred_for_actual, eps))

            rows.append(
                TieResult(
                    season=season,
                    stage=tie["stage"],
                    home_team=home,
                    away_team=away,
                    actual_winner=actual,
                    p_home_advances=round(p_home, 4),
                    home_elo=round(elos[home], 1),
                    away_elo=round(elos[away], 1),
                    model_pick=model_pick,
                    correct=correct,
                    brier=round(brier, 4),
                    log_loss=round(log_loss, 4),
                    prediction_date=date,
                )
            )

            marker = "✓" if correct else "✗"
            print(
                f"  [{idx}/{total}] {season} {tie['stage']:5s}"
                f" {home:22s} vs {away:22s}"
                f" | model P(home)={p_home:.2f} | actual={actual:22s} {marker}"
            )

    return pd.DataFrame([r.__dict__ for r in rows])
