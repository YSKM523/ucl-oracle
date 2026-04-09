"""Match prediction: Poisson scoreline model + Bradley-Terry for single-leg matches."""

from __future__ import annotations

import math

import numpy as np

from config import (
    BRADLEY_TERRY_DRAW_NU,
    KNOCKOUT_PENALTY_ADVANTAGE,
    POISSON_AVG_GOALS,
    UCL_HOME_ADVANTAGE_ELO,
    ET_GOAL_FRACTION,
)


# ── Poisson scoreline model (for two-legged ties) ──────────────────────────

def poisson_expected_goals(
    elo_a: float,
    elo_b: float,
    home_advantage: float = 0.0,
    avg_goals: float = POISSON_AVG_GOALS,
) -> tuple[float, float]:
    """Derive team-specific Poisson lambdas from Elo ratings.

    Parameters
    ----------
    elo_a : Elo of team A
    elo_b : Elo of team B
    home_advantage : Elo bonus for team A (positive = A is home)
    avg_goals : Expected total goals per match

    Returns
    -------
    (lambda_a, lambda_b) — expected goals for each team
    """
    elo_diff = (elo_a + home_advantage - elo_b) / 400.0
    share_a = 10.0 ** (elo_diff / 2.0) / (10.0 ** (elo_diff / 2.0) + 10.0 ** (-elo_diff / 2.0))
    lambda_a = avg_goals * share_a
    lambda_b = avg_goals * (1.0 - share_a)
    return lambda_a, lambda_b


def simulate_leg(
    elo_a: float,
    elo_b: float,
    home_advantage: float,
    rng: np.random.Generator,
    avg_goals: float = POISSON_AVG_GOALS,
) -> tuple[int, int]:
    """Simulate a single match leg, returning (goals_a, goals_b)."""
    lambda_a, lambda_b = poisson_expected_goals(elo_a, elo_b, home_advantage, avg_goals)
    goals_a = rng.poisson(lambda_a)
    goals_b = rng.poisson(lambda_b)
    return int(goals_a), int(goals_b)


def simulate_extra_time(
    elo_a: float,
    elo_b: float,
    home_advantage: float,
    rng: np.random.Generator,
    avg_goals: float = POISSON_AVG_GOALS,
) -> tuple[int, int]:
    """Simulate 30-minute extra time period."""
    et_avg = avg_goals * ET_GOAL_FRACTION
    lambda_a, lambda_b = poisson_expected_goals(elo_a, elo_b, home_advantage, et_avg)
    goals_a = rng.poisson(lambda_a)
    goals_b = rng.poisson(lambda_b)
    return int(goals_a), int(goals_b)


def simulate_penalties(
    elo_a: float,
    elo_b: float,
    rng: np.random.Generator,
    penalty_adv: float = KNOCKOUT_PENALTY_ADVANTAGE,
) -> str:
    """Simulate penalty shootout. Returns 'a' or 'b'."""
    if elo_a >= elo_b:
        return "a" if rng.random() < penalty_adv else "b"
    else:
        return "b" if rng.random() < penalty_adv else "a"


# ── Bradley-Terry (for single-leg Final) ────────────────────────────────────

def match_probabilities(
    elo_a: float,
    elo_b: float,
    home_advantage: float = 0.0,
    nu: float = BRADLEY_TERRY_DRAW_NU,
) -> dict[str, float]:
    """Bradley-Terry model with draws (Davidson 1970)."""
    exp_a = 10.0 ** ((elo_a + home_advantage) / 400.0)
    exp_b = 10.0 ** (elo_b / 400.0)
    denom = exp_a + exp_b + nu * math.sqrt(exp_a * exp_b)

    return {
        "win_a": exp_a / denom,
        "draw": nu * math.sqrt(exp_a * exp_b) / denom,
        "win_b": exp_b / denom,
    }


def knockout_probabilities(
    elo_a: float,
    elo_b: float,
    home_advantage: float = 0.0,
    nu: float = BRADLEY_TERRY_DRAW_NU,
    penalty_adv: float = KNOCKOUT_PENALTY_ADVANTAGE,
) -> dict[str, float]:
    """Match probabilities for single-leg knockout (no draws — ET/penalties)."""
    base = match_probabilities(elo_a, elo_b, home_advantage, nu)

    if elo_a + home_advantage >= elo_b:
        extra_a = base["draw"] * penalty_adv
        extra_b = base["draw"] * (1.0 - penalty_adv)
    else:
        extra_a = base["draw"] * (1.0 - penalty_adv)
        extra_b = base["draw"] * penalty_adv

    return {
        "win_a": base["win_a"] + extra_a,
        "win_b": base["win_b"] + extra_b,
    }
