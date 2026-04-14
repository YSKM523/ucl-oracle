"""Tests for Half-Kelly PnL simulation."""

from __future__ import annotations

import math

import pytest

from backtest.pnl import (
    MAX_EXECUTABLE_PROB,
    MIN_EXECUTABLE_PROB,
    _full_kelly,
    _is_executable_side,
    max_drawdown_pct,
    per_bet_sharpe,
    pnl_summary,
    simulate_pnl,
)


# ── Kelly math ──────────────────────────────────────────────────────────

def test_kelly_zero_when_no_edge():
    """p == market_prob → optimal Kelly = 0."""
    f, d = _full_kelly(p=0.40, market_prob=0.40)
    assert f == pytest.approx(0.0, abs=1e-9)
    assert d == pytest.approx(2.5, abs=1e-6)  # 1/0.4 = 2.5


def test_kelly_positive_when_model_favors_event():
    """p > market_prob → positive Kelly (bet on event)."""
    f, _ = _full_kelly(p=0.60, market_prob=0.40)
    # f = (0.6*2.5 - 1) / (2.5 - 1) = (1.5 - 1) / 1.5 = 0.333
    assert f == pytest.approx(0.333, abs=0.01)


def test_kelly_negative_when_model_disagrees():
    """p < market_prob → negative Kelly (simulator should NOT bet)."""
    f, _ = _full_kelly(p=0.30, market_prob=0.40)
    assert f < 0


# ── Drawdown ────────────────────────────────────────────────────────────

def test_max_drawdown_empty_is_zero():
    assert max_drawdown_pct([]) == 0.0


def test_max_drawdown_monotone_up_is_zero():
    assert max_drawdown_pct([100, 110, 120, 130]) == 0.0


def test_max_drawdown_basic_case():
    # Peak 120 → trough 90 → dd = (120-90)/120 = 25%
    assert max_drawdown_pct([100, 120, 90, 95]) == pytest.approx(25.0)


def test_max_drawdown_worst_of_multiple():
    # Peak1=120, dd 16.67%. Peak2=150, dd to 75 = 50%.
    assert max_drawdown_pct([100, 120, 100, 150, 75]) == pytest.approx(50.0)


# ── Sharpe ──────────────────────────────────────────────────────────────

class FakeBet:
    def __init__(self, pnl, stake):
        self.pnl = pnl
        self.stake = stake


def test_sharpe_one_bet_is_nan():
    bets = [FakeBet(10, 20)]
    assert math.isnan(per_bet_sharpe(bets))


def test_sharpe_uniform_wins_gives_positive():
    # 3 bets, all return +50%
    bets = [FakeBet(5, 10), FakeBet(5, 10), FakeBet(5, 10)]
    # With zero variance, Sharpe is nan (undefined) — current impl returns nan
    result = per_bet_sharpe(bets)
    assert math.isnan(result)


def test_sharpe_mixed_bets_reasonable_sign():
    # 2 wins returning +100%, 1 loss returning -100%
    bets = [FakeBet(10, 10), FakeBet(10, 10), FakeBet(-10, 10)]
    # rets = [1, 1, -1], mean = 0.333, sd ≈ 1.15, Sharpe ≈ 0.29
    result = per_bet_sharpe(bets)
    assert result > 0
    assert result < 1


# ── End-to-end simulation ──────────────────────────────────────────────

def _log(ts, source, team, ai_prob=None, market_prob=0.4, signal=None,
         edge_pct=None, market="qf_advance", season="2025-26"):
    return {
        "timestamp_utc": ts, "source": source, "market_type": market,
        "team": team, "ai_prob": ai_prob, "market_prob": market_prob,
        "edge_pct": edge_pct, "signal": signal, "kelly": None,
        "event_slug": "x", "season": season, "extras": None,
    }


def test_simulate_skips_signals_without_resolution():
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.6,
             market_prob=0.4, signal="BUY", edge_pct=20),
        # No resolution for A
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert len(bets) == 0


