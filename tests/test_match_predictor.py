"""Tests for match prediction models."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytest

from prediction.match_predictor import (
    poisson_expected_goals,
    simulate_leg,
    simulate_extra_time,
    simulate_penalties,
    match_probabilities,
    knockout_probabilities,
)


class TestPoissonExpectedGoals:
    def test_equal_teams(self):
        """Equal Elo teams should split goals evenly."""
        la, lb = poisson_expected_goals(1800, 1800)
        assert abs(la - lb) < 0.01
        assert abs(la + lb - 2.7) < 0.01  # Default avg goals

    def test_stronger_team_scores_more(self):
        """Higher Elo team should have higher expected goals."""
        la, lb = poisson_expected_goals(2000, 1800)
        assert la > lb

    def test_home_advantage(self):
        """Home advantage should boost team A's expected goals."""
        la_neutral, lb_neutral = poisson_expected_goals(1800, 1800, home_advantage=0)
        la_home, lb_home = poisson_expected_goals(1800, 1800, home_advantage=65)
        assert la_home > la_neutral
        assert lb_home < lb_neutral

    def test_total_goals_preserved(self):
        """Total expected goals should equal avg_goals regardless of Elo difference."""
        for elo_a, elo_b in [(2100, 1600), (1800, 1800), (1500, 2000)]:
            la, lb = poisson_expected_goals(elo_a, elo_b)
            assert abs(la + lb - 2.7) < 0.01

    def test_symmetry(self):
        """Swapping teams should swap lambdas."""
        la1, lb1 = poisson_expected_goals(2000, 1800)
        la2, lb2 = poisson_expected_goals(1800, 2000)
        assert abs(la1 - lb2) < 0.01
        assert abs(lb1 - la2) < 0.01


class TestSimulateLeg:
    def test_returns_integers(self):
        rng = np.random.default_rng(42)
        ga, gb = simulate_leg(1900, 1800, 0, rng)
        assert isinstance(ga, int)
        assert isinstance(gb, int)
        assert ga >= 0
        assert gb >= 0

    def test_average_goals(self):
        """Over many simulations, average goals should approach expected."""
        rng = np.random.default_rng(42)
        total = 0
        n = 10_000
        for _ in range(n):
            ga, gb = simulate_leg(1800, 1800, 0, rng)
            total += ga + gb
        avg = total / n
        assert abs(avg - 2.7) < 0.1  # Within 0.1 of expected


class TestMatchProbabilities:
    def test_sums_to_one(self):
        probs = match_probabilities(1800, 1800)
        total = sum(probs.values())
        assert abs(total - 1.0) < 1e-10

    def test_stronger_team_favored(self):
        probs = match_probabilities(2000, 1600)
        assert probs["win_a"] > probs["win_b"]

    def test_draw_positive(self):
        probs = match_probabilities(1800, 1800)
        assert probs["draw"] > 0


class TestKnockoutProbabilities:
    def test_sums_to_one(self):
        probs = knockout_probabilities(1800, 1800)
        total = sum(probs.values())
        assert abs(total - 1.0) < 1e-10

    def test_no_draw(self):
        probs = knockout_probabilities(1800, 1800)
        assert "draw" not in probs

    def test_stronger_team_favored(self):
        probs = knockout_probabilities(2000, 1600)
        assert probs["win_a"] > probs["win_b"]


class TestSimulatePenalties:
    def test_returns_valid(self):
        rng = np.random.default_rng(42)
        result = simulate_penalties(1800, 1800, rng)
        assert result in ("a", "b")

    def test_higher_rated_slight_advantage(self):
        rng = np.random.default_rng(42)
        wins_a = sum(1 for _ in range(10000)
                     if simulate_penalties(2000, 1600, rng) == "a")
        assert wins_a > 5000  # Should win more than half
