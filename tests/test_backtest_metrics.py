"""Tests for backtest metrics."""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.metrics import (
    binomial_pvalue,
    brier_score,
    calibration_bins,
    confidence_bucket_hitrate,
    hit_rate,
    per_stage,
)


def _mk_df(rows):
    return pd.DataFrame(rows)


def test_hit_rate_perfect():
    df = _mk_df([
        {"correct": True, "brier": 0.0, "log_loss": 0.0, "p_home_advances": 0.9,
         "home_team": "A", "actual_winner": "A", "stage": "QF"},
        {"correct": True, "brier": 0.0, "log_loss": 0.0, "p_home_advances": 0.1,
         "home_team": "B", "actual_winner": "C", "stage": "QF"},
    ])
    assert hit_rate(df) == 1.0


def test_brier_matches_manual():
    # P(home)=0.7, home actually lost → brier = (0.7 - 0)^2 = 0.49
    df = _mk_df([{"correct": False, "brier": 0.49, "log_loss": 1.2, "p_home_advances": 0.7,
                  "home_team": "A", "actual_winner": "B", "stage": "R16"}])
    assert brier_score(df) == pytest.approx(0.49)


def test_binomial_pvalue_significant():
    # 40/50 correct, baseline 50% — very significant
    p = binomial_pvalue(40, 50, baseline=0.5)
    assert p < 0.001


def test_binomial_pvalue_at_baseline():
    p = binomial_pvalue(25, 50, baseline=0.5)
    assert p == pytest.approx(0.5, abs=0.01)


def test_per_stage_aggregates():
    df = _mk_df([
        {"correct": True, "brier": 0.1, "log_loss": 0.3, "stage": "R16",
         "p_home_advances": 0.8, "home_team": "A", "actual_winner": "A"},
        {"correct": False, "brier": 0.4, "log_loss": 1.0, "stage": "R16",
         "p_home_advances": 0.7, "home_team": "B", "actual_winner": "C"},
        {"correct": True, "brier": 0.05, "log_loss": 0.2, "stage": "QF",
         "p_home_advances": 0.9, "home_team": "D", "actual_winner": "D"},
    ])
    out = per_stage(df)
    r16_row = out[out["stage"] == "R16"].iloc[0]
    assert r16_row["n"] == 2
    assert r16_row["hit_rate"] == pytest.approx(0.5)
    qf_row = out[out["stage"] == "QF"].iloc[0]
    assert qf_row["hit_rate"] == pytest.approx(1.0)


def test_confidence_bucket_separates_high():
    df = _mk_df([
        # Two high-confidence, one correct one wrong
        {"correct": True, "p_home_advances": 0.9, "brier": 0, "log_loss": 0,
         "stage": "R16", "home_team": "A", "actual_winner": "A"},
        {"correct": False, "p_home_advances": 0.85, "brier": 0, "log_loss": 0,
         "stage": "R16", "home_team": "B", "actual_winner": "C"},
        # Three mild, two correct
        {"correct": True, "p_home_advances": 0.58, "brier": 0, "log_loss": 0,
         "stage": "R16", "home_team": "D", "actual_winner": "D"},
        {"correct": True, "p_home_advances": 0.6, "brier": 0, "log_loss": 0,
         "stage": "R16", "home_team": "E", "actual_winner": "E"},
        {"correct": False, "p_home_advances": 0.6, "brier": 0, "log_loss": 0,
         "stage": "R16", "home_team": "F", "actual_winner": "G"},
    ])
    out = confidence_bucket_hitrate(df)
    high = out[out["confidence"] == "high (≥75%)"].iloc[0]
    mild = out[out["confidence"] == "mild (55-65%)"].iloc[0]
    assert high["n"] == 2
    assert high["hit_rate"] == pytest.approx(0.5)
    assert mild["n"] == 3
    assert mild["hit_rate"] == pytest.approx(2 / 3, abs=0.001)


def test_calibration_bins_counts():
    df = _mk_df([
        {"p_home_advances": 0.05, "home_team": "A", "actual_winner": "B", "correct": False,
         "brier": 0, "log_loss": 0, "stage": "R16"},
        {"p_home_advances": 0.15, "home_team": "C", "actual_winner": "C", "correct": True,
         "brier": 0, "log_loss": 0, "stage": "R16"},
        {"p_home_advances": 0.90, "home_team": "D", "actual_winner": "D", "correct": True,
         "brier": 0, "log_loss": 0, "stage": "R16"},
    ])
    out = calibration_bins(df, n_bins=5)
    # First bin [0.0, 0.2): 2 rows; last bin [0.8, 1.0): 1 row
    assert out.iloc[0]["n"] == 2
    assert out.iloc[-1]["n"] == 1
