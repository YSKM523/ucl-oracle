"""Metrics for backtest evaluation."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def hit_rate(df: pd.DataFrame) -> float:
    return float(df["correct"].mean())


def brier_score(df: pd.DataFrame) -> float:
    return float(df["brier"].mean())


def avg_log_loss(df: pd.DataFrame) -> float:
    return float(df["log_loss"].mean())


def baseline_metrics(df: pd.DataFrame) -> dict:
    """Return {metric: value} for a coin-flip baseline (p=0.5 for every tie)."""
    n = len(df)
    return {
        "hit_rate": 0.50,
        "brier": 0.25,       # (0.5-0)^2 = 0.25 for any outcome
        "log_loss": float(-math.log(0.5)),
    }


def binomial_pvalue(n_correct: int, n_total: int, baseline: float = 0.5) -> float:
    """One-sided p-value that hit rate > baseline (normal approx)."""
    if n_total == 0:
        return float("nan")
    phat = n_correct / n_total
    se = math.sqrt(baseline * (1 - baseline) / n_total)
    if se == 0:
        return float("nan")
    z = (phat - baseline) / se
    # one-sided upper tail
    return 0.5 * math.erfc(z / math.sqrt(2))


def calibration_bins(df: pd.DataFrame, n_bins: int = 5) -> pd.DataFrame:
    """Return calibration table: predicted bucket → mean predicted prob, actual hit rate, count."""
    # Use the "predicted prob for actual winner" to compute calibration —
    # each row contributes its prediction for the home side, compared to home actually winning.
    rows = []
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (df["p_home_advances"] >= lo) & (df["p_home_advances"] < hi + 1e-9)
        sub = df[mask]
        if len(sub) == 0:
            continue
        predicted_mean = float(sub["p_home_advances"].mean())
        actual_rate = float((sub["actual_winner"] == sub["home_team"]).mean())
        rows.append(
            {
                "bin": f"[{lo:.2f}, {hi:.2f})",
                "n": len(sub),
                "predicted_mean": round(predicted_mean, 3),
                "actual_hit_rate": round(actual_rate, 3),
            }
        )
    return pd.DataFrame(rows)


def per_stage(df: pd.DataFrame) -> pd.DataFrame:
    """Hit rate / Brier / log loss grouped by stage."""
    g = df.groupby("stage", sort=False).agg(
        n=("correct", "size"),
        hit_rate=("correct", "mean"),
        brier=("brier", "mean"),
        log_loss=("log_loss", "mean"),
    )
    return g.round(3).reset_index()


def per_season(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("season", sort=True).agg(
        n=("correct", "size"),
        hit_rate=("correct", "mean"),
        brier=("brier", "mean"),
        log_loss=("log_loss", "mean"),
    )
    return g.round(3).reset_index()


def confidence_bucket_hitrate(df: pd.DataFrame) -> pd.DataFrame:
    """How often is the model right when it's very confident vs mildly confident?"""
    # Confidence = max(p, 1-p)
    df = df.copy()
    df["confidence"] = df["p_home_advances"].apply(lambda p: max(p, 1 - p))
    buckets = [
        (0.50, 0.55, "coin flip (50-55%)"),
        (0.55, 0.65, "mild (55-65%)"),
        (0.65, 0.75, "moderate (65-75%)"),
        (0.75, 1.01, "high (≥75%)"),
    ]
    rows = []
    for lo, hi, label in buckets:
        mask = (df["confidence"] >= lo) & (df["confidence"] < hi)
        sub = df[mask]
        if len(sub) == 0:
            continue
        rows.append(
            {
                "confidence": label,
                "n": len(sub),
                "hit_rate": round(float(sub["correct"].mean()), 3),
            }
        )
    return pd.DataFrame(rows)