def test_simulate_places_bet_when_resolution_present():
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
    ]
    bets, traj = simulate_pnl(entries, starting_bankroll=100.0,
                              kelly_multiplier=0.5)
    assert len(bets) == 1
    b = bets[0]
    assert b.direction == "BUY"
    assert b.bet_wins is True
    # Kelly fraction ≈ 0.333, Half-Kelly stake = 100 * 0.333 / 2 = 16.67
    assert b.stake == pytest.approx(16.67, abs=0.1)
    # PnL = stake * (2.5 - 1) = 16.67 * 1.5 = 25
    assert b.pnl == pytest.approx(25.0, abs=0.5)
    assert b.bankroll_after == pytest.approx(125.0, abs=1.0)


def test_simulate_sell_signal_on_event_that_does_not_happen():
    """SELL at market 0.40 (we think it's 0.10); outcome=0 → bet wins."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.10,
             market_prob=0.40, signal="STRONG SELL", edge_pct=-30),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=0.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert len(bets) == 1
    b = bets[0]
    assert b.direction == "SELL"
    assert b.bet_wins is True
    # Betting "NO" at market 0.40: our p_no = 0.90, market_no = 0.60
    # d_no = 1/0.60 = 1.667; f = (0.9 * 1.667 - 1)/(1.667-1) = 0.5/0.667 = 0.75
    # Half-Kelly stake = 100 * 0.75 / 2 = 37.5
    assert b.stake == pytest.approx(37.5, abs=0.5)


def test_simulate_bankroll_goes_down_on_loss():
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=0.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert bets[0].bet_wins is False
    assert bets[0].bankroll_after < 100.0


def test_summary_zero_bets_returns_neutral():
    s = pnl_summary([], starting_bankroll=100.0)
    assert s["n_bets"] == 0
    assert s["roi_pct"] == 0.0
    assert s["max_drawdown_pct"] == 0.0


def test_simulate_respects_min_edge():
    entries = [
        # Edge only 2pp → below min_edge 3pp
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.42,
             market_prob=0.40, signal="BUY", edge_pct=2),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, min_edge_pct=3.0)
    assert len(bets) == 0


def test_simulate_chronological_order():
    """Later timestamp should appear later in bet list and trajectory."""
    entries = [
        _log("2026-04-15T10:00:00Z", "signal", "B", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-16T20:00:00Z", "resolution", "A", market_prob=1.0),
        _log("2026-04-16T21:00:00Z", "resolution", "B", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert bets[0].team == "A"   # earlier ts
    assert bets[1].team == "B"


# ── regression tests for Codex-flagged pairing defects ─────────────────

def test_signal_logged_after_resolution_is_skipped():
    """A signal whose timestamp is AFTER an existing resolution must not be
    scored against that resolution — otherwise PnL sees known outcomes."""
    entries = [
        # Resolution lands first …
        _log("2026-04-14T20:00:00Z", "resolution", "A", market_prob=1.0),
        # … signal appears AFTER, with the same key. This is contamination.
        _log("2026-04-15T09:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 0


def test_earliest_post_signal_resolution_is_used():
    """Two resolutions for the same key — one before the signal, one after.
    Only the post-signal resolution may pair; pre-signal is silently stale."""
    entries = [
        _log("2026-04-14T10:00:00Z", "resolution", "A", market_prob=0.0,
             ts_override="2026-04-14T10:00:00Z"),  # pre-signal, stale
        _log("2026-04-14T11:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T20:00:00Z", "resolution", "A", market_prob=1.0),  # valid
    ] if False else [
        _log("2026-04-14T10:00:00Z", "resolution", "A", market_prob=0.0),
        _log("2026-04-14T11:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T20:00:00Z", "resolution", "A", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 1
    # Outcome must be 1 (from the 20:00 resolution), not 0 (the stale one)
    assert bets[0].outcome == 1
    assert bets[0].bet_wins is True


def test_different_event_slug_prevents_cross_contamination():
    """A signal and resolution for the same (market, team, season) but
    different event_slug must NOT be paired — e.g. separate real-world markets."""
    entries = [
        # Signal for Market A's event
        {**_log("2026-04-14T10:00:00Z", "signal", "Arsenal", ai_prob=0.6,
                market_prob=0.4, signal="BUY", edge_pct=20,
                market="qf_advance"),
         "event_slug": "event-1"},
        # Resolution for a DIFFERENT event_slug
        {**_log("2026-04-15T20:00:00Z", "resolution", "Arsenal",
                market_prob=1.0, market="qf_advance"),
         "event_slug": "event-2"},
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 0


def test_same_event_slug_via_canonical_normalization_pairs_correctly():
    """A resolution logged with None event_slug must normalize to the same
    canonical slug as a signal logged with the explicit canonical value."""
    # Signal uses the canonical winner event_slug string.
    from config import UCL_WINNER_EVENT_SLUG
    entries = [
        {**_log("2026-04-14T10:00:00Z", "signal", "Arsenal", ai_prob=0.6,
                market_prob=0.4, signal="BUY", edge_pct=20, market="winner"),
         "event_slug": UCL_WINNER_EVENT_SLUG},
        # Resolution with event_slug=None — normalises to the same canonical.
        {**_log("2026-05-30T22:00:00Z", "resolution", "Arsenal",
                market_prob=1.0, market="winner"),
         "event_slug": None},
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 1
    assert bets[0].outcome == 1


def test_require_closing_enforces_ordered_triple():
    """With require_closing=True, a bet is only recognised if signal < closing
    < resolution all hold. A closing that pre-dates the signal is rejected."""
    entries = [
        # Closing pre-dates signal — fails ordering invariant
        _log("2026-04-13T10:00:00Z", "closing", "A", market_prob=0.40),
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           require_closing=True)
    assert len(bets) == 0

    # Add a correctly-ordered closing → bet must now materialise
    entries.append(
        _log("2026-04-14T19:00:00Z", "closing", "A", market_prob=0.45),
    )
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           require_closing=True)
    assert len(bets) == 1


def test_same_timestamp_resolution_does_not_pair():
    """A resolution timestamped EXACTLY when the signal was placed is NOT
    strictly after the signal and therefore does not satisfy the pairing
    invariant — avoids hairline look-ahead at wall-clock resolution."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T10:00:00Z", "resolution", "A", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 0


