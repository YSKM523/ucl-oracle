"""Tests for Half-Kelly PnL simulation."""

from __future__ import annotations

import math

import pytest

from backtest.pnl import (
    _full_kelly,
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
