"""Tests for injury-based Elo penalty."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from prediction.elo_adjuster import (
    apply_injury_penalties,
    compute_injury_penalties,
)


@dataclass
class FakeInjury:
    player: str
    transfer_value_m: float
    expected_return: str


def test_superstar_out_for_season_hits_full_tier():
    injuries = {"Arsenal": [FakeInjury("Saka", 98, "Out for season")]}
    deltas, breakdown = compute_injury_penalties(injuries)
    # Tier: ≥€80M → 30; weight: "Out for season" → 1.0
    assert deltas["Arsenal"] == pytest.approx(-30.0)
    assert breakdown[0].elo_penalty == pytest.approx(-30.0)


def test_doubtful_halves_penalty():
    injuries = {"Arsenal": [FakeInjury("Saka", 98, "Doubtful")]}
    deltas, _ = compute_injury_penalties(injuries)
    # 30 * 0.5
    assert deltas["Arsenal"] == pytest.approx(-15.0)


def test_squad_player_tier_is_small():
    injuries = {"Liverpool": [FakeInjury("Endo", 7, "Out for season")]}
    deltas, _ = compute_injury_penalties(injuries)
    # Tier: <€15M → 3; weight 1.0
    assert deltas["Liverpool"] == pytest.approx(-3.0)


def test_multiple_injuries_sum():
    injuries = {
        "Liverpool": [
            FakeInjury("Alisson", 17, "Early May 2026"),   # tier 7 * 0.33 = 2.31
            FakeInjury("Bradley", 39, "Out for season"),    # tier 7 * 1.0 = 7.0
            FakeInjury("Jones", 49, "Doubtful"),            # tier 15 * 0.5 = 7.5
        ]
    }
    deltas, _ = compute_injury_penalties(injuries)
    assert deltas["Liverpool"] == pytest.approx(-(2.31 + 7.0 + 7.5), abs=0.01)


def test_total_cap_caps_extreme_teams():
    injuries = {
        "Arsenal": [FakeInjury(f"Star{i}", 100, "Out for season") for i in range(5)]
    }
    # Uncapped would be 5*30 = 150; cap = 60
    deltas, _ = compute_injury_penalties(injuries)
    assert deltas["Arsenal"] == pytest.approx(-60.0)


def test_apply_penalties_subtracts_from_elo():
    elos = {"Arsenal": 2066.0, "Liverpool": 1922.0}
    deltas = {"Arsenal": -30.0, "Liverpool": -10.0}
    out = apply_injury_penalties(elos, deltas)
    assert out["Arsenal"] == pytest.approx(2036.0)
    assert out["Liverpool"] == pytest.approx(1912.0)


def test_unknown_return_uses_default_weight():
    injuries = {"X": [FakeInjury("p", 50, "Something weird")]}
    deltas, _ = compute_injury_penalties(injuries)
    # tier 15 * default 0.4
    assert deltas["X"] == pytest.approx(-6.0)