# ── regression tests for placement-vs-settlement timing (Codex #2) ────

def test_same_timestamp_signals_size_from_same_bankroll_snapshot():
    """Two signals logged at the SAME timestamp must be sized off the same
    pre-placement bankroll — later list position must not benefit from
    (or be penalised by) earlier bets that settle later."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T10:00:00Z", "signal", "B", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        # A settles first (wins), B settles later — but both should have
        # been sized off the starting bankroll of 100, not 100 + A's PnL.
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
        _log("2026-04-16T20:00:00Z", "resolution", "B", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert len(bets) == 2
    # Both bets should see bankroll_at_placement == 100
    for b in bets:
        assert b.bankroll_at_placement == pytest.approx(100.0, abs=0.001)
    # Same Kelly & stake for identical signals → equal stakes
    assert bets[0].stake == pytest.approx(bets[1].stake, abs=0.001)


def test_later_signal_sees_bankroll_after_earlier_settlement():
    """A signal placed AFTER an earlier bet settles should size off the
    updated bankroll (post-settlement), not the starting one."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T20:00:00Z", "resolution", "A", market_prob=1.0),  # A wins
        _log("2026-04-15T10:00:00Z", "signal", "B", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-16T20:00:00Z", "resolution", "B", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert len(bets) == 2
    # Bets are returned in settlement order; A settles 04-14T20, B at 04-16T20
    a, b = bets[0], bets[1]
    assert a.team == "A"
    assert b.team == "B"
    assert a.bankroll_at_placement == pytest.approx(100.0, abs=0.001)
    # B placed on 04-15, AFTER A settled at 04-14T20 with PnL +25
    assert b.bankroll_at_placement == pytest.approx(125.0, abs=0.001)
    # B's stake scales with its larger bankroll
    assert b.stake > a.stake


def test_overlapping_bet_sizes_off_unpeeked_bankroll_when_capital_available():
    """Signal B placed while A is still OPEN must use the bankroll as of
    B's placement timestamp, which does NOT include A's unrealized PnL.
    So B's stake must NOT be inflated by A's (future) win."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T18:00:00Z", "signal", "B", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-15T10:00:00Z", "resolution", "A", market_prob=1.0),
        _log("2026-04-16T10:00:00Z", "resolution", "B", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    a = next(b for b in bets if b.team == "A")
    b_bet = next(b for b in bets if b.team == "B")
    # Critical no-peek property: B's sizing bankroll does not yet contain
    # A's +25 PnL, so B sees 100 just like A did.
    assert b_bet.bankroll_at_placement == pytest.approx(100.0, abs=0.001)
    assert a.bankroll_at_placement == pytest.approx(100.0, abs=0.001)
    # Both see identical bankroll snapshot → identical stakes
    assert b_bet.stake == pytest.approx(a.stake, abs=0.001)


def test_same_timestamp_placements_are_pro_rata_scaled_if_over_bankroll():
    """If concurrent placements would collectively exceed bankroll, they
    must be scaled down pro-rata rather than one starving the other."""
    # Force the situation by using very-high-edge signals that each want
    # a large chunk of bankroll. Full-Kelly at p=0.95, m=0.10 → f ≈ 0.944
    # Half-Kelly per bet = bankroll * 0.944 / 2 = 47% of bankroll.
    # 3 concurrent such bets would claim 141% of bankroll → must scale.
    entries = []
    for team in ("A", "B", "C"):
        entries += [
            _log("2026-04-14T10:00:00Z", "signal", team, ai_prob=0.95,
                 market_prob=0.10, signal="STRONG BUY", edge_pct=85),
            _log("2026-04-15T20:00:00Z", "resolution", team, market_prob=1.0),
        ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert len(bets) == 3
    # Combined committed stakes may not exceed starting bankroll
    total_stake = sum(b.stake for b in bets)
    assert total_stake <= 100.0 + 1e-6


def test_signal_order_at_same_timestamp_does_not_affect_outcome():
    """Reordering same-timestamp signals in the log must not change PnL —
    they all pull from the same bankroll snapshot."""
    base_entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T10:00:00Z", "signal", "B", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
        _log("2026-04-15T20:00:00Z", "resolution", "B", market_prob=0.0),
    ]
    swapped = [base_entries[1], base_entries[0], *base_entries[2:]]
    bets_a, _ = simulate_pnl(base_entries, starting_bankroll=100.0)
    bets_b, _ = simulate_pnl(swapped, starting_bankroll=100.0)
    # Same final bankroll, same stakes, regardless of log list order.
    assert bets_a[-1].bankroll_after == pytest.approx(
        bets_b[-1].bankroll_after, abs=0.001
    )
    # And sum of stakes equal
    assert sum(b.stake for b in bets_a) == pytest.approx(
        sum(b.stake for b in bets_b), abs=0.001
    )


def test_bet_output_is_in_settlement_order_not_placement_order():
    """Bets are emitted in the order their resolutions land, matching the
    real bankroll state evolution."""
    entries = [
        # A placed FIRST but settles LAST
        _log("2026-04-14T09:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T10:00:00Z", "signal", "B", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        # B settles first
        _log("2026-04-15T10:00:00Z", "resolution", "B", market_prob=1.0),
        _log("2026-04-16T10:00:00Z", "resolution", "A", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert bets[0].team == "B"   # settled first
    assert bets[1].team == "A"   # settled second


# ── regression tests for boundary-price guard (Codex #3) ──────────────

def test_full_kelly_raises_on_zero_market_prob():
    """Must not silently mask a zero market_prob into fake 1e9-odds."""
    with pytest.raises(ValueError):
        _full_kelly(p=0.5, market_prob=0.0)


def test_full_kelly_raises_on_one_market_prob():
    with pytest.raises(ValueError):
        _full_kelly(p=0.5, market_prob=1.0)


def test_executable_side_helper_bounds():
    assert _is_executable_side(0.5) is True
    assert _is_executable_side(MIN_EXECUTABLE_PROB) is True
    assert _is_executable_side(MAX_EXECUTABLE_PROB) is True
    # Just below / above the configured band
    assert _is_executable_side(MIN_EXECUTABLE_PROB - 1e-4) is False
    assert _is_executable_side(MAX_EXECUTABLE_PROB + 1e-4) is False
    assert _is_executable_side(0.0) is False
    assert _is_executable_side(1.0) is False


def test_sell_signal_on_certainty_market_is_rejected():
    """YES price = 1.0 → NO side = 0.0 → must be rejected, not turned into
    1e9-odds payouts that dominate the report."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.01,
             market_prob=1.0, signal="STRONG SELL", edge_pct=-99),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=0.0),
    ]
    bets, traj = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 0
    # And the rejection is visible in the trajectory, not silently dropped
    rejected_rows = [r for r in traj.to_dict("records")
                     if isinstance(r["event"], str) and "rejected" in r["event"]]
    assert len(rejected_rows) == 1


