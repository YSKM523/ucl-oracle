"""Monte Carlo simulation of UCL knockout bracket (QF → SF → Final).

Handles two-legged ties with aggregate scoring, extra time, and penalties.
No away goals rule (abolished in UCL from 2021-22 onwards).
"""

from __future__ import annotations

import logging
from collections import defaultdict

import numpy as np
import pandas as pd

from config import (
    BRACKET,
    FINAL_HOME_ADVANTAGE_ELO,
    FIRST_LEG_RESULTS,
    KNOCKOUT_PENALTY_ADVANTAGE,
    MONTE_CARLO_SIMULATIONS,
    UCL_HOME_ADVANTAGE_ELO,
    UCL_TEAMS,
)
from prediction.match_predictor import (
    knockout_probabilities,
    simulate_extra_time,
    simulate_leg,
    simulate_penalties,
)

log = logging.getLogger(__name__)

STAGES = ["qf_advance", "sf_advance", "final", "champion"]


def resolve_aggregate(
    agg_a: int,
    agg_b: int,
    elo_a: float,
    elo_b: float,
    second_leg_home_adv: float,
    rng: np.random.Generator,
) -> str:
    """Resolve a tied aggregate via extra time then penalties.

    Parameters
    ----------
    agg_a, agg_b : Aggregate goals after two legs
    elo_a, elo_b : Team Elo ratings
    second_leg_home_adv : Home advantage for team in second leg (team B)
    rng : Random generator

    Returns
    -------
    'a' or 'b' — the advancing team
    """
    if agg_a > agg_b:
        return "a"
    if agg_b > agg_a:
        return "b"

    # Tied on aggregate → extra time (played at second-leg venue)
    # Team B is at home for the second leg
    et_a, et_b = simulate_extra_time(elo_a, elo_b, -second_leg_home_adv, rng)
    agg_a += et_a
    agg_b += et_b

    if agg_a > agg_b:
        return "a"
    if agg_b > agg_a:
        return "b"

    # Still tied → penalties
    return simulate_penalties(elo_a, elo_b, rng)


def simulate_second_leg(
    first_leg: dict,
    elo_ratings: dict[str, float],
    rng: np.random.Generator,
) -> str:
    """Simulate the second leg of a QF tie given known first-leg result.

    The second leg is at the away team's ground (they become "home").

    Parameters
    ----------
    first_leg : {"home": str, "away": str, "home_goals": int, "away_goals": int}
    elo_ratings : {team: elo}
    rng : Random generator

    Returns
    -------
    Name of the advancing team.
    """
    team_a = first_leg["home"]   # Was home in first leg
    team_b = first_leg["away"]   # Was away in first leg, NOW home in second leg

    elo_a = elo_ratings[team_a]
    elo_b = elo_ratings[team_b]

    # Second leg: team_b is at home
    home_adv = UCL_HOME_ADVANTAGE_ELO
    # simulate_leg takes (elo_a, elo_b, home_advantage_for_a)
    # Since B is home, A gets negative home advantage
    goals_a_2nd, goals_b_2nd = simulate_leg(elo_a, elo_b, -home_adv, rng)

    # Aggregate
    agg_a = first_leg["home_goals"] + goals_a_2nd
    agg_b = first_leg["away_goals"] + goals_b_2nd

    winner = resolve_aggregate(agg_a, agg_b, elo_a, elo_b, home_adv, rng)
    return team_a if winner == "a" else team_b


def simulate_two_leg_tie(
    team_a: str,
    team_b: str,
    elo_ratings: dict[str, float],
    rng: np.random.Generator,
) -> str:
    """Simulate a full two-legged tie (both legs unknown).

    First leg at team_a's ground, second leg at team_b's ground.

    Returns
    -------
    Name of the advancing team.
    """
    elo_a = elo_ratings[team_a]
    elo_b = elo_ratings[team_b]
    home_adv = UCL_HOME_ADVANTAGE_ELO

    # First leg: A is home
    goals_a_1st, goals_b_1st = simulate_leg(elo_a, elo_b, home_adv, rng)

    # Second leg: B is home
    goals_a_2nd, goals_b_2nd = simulate_leg(elo_a, elo_b, -home_adv, rng)

    # Aggregate
    agg_a = goals_a_1st + goals_a_2nd
    agg_b = goals_b_1st + goals_b_2nd

    winner = resolve_aggregate(agg_a, agg_b, elo_a, elo_b, home_adv, rng)
    return team_a if winner == "a" else team_b


def simulate_final(
    team_a: str,
    team_b: str,
    elo_ratings: dict[str, float],
    rng: np.random.Generator,
) -> str:
    """Simulate the single-leg final at a neutral venue."""
    elo_a = elo_ratings[team_a]
    elo_b = elo_ratings[team_b]

    probs = knockout_probabilities(elo_a, elo_b, home_advantage=FINAL_HOME_ADVANTAGE_ELO)
    return team_a if rng.random() < probs["win_a"] else team_b


