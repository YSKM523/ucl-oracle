"""Level 1: Forecast team Elo trajectories using TSFM models."""

from __future__ import annotations

import gc
import importlib
import logging
import time

import numpy as np

from config import FOUNDATION_MODELS, TSFM_FORECAST_HORIZON, UCL_TEAMS

log = logging.getLogger(__name__)


def forecast_all_teams(
    team_elo_series: dict[str, np.ndarray],
    horizon: int = TSFM_FORECAST_HORIZON,
) -> dict[str, dict[str, dict]]:
    """Run all TSFM models on all 8 teams' Elo histories.

    Memory pattern: load one model → iterate all teams → cleanup → gc.collect.

    Parameters
    ----------
    team_elo_series : {team_name: np.ndarray of weekly Elo values}
    horizon : Number of weeks to forecast forward

    Returns
    -------
    {model_name: {team_name: predict_result_dict}}
    """
    all_forecasts: dict[str, dict[str, dict]] = {}

    for mod_path, cls_name in FOUNDATION_MODELS:
        log.info("Loading %s …", cls_name)
        module = importlib.import_module(mod_path)
        cls = getattr(module, cls_name)
        model = cls()

        model_name = model.name
        all_forecasts[model_name] = {}

        t_start = time.perf_counter()
        for team in sorted(team_elo_series.keys()):
            history = team_elo_series[team]
            result = model.predict(history, horizon)
            all_forecasts[model_name][team] = result

        elapsed = time.perf_counter() - t_start
        log.info(
            "%s: forecasted %d teams in %.1fs (%.2fs/team)",
            model_name, len(team_elo_series), elapsed,
            elapsed / max(len(team_elo_series), 1),
        )

        model.cleanup()
        del model
        gc.collect()

    return all_forecasts


def get_elo_at_week(
    forecasts: dict[str, dict[str, dict]],
    week_index: int = 0,
) -> dict[str, dict[str, float]]:
    """Extract forecasted Elo at a specific week for each model and team.

    Parameters
    ----------
    forecasts : Output of forecast_all_teams
    week_index : 0 = first forecast week (QF), 3 = SF, 7 = Final

    Returns
    -------
    {model_name: {team: forecasted_elo}}
    """
    result = {}
    for model_name, team_forecasts in forecasts.items():
        result[model_name] = {}
        for team, pred in team_forecasts.items():
            idx = min(week_index, len(pred["point_forecast"]) - 1)
            result[model_name][team] = float(pred["point_forecast"][idx])
    return result


def get_elo_with_uncertainty(
    forecasts: dict[str, dict[str, dict]],
    week_index: int = 0,
) -> dict[str, dict[str, dict[str, float]]]:
    """Like get_elo_at_week but includes uncertainty bounds.

    Returns
    -------
    {model_name: {team: {"point": float, "q10": float, "q90": float}}}
    """
    result = {}
    for model_name, team_forecasts in forecasts.items():
        result[model_name] = {}
        for team, pred in team_forecasts.items():
            idx = min(week_index, len(pred["point_forecast"]) - 1)
            result[model_name][team] = {
                "point": float(pred["point_forecast"][idx]),
                "q10": float(pred["quantile_10"][idx]),
                "q90": float(pred["quantile_90"][idx]),
            }
    return result
