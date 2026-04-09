"""Elo trajectory and TSFM forecast visualizations."""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from config import PLOTS_DIR, TSFM_FORECAST_HORIZON


def plot_team_elo_trajectories(
    weekly_series: dict[str, np.ndarray],
    save_path=None,
    n_recent_weeks: int = 104,
):
    """Plot Elo trajectories for all 8 teams (last 2 years)."""
    if save_path is None:
        save_path = PLOTS_DIR / "elo_trajectories.png"

    fig, ax = plt.subplots(figsize=(14, 7))

    # Create date index (approximate — weekly ending on most recent Sunday)
    end_date = pd.Timestamp.now().normalize()
    # Find most recent Sunday
    while end_date.dayofweek != 6:
        end_date -= pd.Timedelta(days=1)

    colors = plt.cm.tab10(np.linspace(0, 1, 8))

    for i, (team, series) in enumerate(sorted(weekly_series.items(),
                                               key=lambda x: x[1][-1],
                                               reverse=True)):
        recent = series[-n_recent_weeks:]
        dates = pd.date_range(end=end_date, periods=len(recent), freq="W-SUN")
        ax.plot(dates, recent, label=f"{team} ({recent[-1]:.0f})",
                color=colors[i], linewidth=2, alpha=0.85)

    # Tournament window
    ax.axvspan(pd.Timestamp("2026-04-14"), pd.Timestamp("2026-05-30"),
               alpha=0.1, color="gold", label="UCL knockout window")

    ax.set_ylabel("Club Elo Rating", fontsize=12)
    ax.set_title("Club Elo Trajectories — UCL QF Teams (Last 2 Years)", fontsize=14, fontweight="bold")
    ax.legend(loc="upper left", fontsize=9, ncol=2)
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=30)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved trajectories: {save_path}")


def plot_team_forecast(
    team: str,
    weekly_series: np.ndarray,
    forecasts: dict[str, dict],
    save_path=None,
    n_context_weeks: int = 52,
):
    """Plot one team's Elo history + TSFM forecast fan chart."""
    if save_path is None:
        save_path = PLOTS_DIR / f"forecast_{team.replace(' ', '_').lower()}.png"

    fig, ax = plt.subplots(figsize=(12, 6))

    # Historical
    end_date = pd.Timestamp.now().normalize()
    while end_date.dayofweek != 6:
        end_date -= pd.Timedelta(days=1)

    context = weekly_series[-n_context_weeks:]
    hist_dates = pd.date_range(end=end_date, periods=len(context), freq="W-SUN")
    ax.plot(hist_dates, context, "k-", linewidth=2, label="Historical Elo", alpha=0.8)

    # Forecasts
    model_colors = {"Chronos-2": "#c62828", "TimesFM-2.5": "#1565c0", "FlowState": "#2e7d32"}
    forecast_dates = pd.date_range(start=end_date + pd.Timedelta(weeks=1),
                                   periods=TSFM_FORECAST_HORIZON, freq="W-SUN")

    for model_name, pred in forecasts.items():
        color = model_colors.get(model_name, "#666")
        point = pred["point_forecast"][:TSFM_FORECAST_HORIZON]
        q10 = pred["quantile_10"][:TSFM_FORECAST_HORIZON]
        q90 = pred["quantile_90"][:TSFM_FORECAST_HORIZON]

        dates = forecast_dates[:len(point)]
        ax.plot(dates, point, color=color, linewidth=1.5, label=model_name)
        ax.fill_between(dates, q10, q90, alpha=0.12, color=color)

    # Tournament window
    ax.axvspan(pd.Timestamp("2026-04-14"), pd.Timestamp("2026-05-30"),
               alpha=0.1, color="gold", label="UCL knockout window")

    ax.set_ylabel("Elo Rating", fontsize=12)
    ax.set_title(f"{team} — Elo Forecast", fontsize=14, fontweight="bold")
    ax.legend(loc="best", fontsize=9)
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    plt.xticks(rotation=30)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved forecast: {save_path}")
