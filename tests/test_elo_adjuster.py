"""Tests for first-leg xG-blended Elo adjustment."""

from __future__ import annotations

import pytest

from prediction.elo_adjuster import (
    adjust_elos_for_first_legs,
    compute_first_leg_adjustments,
)


BASE_ELOS = {
    "Arsenal": 2066.0,
    "Bayern Munich": 2014.0,
    "Barcelona": 1970.0,
    "PSG": 1960.0,
    "Real Madrid": 1938.0,
    "Liverpool": 1922.0,
    "Atletico Madrid": 1877.0,
    "Sporting CP": 1868.0,
}


def test_adjustments_are_zero_sum_per_leg():
    """Each leg's ΔElo should cancel between home and away — no mass created."""
    adjusted, adjustments = adjust_elos_for_first_legs(BASE_ELOS)
    # Sum of Elo across all teams should be invariant
    assert sum(adjusted.values()) == pytest.approx(sum(BASE_ELOS.values()), abs=1e-6)
    # Each leg individually zero-sum
    for adj in adjustments:
        home_delta = adjusted[adj.home] - BASE_ELOS[adj.home]
        # Home delta contributes from this leg only (no overlapping teams across legs)
        assert home_delta == pytest.approx(adj.delta_elo)


def test_overperformance_bumps_elo_up():
    """Atletico dominated Barcelona despite Elo disadvantage → positive Δ."""
    _, adjustments = adjust_elos_for_first_legs(BASE_ELOS)
    qf3 = next(a for a in adjustments if a.qf_id == "QF3")
    # Residual should be negative (from home's perspective) → away Atletico gains
    assert qf3.residual < 0
    assert qf3.delta_elo < 0  # Barcelona (home) loses Elo
    # Apply flips sign for away team
    adjusted, _ = adjust_elos_for_first_legs(BASE_ELOS)
    assert adjusted["Atletico Madrid"] > BASE_ELOS["Atletico Madrid"]
    assert adjusted["Barcelona"] < BASE_ELOS["Barcelona"]


def test_residual_is_capped():
    """Even a 10-goal blowout should not push ΔElo past K * CAP = 25."""
    extreme_xg = {"QF1": {"home_xg": 10.0, "away_xg": 0.0}}
    adjustments = compute_first_leg_adjustments(BASE_ELOS, xg_data=extreme_xg, k=10.0, cap=2.5)
    qf1 = next(a for a in adjustments if a.qf_id == "QF1")
    assert abs(qf1.delta_elo) <= 25.0 + 1e-6


def test_missing_xg_falls_back_to_goals():
    """If xG dict is empty, effective_gd should equal observed_gd."""
    adjustments = compute_first_leg_adjustments(BASE_ELOS, xg_data={})
    for adj in adjustments:
        assert adj.effective_gd == adj.observed_gd


def test_psg_gets_positive_bump():
    """With default placeholders, PSG 2-0 Liverpool (xG 1.70-0.90) should be a net positive."""
    adjusted, _ = adjust_elos_for_first_legs(BASE_ELOS)
    assert adjusted["PSG"] > BASE_ELOS["PSG"]
    assert adjusted["Liverpool"] < BASE_ELOS["Liverpool"]
