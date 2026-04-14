"""Tests for the LOSO (leave-one-season-out) framework."""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.loso import LOSOResult, run_loso, summarize_loso


def _mk_season(name: str, n_correct: int, n_total: int) -> dict:
    """Build a seasons payload entry with synthetic ties."""
    ties = [{"id": f"{name}-{i}"} for i in range(n_total)]
    for i in range(n_total):
        ties[i]["should_be_correct"] = i < n_correct
    return {"season": name, "ties": ties}


def _perfect_predictor(test_ties: list[dict], hypers: dict) -> pd.DataFrame:
    """Stand-in predictor that just replays the 'should_be_correct' ground truth."""
    rows = [{
        "correct": t["should_be_correct"],
        "brier": 0.0 if t["should_be_correct"] else 0.25,
        "log_loss": 0.0 if t["should_be_correct"] else 0.7,
    } for t in test_ties]
    return pd.DataFrame(rows)


def _noop_tuner(train_ties: list[dict]) -> dict:
    return {}


def test_loso_runs_one_fold_per_season():
    payload = [
        _mk_season("2020", n_correct=5, n_total=10),
        _mk_season("2021", n_correct=8, n_total=10),
        _mk_season("2022", n_correct=6, n_total=10),
    ]
    results = run_loso(payload, _perfect_predictor, _noop_tuner)
    assert len(results) == 3
    assert [r.held_out_season for r in results] == ["2020", "2021", "2022"]


def test_loso_holds_out_correct_season():
    payload = [
        _mk_season("2020", n_correct=5, n_total=10),
        _mk_season("2021", n_correct=8, n_total=10),
    ]
    results = run_loso(payload, _perfect_predictor, _noop_tuner)
    r20 = next(r for r in results if r.held_out_season == "2020")
    r21 = next(r for r in results if r.held_out_season == "2021")
    assert r20.hit_rate_test == pytest.approx(0.5)
    assert r21.hit_rate_test == pytest.approx(0.8)
    assert r20.train_seasons == ("2021",)
    assert r21.train_seasons == ("2020",)


def test_tuner_receives_training_ties_only():
    seen_training_sizes = []

    def tuner(train_ties):
        seen_training_sizes.append(len(train_ties))
        return {"tuned_on_n_ties": len(train_ties)}

    payload = [
        _mk_season("2020", 1, 10),
        _mk_season("2021", 2, 20),
        _mk_season("2022", 3, 30),
    ]
    results = run_loso(payload, _perfect_predictor, tuner)
    # Held-out = 2020: train on 20+30 = 50
    # Held-out = 2021: train on 10+30 = 40
    # Held-out = 2022: train on 10+20 = 30
    assert sorted(seen_training_sizes) == [30, 40, 50]
    assert results[0].hypers == {"tuned_on_n_ties": 50}


def test_summary_pooled_row_uses_micro_average():
    r1 = LOSOResult(
        held_out_season="A", hypers={}, n_test=10, n_correct_test=5,
        hit_rate_test=0.5, brier_test=0.20, log_loss_test=0.6,
        train_seasons=("B",),
    )
    r2 = LOSOResult(
        held_out_season="B", hypers={}, n_test=20, n_correct_test=16,
        hit_rate_test=0.8, brier_test=0.15, log_loss_test=0.5,
        train_seasons=("A",),
    )
    df = summarize_loso([r1, r2])
    pooled = df[df["held_out"] == "POOLED (micro)"].iloc[0]
    # 5 + 16 = 21 correct out of 30 → 0.700
    assert pooled["hit_rate"] == pytest.approx(0.7)
    # Brier weighted: (0.20 * 10 + 0.15 * 20) / 30 = 0.167
    assert pooled["brier"] == pytest.approx(0.167, abs=0.01)