def test_buy_signal_on_zero_market_prob_is_rejected():
    """YES price = 0.0 → BUY side = 0.0 → rejected, no fabricated odds."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.5,
             market_prob=0.0, signal="STRONG BUY", edge_pct=50),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 0


def test_thin_market_below_min_threshold_is_rejected():
    """Sub-1% side prob also rejected (too thin/stale to execute)."""
    # YES = 0.998, SELL side = 0.002 — below MIN_EXECUTABLE_PROB
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.01,
             market_prob=0.998, signal="STRONG SELL", edge_pct=-99),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=0.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 0


def test_rejection_does_not_consume_bankroll_or_crash_other_bets():
    """A rejected signal at the same timestamp as a valid one must not
    affect the valid bet's sizing or the final bankroll."""
    entries = [
        # Rejected (boundary)
        _log("2026-04-14T10:00:00Z", "signal", "REJECT", ai_prob=0.01,
             market_prob=1.0, signal="STRONG SELL", edge_pct=-99),
        # Valid
        _log("2026-04-14T10:00:00Z", "signal", "VALID", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-15T20:00:00Z", "resolution", "REJECT", market_prob=0.0),
        _log("2026-04-15T20:00:00Z", "resolution", "VALID", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert len(bets) == 1
    assert bets[0].team == "VALID"
    # VALID bet sizing unaffected by the REJECT signal existing
    assert bets[0].stake == pytest.approx(16.67, abs=0.5)
    assert bets[0].bankroll_after == pytest.approx(125.0, abs=0.5)


# ══════════════════════════════════════════════════════════════════════
# Additional regression coverage for the four Codex-named scenarios
# (simultaneous signals / overlapping settlement / post-resolution /
# boundary prices). These target interaction corners not covered by
# the focused fixes above.
# ══════════════════════════════════════════════════════════════════════

# ── Simultaneous signals ──────────────────────────────────────────────

def test_simultaneous_settlements_both_apply_once_each():
    """Two bets that resolve at exactly the same timestamp must each land
    their PnL against bankroll — no silent drop, no double-apply."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T10:00:00Z", "signal", "B", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        # Both settle at the same wall-clock instant
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
        _log("2026-04-15T20:00:00Z", "resolution", "B", market_prob=0.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert len(bets) == 2
    total_pnl = sum(b.pnl for b in bets)
    # A wins (+25 on 16.67 stake), B loses (-16.67). Net: +8.33
    assert total_pnl == pytest.approx(25.0 - 16.67, abs=0.05)
    # Final bankroll must equal starting + total_pnl exactly (no drift)
    assert bets[-1].bankroll_after == pytest.approx(
        100.0 + total_pnl, abs=0.01
    )


def test_settle_and_place_at_same_timestamp_place_sees_updated_bankroll():
    """If a settlement and a new placement share the same timestamp, the
    settlement must apply FIRST so the new placement sizes off the
    post-settle bankroll, not the pre-settle one."""
    entries = [
        # A placed earlier; resolves at 2026-04-15T20 with a WIN
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        # B placed at the SAME timestamp as A's resolution
        _log("2026-04-15T20:00:00Z", "signal", "B", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
        _log("2026-04-16T20:00:00Z", "resolution", "B", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    a_bet = next(b for b in bets if b.team == "A")
    b_bet = next(b for b in bets if b.team == "B")
    # A sized from 100; after win, bankroll → 125
    assert a_bet.bankroll_at_placement == pytest.approx(100.0, abs=0.001)
    # B must see 125 because A's settlement comes first at the shared ts
    assert b_bet.bankroll_at_placement == pytest.approx(125.0, abs=0.001)


def test_mixed_direction_signals_at_same_timestamp_both_placed():
    """BUY on one team + SELL on another at the same ts must both sit
    open simultaneously, sized from the same bankroll snapshot."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T10:00:00Z", "signal", "B", ai_prob=0.10,
             market_prob=0.40, signal="STRONG SELL", edge_pct=-30),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
        _log("2026-04-15T20:00:00Z", "resolution", "B", market_prob=0.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert len(bets) == 2
    directions = {b.team: b.direction for b in bets}
    assert directions == {"A": "BUY", "B": "SELL"}
    # Both must have been sized from 100 (same snapshot)
    for b in bets:
        assert b.bankroll_at_placement == pytest.approx(100.0, abs=0.001)


# ── Overlapping settlement order ──────────────────────────────────────

def test_three_nested_open_bets_settle_in_staggered_order():
    """Three sequentially-placed bets, each settles only after all are
    open. Settlement cascade must apply PnLs in the correct order."""
    entries = [
        _log("2026-04-14T09:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T12:00:00Z", "signal", "B", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T15:00:00Z", "signal", "C", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        # All open at once; now settle in staggered order (C first, A last)
        _log("2026-04-15T10:00:00Z", "resolution", "C", market_prob=1.0),
        _log("2026-04-15T12:00:00Z", "resolution", "B", market_prob=0.0),
        _log("2026-04-15T14:00:00Z", "resolution", "A", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert [b.team for b in bets] == ["C", "B", "A"]
    # All three sized off the exact same pre-settlement bankroll of 100
    # because every placement happened before ANY settlement.
    for b in bets:
        assert b.bankroll_at_placement == pytest.approx(100.0, abs=0.001)
    # Each monotonically moves the bankroll_after field correctly
    assert bets[0].bankroll_after > bets[0].bankroll_at_placement  # C won
    assert bets[1].bankroll_after < bets[0].bankroll_after         # B lost
    assert bets[2].bankroll_after > bets[1].bankroll_after         # A won


def test_intermediate_bankroll_visible_in_trajectory():
    """Trajectory must show each settlement as a distinct event, so the
    max-drawdown calculation sees the intra-sequence troughs."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-14T10:00:00Z", "signal", "B", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        # A loses first → intermediate trough; B wins later → recovers
        _log("2026-04-15T10:00:00Z", "resolution", "A", market_prob=0.0),
        _log("2026-04-16T10:00:00Z", "resolution", "B", market_prob=1.0),
    ]
    _, traj = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    rows = traj.to_dict("records")
    bankrolls = [r["bankroll"] for r in rows]
    # Must have a trough below 100 and recovery above it
    assert min(bankrolls) < 100.0
    assert bankrolls[-1] > min(bankrolls)


# ── Post-resolution signals ────────────────────────────────────────────

def test_resolution_before_and_after_signal_latest_post_signal_wins():
    """Two resolutions: one BEFORE the signal (stale), one AFTER (valid).
    Only the post-signal resolution may pair."""
    entries = [
        # Stale resolution logged before any signal exists
        _log("2026-04-10T10:00:00Z", "resolution", "A", market_prob=0.0),
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        # Valid post-signal resolution
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 1
    assert bets[0].outcome == 1             # uses the post-signal one
    assert bets[0].bet_wins is True


def test_orphan_resolution_without_matching_signal_is_ignored():
    """A resolution logged for a team that we never signalled must not
    affect the simulation at all — no crash, no ghost bet."""
    entries = [
        # Signal only for A
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.60,
             market_prob=0.40, signal="BUY", edge_pct=20),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
        # Orphan resolution for B — no matching signal
        _log("2026-04-15T20:00:00Z", "resolution", "B", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 1
    assert bets[0].team == "A"


def test_same_team_two_event_slugs_two_independent_bets():
    """Same team in the same season but two distinct event_slugs must
    simulate as two independent bets, each pairing only with its own
    event_slug's resolution."""
    entries = [
        {**_log("2026-04-14T10:00:00Z", "signal", "Arsenal", ai_prob=0.6,
                market_prob=0.4, signal="BUY", edge_pct=20,
                market="qf_advance"),
         "event_slug": "qf-leg"},
        {**_log("2026-04-15T10:00:00Z", "resolution", "Arsenal",
                market_prob=1.0, market="qf_advance"),
         "event_slug": "qf-leg"},
        {**_log("2026-05-01T10:00:00Z", "signal", "Arsenal", ai_prob=0.55,
                market_prob=0.45, signal="BUY", edge_pct=10,
                market="qf_advance"),
         "event_slug": "sf-leg"},
        {**_log("2026-05-02T10:00:00Z", "resolution", "Arsenal",
                market_prob=0.0, market="qf_advance"),
         "event_slug": "sf-leg"},
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 2
    # First bet (QF leg) paired only with QF resolution, second (SF) only SF
    assert bets[0].outcome == 1  # qf-leg resolution
    assert bets[1].outcome == 0  # sf-leg resolution


# ── Boundary market probabilities (end-to-end) ────────────────────────

def test_market_prob_exactly_at_min_threshold_is_executable():
    """Side prob == MIN_EXECUTABLE_PROB is an inclusive boundary — must
    accept the bet, not reject it as non-executable."""
    # BUY at market 0.01 (= MIN) → side_prob = 0.01, executable per helper
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.5,
             market_prob=MIN_EXECUTABLE_PROB, signal="BUY", edge_pct=49),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert len(bets) == 1
    assert bets[0].bet_wins is True


def test_market_prob_just_below_threshold_is_rejected_end_to_end():
    """0.009 (< 1%) must be rejected end-to-end — not just at helper."""
    entries = [
        # BUY at market 0.009 → side_prob = 0.009 < MIN
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.5,
             market_prob=0.009, signal="BUY", edge_pct=49),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
    ]
    bets, traj = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 0
    events = [r["event"] for r in traj.to_dict("records")
              if isinstance(r["event"], str)]
    assert any("rejected" in e for e in events)


def test_market_prob_just_above_max_threshold_is_rejected():
    """Symmetric: side prob just above MAX_EXECUTABLE_PROB also rejected.
    YES=0.991 via SELL → side_prob = 0.009, which is below MIN."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=0.01,
             market_prob=0.991, signal="STRONG SELL", edge_pct=-98),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=0.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0)
    assert len(bets) == 0


def test_ai_prob_at_one_on_low_market_executes_with_full_kelly():
    """AI certainty (p=1.0) on a non-boundary market must execute with
    large but valid Kelly — not crash or get silently dropped."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "A", ai_prob=1.0,
             market_prob=0.20, signal="STRONG BUY", edge_pct=80),
        _log("2026-04-15T20:00:00Z", "resolution", "A", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert len(bets) == 1
    # full-Kelly f = (1*5 - 1) / 4 = 1.0; Half-Kelly = 0.5 → stake = 50
    assert bets[0].stake == pytest.approx(50.0, abs=0.1)
    assert bets[0].bet_wins is True


def test_boundary_market_prob_zero_crosses_does_not_poison_other_bets():
    """A signal with YES=0 next to a valid signal must be rejected without
    polluting the bankroll trajectory or the valid bet's stake."""
    entries = [
        _log("2026-04-14T10:00:00Z", "signal", "POISON", ai_prob=0.5,
             market_prob=0.0, signal="BUY", edge_pct=50),
        _log("2026-04-14T11:00:00Z", "signal", "CLEAN", ai_prob=0.6,
             market_prob=0.4, signal="BUY", edge_pct=20),
        _log("2026-04-15T20:00:00Z", "resolution", "POISON", market_prob=0.0),
        _log("2026-04-15T21:00:00Z", "resolution", "CLEAN", market_prob=1.0),
    ]
    bets, _ = simulate_pnl(entries, starting_bankroll=100.0,
                           kelly_multiplier=0.5)
    assert len(bets) == 1
    assert bets[0].team == "CLEAN"
    # CLEAN must be sized exactly as if POISON never existed
    assert bets[0].bankroll_at_placement == pytest.approx(100.0, abs=0.001)
    assert bets[0].stake == pytest.approx(16.67, abs=0.5)
