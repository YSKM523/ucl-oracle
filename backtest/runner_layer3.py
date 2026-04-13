"""Layer 3 backtest: predict remaining tie outcome given known first-leg result.

Unlike Layers 1/2 (which simulate both legs from scratch), Layer 3 reflects
the live pipeline's use case: the first leg has been played, its xG is known,
and we need to predict who advances by simulating only the second leg.

Two variants per tie:
  - L3a (baseline): Elo + actual first-leg score, no xG signal
  - L3b (with xG):  apply xG-residual Elo adjustment, then simulate 2nd leg

Comparing L3b vs L3a isolates the xG adjustment's incremental value.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.data_loader import get_elos_at_date, load_seasons
from backtest.runner import TieResult
from config import UCL_HOME_ADVANTAGE_ELO
from prediction.knockout_simulator import simulate_second_leg
from prediction.match_predictor import poisson_expected_goals

log = logging.getLogger(__name__)
DEFAULT_N_SIMS = 5_000

HISTORICAL_XG_CACHE = Path(__file__).resolve().parent / "fixtures" / "historical_xg.json"


def load_historical_xg() -> dict[str, dict[str, dict]]:
    if not HISTORICAL_XG_CACHE.exists():
        return {}
    return json.loads(HISTORICAL_XG_CACHE.read_text())


def compute_leg_elo_delta(
    elo_home: float,
    elo_away: float,
    home_goals: int,
    away_goals: int,
    home_xg: float | None = None,
    away_xg: float | None = None,
    alpha: float = 0.6,
    k: float = 10.0,
    cap: float = 2.5,
) -> float:
    """Return ΔElo (positive = shift toward home team)."""
    observed_gd = home_goals - away_goals
    if home_xg is not None and away_xg is not None:
        xgd = home_xg - away_xg
        effective_gd = alpha * xgd + (1 - alpha) * observed_gd
    else:
        effective_gd = float(observed_gd)

    lam_h, lam_a = poisson_expected_goals(elo_home, elo_away, UCL_HOME_ADVANTAGE_ELO)
    expected_gd = lam_h - lam_a
    residual = effective_gd - expected_gd
    return k * max(-cap, min(cap, residual))


def simulate_tie_given_first_leg(
    home_team: str,
    away_team: str,
    first_leg_home_goals: int,
    first_leg_away_goals: int,
    elo_home: float,
    elo_away: float,
    n_sims: int,
    seed: int = 42,
) -> float:
    """Return P(home_team advances) after 2nd leg given first-leg result."""
    rng = np.random.default_rng(seed)
    first_leg = {
        "home": home_team, "away": away_team,
        "home_goals": first_leg_home_goals, "away_goals": first_leg_away_goals,
    }
    elos = {home_team: elo_home, away_team: elo_away}
    wins = 0
    for _ in range(n_sims):
        adv = simulate_second_leg(first_leg, elos, rng)
        if adv == home_team:
            wins += 1
    return wins / n_sims


def run_backtest_layer3(
    use_xg: bool,
    n_sims: int = DEFAULT_N_SIMS,
) -> pd.DataFrame:
    """Run Layer 3 backtest. If use_xg=True, apply xG-based Elo adjustment."""
    seasons = load_seasons()
    xg_cache = load_historical_xg() if use_xg else {}
    rows: list[dict] = []

    total = sum(
        1 for s in seasons for t in s["ties"]
        if not t.get("is_single_match", False) and t.get("legs")
    )
    idx = 0

    for season_obj in seasons:
        season = season_obj["season"]
        for tie in season_obj["ties"]:
            if tie.get("is_single_match", False) or not tie.get("legs"):
                continue
            idx += 1

            home, away = tie["home_team"], tie["away_team"]
            actual = tie["winner"]
            legs = tie["legs"]
            first_leg = legs[0]
            first_date = first_leg["date"]

            # Elo at first-leg date (pre-match snapshot)
            try:
                elos = get_elos_at_date([home, away], first_date)
            except Exception as exc:
                log.warning("Elo fetch failed for %s: %s", first_date, exc)
                continue
            if elos.get(home) is None or elos.get(away) is None:
                log.warning("Missing Elo for tie %s vs %s on %s", home, away, first_date)
                continue
            elo_home, elo_away = elos[home], elos[away]

            # Optional xG-based adjustment
            home_xg = away_xg = None
            if use_xg:
                tie_xg = xg_cache.get(season, {}).get(
                    f"{tie['stage']}_{home}_vs_{away}"
                )
                if tie_xg is not None:
                    home_xg = tie_xg.get("home_xg")
                    away_xg = tie_xg.get("away_xg")
                # If xG missing, fall through with no adjustment (same as L3a)

            if use_xg and home_xg is not None and away_xg is not None:
                delta = compute_leg_elo_delta(
                    elo_home, elo_away,
                    first_leg["home_goals"], first_leg["away_goals"],
                    home_xg=home_xg, away_xg=away_xg,
                )
                elo_home_adj = elo_home + delta
                elo_away_adj = elo_away - delta
            else:
                elo_home_adj = elo_home
                elo_away_adj = elo_away

            p_home = simulate_tie_given_first_leg(
                home, away,
                first_leg["home_goals"], first_leg["away_goals"],
                elo_home_adj, elo_away_adj,
                n_sims=n_sims,
            )

            model_pick = home if p_home >= 0.5 else away
            correct = model_pick == actual
            actual_home_wins = 1.0 if actual == home else 0.0
            brier = (p_home - actual_home_wins) ** 2
            p_for_actual = p_home if actual_home_wins == 1 else (1 - p_home)
            log_loss = -np.log(max(p_for_actual, 1e-9))

            rows.append(
                asdict(
                    TieResult(
                        season=season,
                        stage=tie["stage"],
                        home_team=home,
                        away_team=away,
                        actual_winner=actual,
                        p_home_advances=round(p_home, 4),
                        home_elo=round(elo_home_adj, 1),
                        away_elo=round(elo_away_adj, 1),
                        model_pick=model_pick,
                        correct=correct,
                        brier=round(brier, 4),
                        log_loss=round(log_loss, 4),
                        prediction_date=first_leg["date"],
                    )
                )
            )

            marker = "✓" if correct else "✗"
            xg_tag = ""
            if use_xg and home_xg is not None:
                xg_tag = f" xG={home_xg:.2f}-{away_xg:.2f}"
            print(
                f"  [{idx}/{total}] {season} {tie['stage']:5s}"
                f" {home:22s} vs {away:22s}"
                f" | 1st leg {first_leg['home_goals']}-{first_leg['away_goals']}{xg_tag}"
                f" | P(home)={p_home:.2f} | actual={actual:22s} {marker}"
            )

    return pd.DataFrame(rows)
