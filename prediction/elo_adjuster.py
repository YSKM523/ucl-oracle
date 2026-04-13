"""First-leg performance → Elo adjustment.

Updates each team's Elo after the QF first legs based on residual between
observed performance (blended xG + actual goals) and Elo-implied expectation.
The adjusted Elo is used for SF/Final Monte Carlo simulation, while QF sims
still resolve aggregate ties from the actual first-leg scores.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config import (
    FIRST_LEG_ELO_K,
    FIRST_LEG_RESIDUAL_CAP,
    FIRST_LEG_RESULTS,
    FIRST_LEG_XG,
    INJURY_DEFAULT_WEIGHT,
    INJURY_RETURN_WEIGHTS,
    INJURY_TIERS,
    INJURY_TOTAL_CAP,
    UCL_HOME_ADVANTAGE_ELO,
    XG_BLEND_ALPHA,
)
from prediction.match_predictor import poisson_expected_goals

log = logging.getLogger(__name__)


@dataclass
class LegAdjustment:
    qf_id: str
    home: str
    away: str
    expected_gd: float
    observed_gd: float
    effective_gd: float
    residual: float
    delta_elo: float


def compute_first_leg_adjustments(
    elos: dict[str, float],
    xg_data: dict[str, dict[str, float]] | None = None,
    alpha: float = XG_BLEND_ALPHA,
    k: float = FIRST_LEG_ELO_K,
    cap: float = FIRST_LEG_RESIDUAL_CAP,
) -> list[LegAdjustment]:
    """Compute per-leg ΔElo from first-leg performance vs Elo expectation."""
    if xg_data is None:
        xg_data = FIRST_LEG_XG
    adjustments: list[LegAdjustment] = []

    for qf_id, leg in FIRST_LEG_RESULTS.items():
        home, away = leg["home"], leg["away"]
        gh, ga = leg["home_goals"], leg["away_goals"]
        observed_gd = gh - ga

        xg_leg = xg_data.get(qf_id)
        if xg_leg is not None:
            xgd = xg_leg["home_xg"] - xg_leg["away_xg"]
            effective_gd = alpha * xgd + (1 - alpha) * observed_gd
        else:
            effective_gd = observed_gd  # no xG → fall back to actual

        lam_h, lam_a = poisson_expected_goals(
            elos[home], elos[away], home_advantage=UCL_HOME_ADVANTAGE_ELO
        )
        expected_gd = lam_h - lam_a

        residual = effective_gd - expected_gd
        residual_clipped = max(-cap, min(cap, residual))
        delta = k * residual_clipped

        adjustments.append(
            LegAdjustment(
                qf_id=qf_id,
                home=home,
                away=away,
                expected_gd=expected_gd,
                observed_gd=observed_gd,
                effective_gd=effective_gd,
                residual=residual,
                delta_elo=delta,
            )
        )

    return adjustments


def apply_adjustments(
    elos: dict[str, float],
    adjustments: list[LegAdjustment],
) -> dict[str, float]:
    """Return a new Elo dict with first-leg adjustments applied."""
    adjusted = dict(elos)
    for adj in adjustments:
        adjusted[adj.home] = adjusted[adj.home] + adj.delta_elo
        adjusted[adj.away] = adjusted[adj.away] - adj.delta_elo
    return adjusted


def adjust_elos_for_first_legs(
    elos: dict[str, float],
    xg_data: dict[str, dict[str, float]] | None = None,
) -> tuple[dict[str, float], list[LegAdjustment]]:
    """Convenience wrapper: compute + apply first-leg Elo adjustments."""
    adjustments = compute_first_leg_adjustments(elos, xg_data=xg_data)
    return apply_adjustments(elos, adjustments), adjustments


@dataclass
class InjuryPenalty:
    team: str
    player: str
    transfer_value_m: float
    tier_base: float
    availability_weight: float  # fraction of remaining matches missed
    expected_return: str
    elo_penalty: float          # negative contribution


def _tier_base(transfer_value_m: float) -> float:
    for threshold, penalty in INJURY_TIERS:
        if transfer_value_m >= threshold:
            return penalty
    return INJURY_TIERS[-1][1]


def _return_weight(expected_return: str) -> float:
    key = (expected_return or "").strip().lower()
    return INJURY_RETURN_WEIGHTS.get(key, INJURY_DEFAULT_WEIGHT)


def compute_injury_penalties(
    injuries_by_team: dict[str, list],
    total_cap: float = INJURY_TOTAL_CAP,
) -> tuple[dict[str, float], list[InjuryPenalty]]:
    """Return (elo_delta_by_team, per_player_breakdown).

    `injuries_by_team` values are Injury-like objects with attrs:
      .player, .transfer_value_m, .expected_return
    """
    team_deltas: dict[str, float] = {}
    breakdown: list[InjuryPenalty] = []

    for team, injuries in injuries_by_team.items():
        team_total = 0.0
        for inj in injuries:
            tier = _tier_base(inj.transfer_value_m)
            w = _return_weight(inj.expected_return)
            penalty = tier * w  # positive magnitude
            team_total += penalty
            breakdown.append(
                InjuryPenalty(
                    team=team,
                    player=inj.player,
                    transfer_value_m=inj.transfer_value_m,
                    tier_base=tier,
                    availability_weight=w,
                    expected_return=inj.expected_return,
                    elo_penalty=-penalty,
                )
            )
        team_deltas[team] = -min(team_total, total_cap)

    return team_deltas, breakdown


def apply_injury_penalties(
    elos: dict[str, float],
    team_deltas: dict[str, float],
) -> dict[str, float]:
    adjusted = dict(elos)
    for team, delta in team_deltas.items():
        if team in adjusted:
            adjusted[team] = adjusted[team] + delta
    return adjusted


def format_injury_report(
    team_deltas: dict[str, float],
    breakdown: list[InjuryPenalty],
) -> str:
    lines = [
        f"{'Team':<20s} {'ΔElo':>8s} {'Players':>8s}",
        "-" * 40,
    ]
    counts: dict[str, int] = {}
    for b in breakdown:
        counts[b.team] = counts.get(b.team, 0) + 1
    for team in sorted(team_deltas, key=team_deltas.get):
        lines.append(
            f"{team:<20s} {team_deltas[team]:+8.1f} {counts.get(team, 0):>8d}"
        )
    # Top individual penalties
    top = sorted(breakdown, key=lambda b: b.elo_penalty)[:10]
    if top:
        lines.append("")
        lines.append(
            f"{'Top player-level hits':<36s} {'€M':>6s} {'Wgt':>5s} {'ΔElo':>7s}  {'Return':<20s}"
        )
        lines.append("-" * 82)
        for b in top:
            if b.elo_penalty >= 0:
                break
            label = f"{b.team} · {b.player}"
            lines.append(
                f"{label:<36s} {b.transfer_value_m:6.0f} {b.availability_weight:5.2f} "
                f"{b.elo_penalty:+7.2f}  {b.expected_return:<20s}"
            )
    return "\n".join(lines)


def format_adjustments_report(
    adjustments: list[LegAdjustment],
    before: dict[str, float],
    after: dict[str, float],
) -> str:
    """Human-readable summary of adjustments."""
    lines = [
        f"{'Leg':<5s} {'Match':<32s} {'ExpGD':>6s} {'EffGD':>6s} {'Resid':>6s} {'ΔElo':>7s}",
        "-" * 70,
    ]
    for a in adjustments:
        match = f"{a.home} vs {a.away}"
        lines.append(
            f"{a.qf_id:<5s} {match:<32s} "
            f"{a.expected_gd:+6.2f} {a.effective_gd:+6.2f} "
            f"{a.residual:+6.2f} {a.delta_elo:+7.2f}"
        )
    lines.append("")
    lines.append(f"{'Team':<20s} {'Before':>8s} {'After':>8s} {'Δ':>7s}")
    lines.append("-" * 46)
    for team in sorted(before, key=lambda t: after[t] - before[t], reverse=True):
        d = after[team] - before[team]
        lines.append(f"{team:<20s} {before[team]:8.1f} {after[team]:8.1f} {d:+7.2f}")
    return "\n".join(lines)
