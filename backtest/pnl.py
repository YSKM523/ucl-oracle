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

from markets.signal_log import canonical_event_slug, filter_entries, read_all

# Below this implied probability on the side we're betting, the order book is
# assumed too thin / stale / rounded to execute against. Guards the Kelly math
# from fabricating billion-to-one odds when a closed or boundary-priced market
# would otherwise push decimal odds to infinity.
MIN_EXECUTABLE_PROB = 0.01
MAX_EXECUTABLE_PROB = 1 - MIN_EXECUTABLE_PROB


@dataclass
class Bet:
    ts_signal: str
    ts_resolution: str           # when PnL actually lands
    market_type: str
    team: str
    season: str
    direction: str               # 'BUY' or 'SELL'
    entry_prob: float            # market implied prob at signal time
    ai_prob: float
    kelly_fraction: float        # full-Kelly stake fraction (may be negative)
    stake: float                 # stake committed at placement (after scaling)
    decimal_odds: float
    outcome: int                 # 1 = event happened, 0 = event didn't
    bet_wins: bool               # whether THIS bet pays out (direction-aware)
    pnl: float                   # stake-weighted PnL for this bet
    bankroll_at_placement: float # bankroll when bet was sized (no peek)
    bankroll_after: float        # bankroll after this bet settles


def _full_kelly(p: float, market_prob: float) -> tuple[float, float]:
    """Return (kelly_fraction, decimal_odds) for a bet whose side trades at
    ``market_prob``. Caller MUST pre-validate ``market_prob`` is inside
    ``(MIN_EXECUTABLE_PROB, MAX_EXECUTABLE_PROB)`` before calling; this
    function no longer masks boundary values because doing so fabricated
    near-infinite decimal odds on closed or rounded markets.
    """
    if not (0.0 < market_prob < 1.0):
        raise ValueError(
            f"market_prob out of range (0, 1): got {market_prob!r}"
        )
    d = 1.0 / market_prob
    b = d - 1.0
    f = (p * d - 1.0) / b
    return f, d


def _is_executable_side(side_prob: float) -> bool:
    """True iff the price we'd stake against is within the configured
    tradeable range. Rejects 0.0 / 1.0 / outside-band as non-executable."""
    return MIN_EXECUTABLE_PROB <= side_prob <= MAX_EXECUTABLE_PROB


def _key(entry: dict) -> tuple:
    """Compound pairing key: (market_type, team, season, canonical event_slug)."""
    return (
        entry["market_type"],
        entry["team"],
        entry["season"],
        canonical_event_slug(entry["market_type"], entry.get("event_slug")),
    )


def _index_by_key_sorted(
    entries: list[dict], source: str,
) -> dict[tuple, list[dict]]:
    """All entries of one source, grouped by _key, each list sorted by timestamp."""
    out: dict[tuple, list[dict]] = {}
    for e in filter_entries(entries, source=source):
        out.setdefault(_key(e), []).append(e)
    for k in out:
        out[k].sort(key=lambda r: r["timestamp_utc"])
    return out


def _first_after(
    rows: list[dict], after_ts: str,
    before_ts: str | None = None,
) -> dict | None:
    """First row whose timestamp is strictly after ``after_ts`` (and strictly
    before ``before_ts`` if given). Input list must already be timestamp-sorted."""
    for r in rows:
        if r["timestamp_utc"] <= after_ts:
            continue
        if before_ts is not None and r["timestamp_utc"] >= before_ts:
            return None
        return r
    return None


