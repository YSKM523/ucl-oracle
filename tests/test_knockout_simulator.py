"""Tests for knockout bracket simulation."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytest

from config import FIRST_LEG_RESULTS, FALLBACK_ELO, UCL_TEAMS
from prediction.knockout_simulator import (
    resolve_aggregate,
    simulate_second_leg,
    simulate_two_leg_tie,
    simulate_final,
    simulate_bracket,
    run_monte_carlo,
)


class TestResolveAggregate:
    def test_team_a_wins_on_aggregate(self):
        rng = np.random.default_rng(42)
        result = resolve_aggregate(3, 1, 1800, 1800, 65, rng)
        assert result == "a"

    def test_team_b_wins_on_aggregate(self):
        rng = np.random.default_rng(42)
        result = resolve_aggregate(1, 3, 1800, 1800, 65, rng)
        assert result == "b"

    def test_tied_aggregate_goes_to_et(self):
        """Tied aggregate should not crash and should return a winner."""
        rng = np.random.default_rng(42)
        results = set()
        for seed in range(100):
            rng = np.random.default_rng(seed)
            result = resolve_aggregate(2, 2, 1800, 1800, 65, rng)
            assert result in ("a", "b")
            results.add(result)
        # Should have both outcomes across 100 trials
        assert len(results) == 2


class TestSimulateSecondLeg:
    def test_returns_valid_team(self):
        rng = np.random.default_rng(42)
        winner = simulate_second_leg(FIRST_LEG_RESULTS["QF1"], FALLBACK_ELO, rng)
        assert winner in ("PSG", "Liverpool")

    def test_psg_favored_over_liverpool(self):
        """PSG leads 2-0; should advance most of the time."""
        rng = np.random.default_rng(42)
        psg_wins = sum(
            1 for _ in range(5000)
            if simulate_second_leg(FIRST_LEG_RESULTS["QF1"], FALLBACK_ELO, rng) == "PSG"
        )
        assert psg_wins > 3500  # > 70%

    def test_arsenal_favored_over_sporting(self):
        """Arsenal leads 1-0 and has much higher Elo."""
        rng = np.random.default_rng(42)
        arsenal_wins = sum(
            1 for _ in range(5000)
            if simulate_second_leg(FIRST_LEG_RESULTS["QF4"], FALLBACK_ELO, rng) == "Arsenal"
        )
        assert arsenal_wins > 4500  # > 90%


class TestSimulateBracket:
    def test_returns_all_teams(self):
        rng = np.random.default_rng(42)
        result = simulate_bracket(FALLBACK_ELO, FIRST_LEG_RESULTS, rng)
        assert set(result.keys()) == set(UCL_TEAMS)

    def test_exactly_one_champion(self):
        rng = np.random.default_rng(42)
        result = simulate_bracket(FALLBACK_ELO, FIRST_LEG_RESULTS, rng)
        champions = [t for t, s in result.items() if s == "champion"]
        assert len(champions) == 1

    def test_exactly_one_runner_up(self):
        rng = np.random.default_rng(42)
        result = simulate_bracket(FALLBACK_ELO, FIRST_LEG_RESULTS, rng)
        runners_up = [t for t, s in result.items() if s == "runner_up"]
        assert len(runners_up) == 1

    def test_four_qf_advance(self):
        """Exactly 4 teams should advance from QF."""
        rng = np.random.default_rng(42)
        result = simulate_bracket(FALLBACK_ELO, FIRST_LEG_RESULTS, rng)
        advanced = [t for t, s in result.items() if s != "qf_eliminated"]
        assert len(advanced) == 4


class TestRunMonteCarlo:
    def test_champion_probabilities_sum_to_one(self):
        results = run_monte_carlo(FALLBACK_ELO, n_simulations=5_000, seed=42)
        total = results["P(champion)"].sum()
        assert abs(total - 1.0) < 0.01

    def test_all_teams_present(self):
        results = run_monte_carlo(FALLBACK_ELO, n_simulations=1_000, seed=42)
        assert set(results["team"]) == set(UCL_TEAMS)

    def test_qf_advance_monotonic(self):
        """Stage probabilities must be non-increasing: QF ≥ Final ≥ Champion."""
        results = run_monte_carlo(FALLBACK_ELO, n_simulations=5_000, seed=42)
        for _, row in results.iterrows():
            assert row["P(qf_advance)"] >= row["P(final)"]
            assert row["P(final)"] >= row["P(champion)"]

    def test_arsenal_is_favorite(self):
        """Arsenal should be the favorite (highest Elo + favorable bracket)."""
        results = run_monte_carlo(FALLBACK_ELO, n_simulations=10_000, seed=42)
        top_team = results.iloc[0]["team"]
        assert top_team == "Arsenal"
