"""Head-to-head: model vs bookmaker implied prob (the hard baseline).

The industry-standard skill test is not 'do you beat 50%'; it's whether the
model's Brier score is lower than the market's for the same set of resolved
events. Equivalently, the **Brier Skill Score** (BSS):

    BSS = 1 − Brier(model) / Brier(market)

BSS > 0 → model more skilled than the closing market
BSS = 0 → no skill over naïve-market baseline
BSS < 0 → model worse than just copying the market

This module reads ``results/signal_log.jsonl`` for triples of
(signal, closing, resolution) on the same (market_type, team, season)
and reports pairwise Brier, BSS, and a paired t-test on per-event
squared-error differences.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from markets.signal_log import filter_entries, read_all


@dataclass
class BenchmarkRow:
    market_type: str
    team: str
    season: str
    ai_prob: float
    market_close_prob: float
    outcome: int          # 0 or 1
    model_sq_err: float
    market_sq_err: float


def _latest_by(entries: list[dict], key: tuple) -> dict | None:
    cand = None
    for e in entries:
        k = (e["market_type"], e["team"], e["season"])
        if k != key:
            continue
        if cand is None or e["timestamp_utc"] > cand["timestamp_utc"]:
            cand = e
    return cand


def build_resolved_sample(entries: list[dict] | None = None) -> list[BenchmarkRow]:
    if entries is None:
        entries = read_all()
    signals = filter_entries(entries, source="signal")
    closings = filter_entries(entries, source="closing")
    resolutions = filter_entries(entries, source="resolution")

    # Key → latest entry for that key
    def pick_latest(source_rows: list[dict]) -> dict[tuple, dict]:
        out: dict[tuple, dict] = {}
        for e in source_rows:
            k = (e["market_type"], e["team"], e["season"])
            if k not in out or e["timestamp_utc"] > out[k]["timestamp_utc"]:
                out[k] = e
        return out

    latest_closings = pick_latest(closings)
    latest_resolutions = pick_latest(resolutions)
    latest_signals = pick_latest(signals)

    rows: list[BenchmarkRow] = []
    for key, sig in latest_signals.items():
        clos = latest_closings.get(key)
        res = latest_resolutions.get(key)
        if clos is None or res is None:
            continue
        outcome = int(res["market_prob"] >= 0.5)
        ai_p = sig["ai_prob"]
        mkt_p = clos["market_prob"]
        if ai_p is None:
            continue
        rows.append(
            BenchmarkRow(
                market_type=key[0],
                team=key[1],
                season=key[2],
                ai_prob=float(ai_p),
                market_close_prob=float(mkt_p),
                outcome=outcome,
                model_sq_err=(float(ai_p) - outcome) ** 2,
                market_sq_err=(float(mkt_p) - outcome) ** 2,
            )
        )
    return rows


def benchmark_stats(rows: list[BenchmarkRow]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0}

    model_brier = sum(r.model_sq_err for r in rows) / n
    market_brier = sum(r.market_sq_err for r in rows) / n
    bss = (
        1 - model_brier / market_brier
        if market_brier > 0 else float("nan")
    )

    # Paired t-test on (market_sq_err − model_sq_err)
    # H1: model has lower squared error than market
    diffs = [r.market_sq_err - r.model_sq_err for r in rows]
    mean_d = sum(diffs) / n
    if n > 1:
        var_d = sum((d - mean_d) ** 2 for d in diffs) / (n - 1)
        sd_d = math.sqrt(var_d)
        se_d = sd_d / math.sqrt(n)
        t_stat = mean_d / se_d if se_d > 0 else float("nan")
        p_one_sided = (
            0.5 * math.erfc(t_stat / math.sqrt(2))
            if t_stat == t_stat else float("nan")
        )
    else:
        sd_d = 0.0
        se_d = 0.0
        t_stat = float("nan")
        p_one_sided = float("nan")

    return {
        "n": n,
        "model_brier": round(model_brier, 4),
        "market_brier": round(market_brier, 4),
        "brier_skill_score": round(bss, 4) if bss == bss else None,
        "mean_err_gap_pp": round(mean_d, 4),
        "t_stat": round(t_stat, 3) if t_stat == t_stat else None,
        "p_one_sided": round(p_one_sided, 4) if p_one_sided == p_one_sided else None,
        "model_wins_per_event": sum(
            1 for r in rows if r.model_sq_err < r.market_sq_err
        ),
    }


def per_market_breakdown(rows: list[BenchmarkRow]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    groups: dict[str, list[BenchmarkRow]] = {}
    for r in rows:
        groups.setdefault(r.market_type, []).append(r)
    out_rows = []
    for mt, sub in groups.items():
        s = benchmark_stats(sub)
        s["market_type"] = mt
        out_rows.append(s)
    return pd.DataFrame(out_rows)


def paired_table(rows: list[BenchmarkRow]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([r.__dict__ for r in rows]).round({
        "ai_prob": 3,
        "market_close_prob": 3,
        "model_sq_err": 4,
        "market_sq_err": 4,
    })
