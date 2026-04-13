"""Layer 2 backtest: Elo-baseline + TSFM ensemble forecast at tie date.

At each tie's first-leg date we:
  1. Truncate each team's clubelo history to rows ending strictly before that date
  2. Resample to weekly (TSFM_CONTEXT_WEEKS)
  3. Run 3 TSFM models (Chronos-2, TimesFM-2.5, FlowState) → forecasted Elo
  4. Ensemble with truncated-Elo baseline
  5. Simulate the tie with ensemble Elos
"""

from __future__ import annotations

import gc
import importlib
import logging
import time
from dataclasses import asdict

import numpy as np
import pandas as pd

from backtest.data_loader import fetch_team_history, load_seasons, truncate_history
from backtest.runner import TieResult, predict_tie
from config import FOUNDATION_MODELS, TSFM_CONTEXT_WEEKS, TSFM_FORECAST_HORIZON
from data.elo import resample_to_weekly

log = logging.getLogger(__name__)
DEFAULT_N_SIMS = 5_000


def _collect_all_pairs(seasons: list[dict]) -> list[tuple[str, str]]:
    """Return sorted list of (team, tie_date) pairs needed across all ties."""
    pairs: set[tuple[str, str]] = set()
    for s in seasons:
        for t in s["ties"]:
            pairs.add((t["home_team"], t["first_leg_date"]))
            pairs.add((t["away_team"], t["first_leg_date"]))
    return sorted(pairs)


def _build_truncated_series(team: str, date: str) -> np.ndarray | None:
    """Fetch team history, truncate to date, resample to weekly. None on error."""
    try:
        hist = fetch_team_history(team)
    except Exception as exc:
        log.warning("History fetch failed for %s: %s", team, exc)
        return None
    trunc = truncate_history(hist, date)
    if len(trunc) == 0:
        log.warning("No pre-date history for %s before %s", team, date)
        return None
    try:
        return resample_to_weekly(trunc, n_weeks=TSFM_CONTEXT_WEEKS)
    except Exception as exc:
        log.warning("Resample failed for %s @ %s: %s", team, date, exc)
        return None


def _forecast_all_pairs(
    pair_series: dict[tuple[str, str], np.ndarray],
    horizon: int = TSFM_FORECAST_HORIZON,
) -> dict[str, dict[tuple[str, str], float]]:
    """Run all 3 TSFM models on every (team, date) pair. Returns forecasted Elo at week 0."""
    out: dict[str, dict[tuple[str, str], float]] = {}
    pairs = sorted(pair_series.keys())

    for mod_path, cls_name in FOUNDATION_MODELS:
        log.info("Loading %s …", cls_name)
        module = importlib.import_module(mod_path)
        cls = getattr(module, cls_name)
        model = cls()
        model_name = model.name

        out[model_name] = {}
        t_start = time.perf_counter()
        for i, key in enumerate(pairs, start=1):
            series = pair_series[key]
            try:
                result = model.predict(series, horizon)
                elo_week0 = float(result["point_forecast"][0])
                out[model_name][key] = elo_week0
            except Exception as exc:
                log.warning("%s forecast failed for %s: %s", model_name, key, exc)
            if i % 20 == 0:
                elapsed = time.perf_counter() - t_start
                log.info("  %s: %d/%d (%.1fs elapsed)", model_name, i, len(pairs), elapsed)

        elapsed = time.perf_counter() - t_start
        log.info("%s: %d pairs in %.1fs", model_name, len(pairs), elapsed)
        model.cleanup()
        del model
        gc.collect()

    return out


def _ensemble_elo(
    key: tuple[str, str],
    model_forecasts: dict[str, dict[tuple[str, str], float]],
    baseline_elo: float,
) -> float:
    """Average all TSFM model forecasts + Elo-baseline for this (team, date) key."""
    values = [baseline_elo]
    for mname, fmap in model_forecasts.items():
        v = fmap.get(key)
        if v is not None:
            values.append(v)
    return float(np.mean(values))


def run_backtest_layer2(n_sims: int = DEFAULT_N_SIMS) -> pd.DataFrame:
    """Full Layer 2 backtest loop."""
    seasons = load_seasons()
    total_ties = sum(len(s["ties"]) for s in seasons)

    # Step 1: collect unique (team, date) pairs and their truncated weekly Elo series
    print(f"\nCollecting truncated histories for all ties …")
    pairs = _collect_all_pairs(seasons)
    pair_series: dict[tuple[str, str], np.ndarray] = {}
    missing_pairs: list[tuple[str, str]] = []
    for key in pairs:
        team, date = key
        s = _build_truncated_series(team, date)
        if s is None:
            missing_pairs.append(key)
        else:
            pair_series[key] = s
    print(f"  {len(pair_series)}/{len(pairs)} pairs with usable history "
          f"({len(missing_pairs)} missing)")

    # Step 2: batch forecast across all models
    print(f"\nRunning TSFM forecasts on {len(pair_series)} (team,date) pairs …")
    model_forecasts = _forecast_all_pairs(pair_series)

    # Step 3: iterate ties, ensemble, simulate
    print(f"\nSimulating {total_ties} ties with ensemble Elo …")
    rows: list[dict] = []
    idx = 0
    for season_obj in seasons:
        season = season_obj["season"]
        for tie in season_obj["ties"]:
            idx += 1
            home, away = tie["home_team"], tie["away_team"]
            date = tie["first_leg_date"]
            actual = tie["winner"]
            is_single = tie.get("is_single_match", False)

            # Elo baseline at date = last value of the truncated weekly series
            s_home = pair_series.get((home, date))
            s_away = pair_series.get((away, date))
            if s_home is None or s_away is None:
                log.warning("Skipping tie (missing history): %s vs %s on %s",
                            home, away, date)
                continue

            baseline_home = float(s_home[-1])
            baseline_away = float(s_away[-1])
            elo_home = _ensemble_elo((home, date), model_forecasts, baseline_home)
            elo_away = _ensemble_elo((away, date), model_forecasts, baseline_away)

            elos = {home: elo_home, away: elo_away}
            p_home = predict_tie(home, away, elos, is_single, n_sims=n_sims)

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
                        home_elo=round(elo_home, 1),
                        away_elo=round(elo_away, 1),
                        model_pick=model_pick,
                        correct=correct,
                        brier=round(brier, 4),
                        log_loss=round(log_loss, 4),
                        prediction_date=date,
                    )
                )
            )

            marker = "✓" if correct else "✗"
            print(
                f"  [{idx}/{total_ties}] {season} {tie['stage']:5s}"
                f" {home:22s} vs {away:22s}"
                f" | P(home)={p_home:.2f} Elo(ens)={elo_home:.0f}-{elo_away:.0f}"
                f" | actual={actual:22s} {marker}"
            )

    return pd.DataFrame(rows)
