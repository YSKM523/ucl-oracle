"""Half-Kelly PnL simulation over the signal log.

For every ``(signal, closing, resolution)`` triple in ``results/signal_log.jsonl``
we place a synthetic bet **at the signal-time market price** (not closing —
closing is used only as a CLV diagnostic), stake by Half-Kelly, and walk the
bankroll forward through time-ordered events. Output: ROI, max drawdown,
per-bet Sharpe, win rate, total volume staked.

We deliberately do NOT try to reconstruct a historical Polymarket trajectory
for the 83-tie backtest — probes of the Gamma API showed closed UCL markets
aren't preserved and no free bookmaker API covers tie-level 'advance'
markets historically. This module is therefore a **forward-test PnL**:
every match resolution adds one data point going forward. A synthetic
Elo-implied stress test is available separately for scale; it's explicitly
labelled as illustrative, not real market data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from markets.signal_log import filter_entries, read_all


@dataclass
class Bet:
    ts_signal: str
    market_type: str
    team: str
    season: str
    direction: str               # 'BUY' or 'SELL'
    entry_prob: float            # market implied prob at signal time
    ai_prob: float
    kelly_fraction: float        # full-Kelly stake fraction (may be negative)
    stake: float                 # actual stake in bankroll units
    decimal_odds: float
    outcome: int                 # 1 = event happened, 0 = event didn't
    bet_wins: bool               # whether THIS bet pays out (direction-aware)
    pnl: float                   # stake-weighted PnL for this bet
    bankroll_after: float


def _full_kelly(p: float, market_prob: float) -> tuple[float, float]:
    """Return (kelly_fraction, decimal_odds) for a BUY on the event."""
    # Decimal odds offered = 1 / market_prob (fair book, no vig)
    d = 1.0 / max(market_prob, 1e-9)
    b = d - 1.0
    if b <= 0:
        return 0.0, d
    f = (p * d - 1.0) / b
    return f, d


def simulate_pnl(
    entries: list[dict] | None = None,
    starting_bankroll: float = 100.0,
    kelly_multiplier: float = 0.5,
    min_edge_pct: float = 3.0,
    require_resolution: bool = True,
) -> tuple[list[Bet], pd.DataFrame]:
    """Walk the signal log in time order, placing Half-Kelly bets.

    Returns (list_of_bet_records, bankroll_trajectory_df).
    """
    if entries is None:
        entries = read_all()

    # Pair each signal with the latest closing (for decimal-odds context only)
    # and latest resolution for that (market_type, team, season) key.
    def latest_by(source: str) -> dict[tuple, dict]:
        out: dict[tuple, dict] = {}
        for e in filter_entries(entries, source=source):
            k = (e["market_type"], e["team"], e["season"])
            if k not in out or e["timestamp_utc"] > out[k]["timestamp_utc"]:
                out[k] = e
        return out

    resolutions = latest_by("resolution")

    # All signals that cross the min-edge threshold, chronological
    signals = [
        e for e in filter_entries(entries, source="signal")
        if e.get("signal") in {"BUY", "SELL", "STRONG BUY", "STRONG SELL"}
        and (e.get("edge_pct") is None or abs(e["edge_pct"]) >= min_edge_pct)
    ]
    signals.sort(key=lambda e: e["timestamp_utc"])

    bankroll = starting_bankroll
    bets: list[Bet] = []
    traj_rows: list[dict] = [{
        "ts": signals[0]["timestamp_utc"] if signals else None,
        "event": "start",
        "bankroll": bankroll,
    }] if signals else []

    for sig in signals:
        key = (sig["market_type"], sig["team"], sig["season"])
        if require_resolution and key not in resolutions:
            continue
        res = resolutions.get(key)
        outcome = int(res["market_prob"] >= 0.5) if res is not None else 0

        ai_p = sig["ai_prob"]
        mkt_p = sig["market_prob"]
        direction = "BUY" if "BUY" in sig["signal"].upper() else "SELL"

        if direction == "BUY":
            p, m = ai_p, mkt_p
            bet_wins = outcome == 1
        else:
            # Betting on "NO": our prob of NO = 1-ai_p, market NO = 1-mkt_p
            p, m = 1 - ai_p, 1 - mkt_p
            bet_wins = outcome == 0

        f_full, d_odds = _full_kelly(p, m)
        stake_frac = max(0.0, f_full) * kelly_multiplier
        stake = bankroll * stake_frac

        if stake <= 0:
            continue

        if bet_wins:
            pnl = stake * (d_odds - 1.0)
        else:
            pnl = -stake

        bankroll += pnl
        bets.append(
            Bet(
                ts_signal=sig["timestamp_utc"],
                market_type=sig["market_type"],
                team=sig["team"],
                season=sig["season"],
                direction=direction,
                entry_prob=mkt_p,
                ai_prob=ai_p,
                kelly_fraction=round(f_full, 4),
                stake=round(stake, 4),
                decimal_odds=round(d_odds, 4),
                outcome=outcome,
                bet_wins=bet_wins,
                pnl=round(pnl, 4),
                bankroll_after=round(bankroll, 4),
            )
        )
        traj_rows.append({
            "ts": sig["timestamp_utc"],
            "event": f"{direction} {sig['team']} ({sig['market_type']})",
            "bankroll": round(bankroll, 4),
        })

    return bets, pd.DataFrame(traj_rows)


# ── metrics ─────────────────────────────────────────────────────────────

def max_drawdown_pct(bankrolls: list[float]) -> float:
    """Peak-to-trough drawdown as a % of peak, across the trajectory."""
    peak = bankrolls[0] if bankrolls else 0.0
    worst = 0.0
    for b in bankrolls:
        peak = max(peak, b)
        if peak > 0:
            dd = (peak - b) / peak
            worst = max(worst, dd)
    return worst * 100.0


def per_bet_sharpe(bets: list[Bet]) -> float:
    """Return / risk, where return = PnL / stake per bet, risk = std of those returns.

    Uses the classic Sharpe form with a zero benchmark (bookmaker closing line
    is the relevant benchmark for sports betting — we already track CLV
    separately). Not annualized; this is per-bet.
    """
    if not bets:
        return 0.0
    rets = [b.pnl / b.stake for b in bets if b.stake > 0]
    if not rets:
        return 0.0
    mean = sum(rets) / len(rets)
    if len(rets) == 1:
        return float("nan")
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    sd = math.sqrt(var)
    return mean / sd if sd > 0 else float("nan")


def pnl_summary(
    bets: list[Bet],
    starting_bankroll: float = 100.0,
) -> dict:
    if not bets:
        return {
            "n_bets": 0, "total_staked": 0.0, "final_bankroll": starting_bankroll,
            "total_pnl": 0.0, "roi_pct": 0.0, "return_on_turnover_pct": 0.0,
            "max_drawdown_pct": 0.0, "per_bet_sharpe": 0.0, "win_rate_pct": 0.0,
        }
    total_staked = sum(b.stake for b in bets)
    final_br = bets[-1].bankroll_after
    wins = sum(1 for b in bets if b.bet_wins)
    bankrolls = [starting_bankroll] + [b.bankroll_after for b in bets]
    return {
        "n_bets": len(bets),
        "total_staked": round(total_staked, 4),
        "final_bankroll": round(final_br, 4),
        "total_pnl": round(final_br - starting_bankroll, 4),
        "roi_pct": round((final_br / starting_bankroll - 1) * 100, 2),
        "return_on_turnover_pct": (
            round((final_br - starting_bankroll) / total_staked * 100, 2)
            if total_staked > 0 else 0.0
        ),
        "max_drawdown_pct": round(max_drawdown_pct(bankrolls), 2),
        "per_bet_sharpe": round(per_bet_sharpe(bets), 3),
        "win_rate_pct": round(wins / len(bets) * 100, 2),
    }


def bets_to_dataframe(bets: list[Bet]) -> pd.DataFrame:
    if not bets:
        return pd.DataFrame()
    return pd.DataFrame([b.__dict__ for b in bets])