def simulate_bracket(
    elo_ratings: dict[str, float],
    first_leg_results: dict[str, dict],
    rng: np.random.Generator,
) -> dict[str, str]:
    """Simulate the entire UCL knockout bracket from QF second legs.

    Returns
    -------
    {team: highest_stage_reached} for all 8 teams.
    Stages: "qf_eliminated", "qf_advance" (=reached SF), "sf_eliminated",
            "sf_advance" (=reached final), "runner_up", "champion"
    """
    result = {team: "qf_eliminated" for team in UCL_TEAMS}

    # ── Quarter-finals (second legs only — first legs already played) ───
    qf_winners = {}
    for qf_id, first_leg in first_leg_results.items():
        winner = simulate_second_leg(first_leg, elo_ratings, rng)
        qf_winners[qf_id] = winner
        result[winner] = "qf_advance"

    # ── Semi-finals (two-legged ties, both legs simulated) ──────────────
    sf_winners = {}
    for sf_id, (qf_a_id, qf_b_id) in BRACKET.items():
        if sf_id == "Final":
            continue
        team_a = qf_winners[qf_a_id]
        team_b = qf_winners[qf_b_id]

        # Randomly assign home/away for SF (UEFA draws this; we simulate 50/50)
        if rng.random() < 0.5:
            winner = simulate_two_leg_tie(team_a, team_b, elo_ratings, rng)
        else:
            winner = simulate_two_leg_tie(team_b, team_a, elo_ratings, rng)

        sf_winners[sf_id] = winner
        loser = team_b if winner == team_a else team_a
        result[winner] = "sf_advance"
        result[loser] = "sf_eliminated"

    # ── Final (single match, neutral venue) ─────────────────────────────
    sf1_id, sf2_id = BRACKET["Final"]
    finalist_a = sf_winners[sf1_id]
    finalist_b = sf_winners[sf2_id]

    champion = simulate_final(finalist_a, finalist_b, elo_ratings, rng)
    runner_up = finalist_b if champion == finalist_a else finalist_a
    result[champion] = "champion"
    result[runner_up] = "runner_up"

    return result


def run_monte_carlo(
    elo_ratings: dict[str, float],
    first_leg_results: dict[str, dict] | None = None,
    n_simulations: int = MONTE_CARLO_SIMULATIONS,
    seed: int = 42,
) -> pd.DataFrame:
    """Run Monte Carlo simulation of the UCL knockout bracket.

    Returns
    -------
    DataFrame with columns: team, P(qf_advance), P(sf_advance), P(final), P(champion)
    Sorted by P(champion) descending.
    """
    if first_leg_results is None:
        first_leg_results = FIRST_LEG_RESULTS

    rng = np.random.default_rng(seed)

    stage_rank = {s: i for i, s in enumerate([
        "qf_eliminated", "qf_advance", "sf_eliminated",
        "sf_advance", "runner_up", "champion",
    ])}

    counters: dict[str, dict[str, int]] = defaultdict(
        lambda: {s: 0 for s in STAGES}
    )

    log.info("Running %d Monte Carlo simulations …", n_simulations)
    for sim in range(n_simulations):
        result = simulate_bracket(elo_ratings, first_leg_results, rng)

        for team, stage in result.items():
            team_rank = stage_rank.get(stage, 0)
            for s in STAGES:
                if s == "qf_advance" and team_rank >= stage_rank["qf_advance"]:
                    counters[team][s] += 1
                elif s == "sf_advance" and team_rank >= stage_rank["sf_advance"]:
                    counters[team][s] += 1
                elif s == "final" and team_rank >= stage_rank["runner_up"]:
                    counters[team][s] += 1
                elif s == "champion" and team_rank >= stage_rank["champion"]:
                    counters[team][s] += 1

        if (sim + 1) % 10000 == 0:
            log.info("  %d / %d simulations complete", sim + 1, n_simulations)

    # Convert to probabilities
    rows = []
    for team in sorted(counters.keys()):
        row = {"team": team}
        for stage in STAGES:
            row[f"P({stage})"] = counters[team][stage] / n_simulations
        rows.append(row)

    df = pd.DataFrame(rows).sort_values("P(champion)", ascending=False)
    return df.reset_index(drop=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

    from data.fetcher_clubelo import fetch_current_elos

    elos = fetch_current_elos()
    results = run_monte_carlo(elos, n_simulations=50_000)

    print("\n2025-26 UCL Predictions (50K simulations, Elo-only baseline):")
    print(f"{'Team':20s} {'QF Adv%':>8} {'SF Adv%':>8} {'Final%':>8} {'Win%':>8}")
    print("-" * 56)
    for _, row in results.iterrows():
        print(
            f"{row['team']:20s} "
            f"{row['P(qf_advance)']:7.1%} "
            f"{row['P(sf_advance)']:7.1%} "
            f"{row['P(final)']:7.1%} "
            f"{row['P(champion)']:7.1%}"
        )

    total = results["P(champion)"].sum()
    print(f"\nP(champion) sum: {total:.4f} (should be ~1.0)")