def simulate_pnl(
    entries: list[dict] | None = None,
    starting_bankroll: float = 100.0,
    kelly_multiplier: float = 0.5,
    min_edge_pct: float = 3.0,
    require_resolution: bool = True,
    require_closing: bool = False,
) -> tuple[list[Bet], pd.DataFrame]:
    """Walk the signal log in time order, placing Half-Kelly bets.

    Pairing invariants (enforced to eliminate look-ahead / stale-match contamination):
      • Resolutions and signals must share the full 4-tuple key
        ``(market_type, team, season, canonical_event_slug)``. A different
        ``event_slug`` for the same team in the same season — e.g. a repeat
        opponent in a later round — is no longer conflated.
      • A signal is paired with the EARLIEST resolution that is timestamped
        strictly after the signal. Post-resolution signals (logged after a
        result is already recorded) are skipped, not silently back-dated.
      • When ``require_closing=True``, a closing row must also exist with
        ``signal.ts < closing.ts < resolution.ts`` — i.e. the report only
        recognises a fully-ordered triple.

    Returns ``(list_of_bet_records, bankroll_trajectory_df)``.
    """
    if entries is None:
        entries = read_all()

    resolutions_by_key = _index_by_key_sorted(entries, source="resolution")
    closings_by_key = (
        _index_by_key_sorted(entries, source="closing") if require_closing else {}
    )

    # All signals that cross the min-edge threshold, chronological
    signals = [
        e for e in filter_entries(entries, source="signal")
        if e.get("signal") in {"BUY", "SELL", "STRONG BUY", "STRONG SELL"}
        and (e.get("edge_pct") is None or abs(e["edge_pct"]) >= min_edge_pct)
    ]
    signals.sort(key=lambda e: e["timestamp_utc"])

    # ── Pair each eligible signal with its resolution ──────────────────
    # Skip signals that violate the pairing invariants (post-resolution,
    # closing out of order, no resolution yet).
    paired: list[tuple[dict, dict]] = []
    for sig in signals:
        key = _key(sig)
        res = _first_after(resolutions_by_key.get(key, []), sig["timestamp_utc"])
        if require_resolution and res is None:
            continue
        if res is None:
            # require_resolution=False + no res → can't simulate a bet
            continue
        if require_closing:
            clos = _first_after(
                closings_by_key.get(key, []),
                sig["timestamp_utc"],
                before_ts=res["timestamp_utc"],
            )
            if clos is None:
                continue
        paired.append((sig, res))

    # ── Build a merged placement / settlement event timeline ──────────
    # kind ordering at same timestamp: settlements first (free bankroll
    # before sizing new placements), then placements. Stable secondary
    # ordering by paired-list index keeps behaviour deterministic.
    kind_order = {"settle": 0, "place": 1}
    events: list[tuple[str, str, int]] = []
    for idx, (sig, res) in enumerate(paired):
        events.append((sig["timestamp_utc"], "place", idx))
        events.append((res["timestamp_utc"], "settle", idx))
    events.sort(key=lambda e: (e[0], kind_order[e[1]], e[2]))

    bankroll = starting_bankroll
    open_bets: dict[int, dict] = {}       # idx → {stake, direction, decimal_odds, …}
    settled_bets: list[Bet] = []          # completed, in settlement order
    traj_rows: list[dict] = [{
        "ts": events[0][0] if events else None,
        "event": "start", "bankroll": bankroll,
    }] if events else []

    # Walk the timeline in (ts, kind) groups so same-timestamp events
    # resolve collectively: settle everything first, snapshot bankroll,
    # size all placements off that single snapshot.
    i = 0
    while i < len(events):
        ts = events[i][0]
        group = []
        while i < len(events) and events[i][0] == ts:
            group.append(events[i])
            i += 1

        # 1) Process all settlements at this timestamp first.
        for _, kind, idx in group:
            if kind != "settle":
                continue
            if idx not in open_bets:
                # Its placement was rejected (e.g. non-executable boundary
                # price). Nothing to settle. Already recorded as 'rejected'
                # in the trajectory.
                continue
            bet_state = open_bets.pop(idx)
            sig, res = paired[idx]
            outcome = int(res["market_prob"] >= 0.5)
            direction = bet_state["direction"]
            bet_wins = (
                (direction == "BUY" and outcome == 1)
                or (direction == "SELL" and outcome == 0)
            )
            stake = bet_state["stake"]
            pnl = (
                stake * (bet_state["decimal_odds"] - 1.0) if bet_wins
                else -stake
            )
            bankroll += pnl
            settled_bets.append(
                Bet(
                    ts_signal=sig["timestamp_utc"],
                    ts_resolution=res["timestamp_utc"],
                    market_type=sig["market_type"],
                    team=sig["team"],
                    season=sig["season"],
                    direction=direction,
                    entry_prob=bet_state["entry_prob"],
                    ai_prob=bet_state["ai_prob"],
                    kelly_fraction=round(bet_state["kelly_fraction"], 4),
                    stake=round(stake, 4),
                    decimal_odds=round(bet_state["decimal_odds"], 4),
                    outcome=outcome,
                    bet_wins=bet_wins,
                    pnl=round(pnl, 4),
                    bankroll_at_placement=round(
                        bet_state["bankroll_at_placement"], 4
                    ),
                    bankroll_after=round(bankroll, 4),
                )
            )
            traj_rows.append({
                "ts": res["timestamp_utc"],
                "event": f"settle {direction} {sig['team']} ({sig['market_type']})",
                "bankroll": round(bankroll, 4),
            })

        # 2) Snapshot bankroll for all placements at this timestamp.
        placement_snapshot = bankroll
        # Available capital = snapshot minus still-open committed stakes.
        # Same-timestamp placements all share this same snapshot.
        committed = sum(b["stake"] for b in open_bets.values())
        free = max(0.0, placement_snapshot - committed)

        # Compute proposed stakes for every placement at this ts.
        proposals: list[tuple[int, float, dict]] = []
        for _, kind, idx in group:
            if kind != "place":
                continue
            sig, _ = paired[idx]
            ai_p = sig["ai_prob"]
            mkt_p = sig["market_prob"]
            direction = "BUY" if "BUY" in sig["signal"].upper() else "SELL"
            if direction == "BUY":
                p, m = ai_p, mkt_p
            else:
                p, m = 1 - ai_p, 1 - mkt_p
            # Boundary guard: the side we'd stake against must be a
            # plausibly executable price. 0.0 / 1.0 / sub-1% markets are
            # treated as non-executable rather than fabricated into
            # near-infinite decimal odds.
            if not _is_executable_side(m):
                traj_rows.append({
                    "ts": sig["timestamp_utc"],
                    "event": (
                        f"rejected {direction} {sig['team']} "
                        f"({sig['market_type']}) — side_prob={m:.4f} "
                        f"outside [{MIN_EXECUTABLE_PROB}, {MAX_EXECUTABLE_PROB}]"
                    ),
                    "bankroll": round(bankroll, 4),
                })
                continue
            f_full, d_odds = _full_kelly(p, m)
            stake_frac = max(0.0, f_full) * kelly_multiplier
            proposed = placement_snapshot * stake_frac
            if proposed <= 0:
                continue
            proposals.append(
                (idx, proposed, {
                    "direction": direction,
                    "decimal_odds": d_odds,
                    "kelly_fraction": f_full,
                    "entry_prob": mkt_p,
                    "ai_prob": ai_p,
                }),
            )

        # 3) Scale down pro-rata if collective stake would exceed free capital.
        total_proposed = sum(p for _, p, _ in proposals)
        scale = 1.0
        if total_proposed > free > 0:
            scale = free / total_proposed
        elif total_proposed > 0 and free <= 0:
            # Fully committed elsewhere — no new placements can open.
            proposals = []

        # 4) Open bets at this timestamp — all from the same snapshot.
        for idx, proposed, meta in proposals:
            final_stake = proposed * scale
            if final_stake <= 0:
                continue
            open_bets[idx] = {
                "stake": final_stake,
                "bankroll_at_placement": placement_snapshot,
                **meta,
            }
            sig, _ = paired[idx]
            traj_rows.append({
                "ts": sig["timestamp_utc"],
                "event": (
                    f"place {meta['direction']} {sig['team']} "
                    f"({sig['market_type']}) stake={final_stake:.2f}"
                ),
                "bankroll": round(bankroll, 4),  # unchanged at placement
            })

    return settled_bets, pd.DataFrame(traj_rows)


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
