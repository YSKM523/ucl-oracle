"""Closing Line Value (CLV) analysis.

For every BUY/SELL signal in the log, pair it with the most recent 'closing'
snapshot for the same (market_type, team, season). CLV is measured in
percentage points of implied probability:

    CLV_pp(BUY)  = closing_prob - entry_prob     # market moved our way → +
    CLV_pp(SELL) = entry_prob - closing_prob     # market moved our way → +

Under market efficiency CLV is mean-zero noise. A consistent positive CLV is
the industry-standard evidence of genuine edge, independent of hit rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from markets.signal_log import filter_entries, read_all


@dataclass
class PairedSignal:
    market_type: str
    team: str
    season: str
    signal: str
    entry_ts: str
    closing_ts: str
    entry_market_prob: float
    closing_market_prob: float
    ai_prob: float
    edge_pct: float
    clv_pp: float            # signed so that positive = alpha
    direction: str           # 'BUY' or 'SELL'


def _direction(signal: str | None) -> str | None:
    if signal is None:
        return None
    s = signal.upper()
    if "BUY" in s:
        return "BUY"
    if "SELL" in s:
        return "SELL"
    return None


def pair_signals_with_closings(entries: list[dict]) -> list[PairedSignal]:
    """For every signal row, find the LATEST closing for the same key."""
    # Group closings by key
    closings: dict[tuple, dict] = {}
    for e in filter_entries(entries, source="closing"):
        key = (e["market_type"], e["team"], e["season"])
        if key not in closings or e["timestamp_utc"] > closings[key]["timestamp_utc"]:
            closings[key] = e

    paired: list[PairedSignal] = []
    for sig in filter_entries(entries, source="signal"):
        direction = _direction(sig.get("signal"))
        if direction is None:
            continue
        key = (sig["market_type"], sig["team"], sig["season"])
        clos = closings.get(key)
        if clos is None:
            continue
        entry_p = sig["market_prob"]
        close_p = clos["market_prob"]
        if direction == "BUY":
            clv = (close_p - entry_p) * 100
        else:
            clv = (entry_p - close_p) * 100
        paired.append(
            PairedSignal(
                market_type=sig["market_type"],
                team=sig["team"],
                season=sig["season"],
                signal=sig["signal"],
                entry_ts=sig["timestamp_utc"],
                closing_ts=clos["timestamp_utc"],
                entry_market_prob=entry_p,
                closing_market_prob=close_p,
                ai_prob=sig["ai_prob"],
                edge_pct=sig["edge_pct"],
                clv_pp=clv,
                direction=direction,
            )
        )
    return paired


def clv_summary_stats(paired: list[PairedSignal]) -> dict:
    """Aggregate stats over all paired signals."""
    if not paired:
        return {"n": 0}
    xs = [p.clv_pp for p in paired]
    n = len(xs)
    mean = sum(xs) / n
    if n > 1:
        var = sum((x - mean) ** 2 for x in xs) / (n - 1)
        sd = math.sqrt(var)
        se = sd / math.sqrt(n)
        # One-sided t-test H0: mean <= 0  vs  H1: mean > 0
        t = mean / se if se > 0 else float("nan")
        # Normal-approx two-tailed p for one-sided upper:
        p_value = 0.5 * math.erfc(t / math.sqrt(2)) if t == t else float("nan")
    else:
        sd = 0.0
        se = 0.0
        t = float("nan")
        p_value = float("nan")
    return {
        "n": n,
        "mean_clv_pp": round(mean, 3),
        "sd_clv_pp": round(sd, 3),
        "se_clv_pp": round(se, 3),
        "t_stat": round(t, 3) if t == t else None,
        "p_value_one_sided": round(p_value, 4) if p_value == p_value else None,
        "pct_positive": round(sum(1 for x in xs if x > 0) / n * 100, 1),
    }


def per_signal_breakdown(paired: list[PairedSignal]) -> pd.DataFrame:
    rows = [p.__dict__ for p in paired]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df[
        [
            "market_type", "team", "direction", "signal", "edge_pct",
            "entry_market_prob", "closing_market_prob", "clv_pp",
            "entry_ts", "closing_ts", "season",
        ]
    ].sort_values("clv_pp", ascending=False)
    return df.round({
        "edge_pct": 1,
        "entry_market_prob": 4,
        "closing_market_prob": 4,
        "clv_pp": 2,
    })


def per_direction_stats(paired: list[PairedSignal]) -> pd.DataFrame:
    rows = []
    for d in ("BUY", "SELL"):
        sub = [p for p in paired if p.direction == d]
        if not sub:
            continue
        stats = clv_summary_stats(sub)
        stats["direction"] = d
        rows.append(stats)
    return pd.DataFrame(rows)


def per_strength_stats(paired: list[PairedSignal]) -> pd.DataFrame:
    rows = []
    for strength in ("STRONG BUY", "BUY", "SELL", "STRONG SELL"):
        sub = [p for p in paired if p.signal == strength]
        if not sub:
            continue
        stats = clv_summary_stats(sub)
        stats["signal"] = strength
        rows.append(stats)
    return pd.DataFrame(rows)


def load_and_analyze() -> dict:
    """End-to-end: read the log, pair, compute everything."""
    entries = read_all()
    paired = pair_signals_with_closings(entries)
    return {
        "paired": paired,
        "summary": clv_summary_stats(paired),
        "per_direction": per_direction_stats(paired),
        "per_strength": per_strength_stats(paired),
        "per_signal_df": per_signal_breakdown(paired),
    }
