"""Convert clubelo.com period data to weekly time series for TSFM input."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from config import TSFM_CONTEXT_WEEKS

log = logging.getLogger(__name__)


def resample_to_weekly(history_df: pd.DataFrame, n_weeks: int = TSFM_CONTEXT_WEEKS) -> np.ndarray:
    """Convert clubelo.com period-format data to a weekly Elo time series.

    Each row in history_df has (date_from, date_to, elo) meaning the club
    had that Elo from date_from through date_to.

    Returns
    -------
    np.ndarray of shape (n_weeks,) — last n_weeks of Sunday-ending weekly Elo.
    """
    # Expand periods to daily frequency
    daily_records = []
    for _, row in history_df.iterrows():
        dates = pd.date_range(row["date_from"], row["date_to"], freq="D")
        for d in dates:
            daily_records.append({"date": d, "elo": row["elo"]})

    if not daily_records:
        raise ValueError("No Elo data to resample")

    daily_df = pd.DataFrame(daily_records)
    daily_df = daily_df.drop_duplicates(subset="date", keep="last")
    daily_df = daily_df.set_index("date").sort_index()

    # Resample to weekly (Sunday-ending), forward-fill gaps
    weekly = daily_df["elo"].resample("W-SUN").last().ffill()

    # Take last n_weeks
    arr = weekly.values[-n_weeks:]

    if len(arr) < n_weeks:
        # Pad front with earliest value if history is shorter than n_weeks
        pad = np.full(n_weeks - len(arr), arr[0])
        arr = np.concatenate([pad, arr])

    return arr.astype(np.float64)


def build_all_weekly_series(
    histories: dict[str, pd.DataFrame],
    n_weeks: int = TSFM_CONTEXT_WEEKS,
) -> dict[str, np.ndarray]:
    """Build weekly Elo series for all teams.

    Parameters
    ----------
    histories : {team: DataFrame from fetch_club_history}

    Returns
    -------
    {team: np.ndarray of shape (n_weeks,)}
    """
    series = {}
    for team, hist_df in histories.items():
        series[team] = resample_to_weekly(hist_df, n_weeks)
        log.info("%s: %d weeks, latest Elo = %.1f", team, len(series[team]), series[team][-1])
    return series
