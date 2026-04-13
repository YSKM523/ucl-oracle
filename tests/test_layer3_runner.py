"""Tests for Layer 3 helpers."""

from __future__ import annotations

import pytest

from backtest.runner_layer3 import compute_leg_elo_delta


BASE_HOME = 2000.0
BASE_AWAY = 1800.0


def test_delta_zero_when_result_matches_expectation():
    """If effective_gd ≈ expected_gd, residual ≈ 0 → delta ≈ 0."""
    # Home is 200 Elo stronger + home advantage → expected ~1.3 goal diff
    # If result = 2-1 (diff 1.0) with xG close to it, residual is small
    delta = compute_leg_elo_delta(
        BASE_HOME, BASE_AWAY,
        home_goals=2, away_goals=1,
        home_xg=1.8, away_xg=0.8,  # xGd = 1.0
    )
    # residual = 1.0 - expected(~1.73) = -0.73; delta = 10 * -0.73 ≈ -7.3 (small)
    assert abs(delta) < 10


def test_delta_positive_when_home_overperforms():
    """Home wins bigger than Elo expected → positive delta."""
    delta = compute_leg_elo_delta(
        BASE_HOME, BASE_AWAY,
        home_goals=4, away_goals=0,
        home_xg=3.0, away_xg=0.2,
    )
    # effective_gd ≈ 0.6*2.8 + 0.4*4 = 3.28; expected ≈ 1.3; residual ≈ 2 (capped at 2.5)
    # delta = 10*2 = 20 (positive shift to home)
    assert delta > 10


def test_delta_capped():
    """Extreme blowouts cannot push delta past K * cap."""
    delta = compute_leg_elo_delta(
        BASE_HOME, BASE_AWAY,
        home_goals=10, away_goals=0,
        home_xg=8.0, away_xg=0.0,
    )
    # At K=10, cap=2.5 → |delta| ≤ 25
    assert abs(delta) <= 25.0 + 1e-6


def test_no_xg_falls_back_to_goals():
    """Without xG, formula uses actual goal differential."""
    delta = compute_leg_elo_delta(
        BASE_HOME, BASE_AWAY,
        home_goals=0, away_goals=2,  # upset away win
        home_xg=None, away_xg=None,
    )
    # observed_gd = -2; expected ≈ +1.3; residual ≈ -3.3 (capped at -2.5)
    # delta = 10 * -2.5 = -25 (big shift toward away)
    assert delta < -10


def test_xg_dampens_lucky_win():
    """1-0 home win with hostile xG (away outshooting) should produce smaller delta than score alone."""
    delta_score_only = compute_leg_elo_delta(
        BASE_HOME, BASE_AWAY, home_goals=1, away_goals=0,
        home_xg=None, away_xg=None,
    )
    delta_with_unfavorable_xg = compute_leg_elo_delta(
        BASE_HOME, BASE_AWAY, home_goals=1, away_goals=0,
        home_xg=0.4, away_xg=1.8,  # away dominated chances
    )
    # xG-weighted residual should be more negative (or less positive) than score-only
    assert delta_with_unfavorable_xg < delta_score_only
