"""Tests for signal log + CLV pairing / stats."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backtest.clv import (
    clv_summary_stats,
    pair_signals_with_closings,
    per_direction_stats,
    per_strength_stats,
)
from markets.signal_log import (
    LogEntry,
    append_closing,
    append_signal,
    read_all,
)


@pytest.fixture
def tmp_log(tmp_path: Path) -> Path:
    return tmp_path / "signal_log.jsonl"


# ── signal_log ──────────────────────────────────────────────────────────

def test_append_and_read_roundtrip(tmp_log):
    append_signal(
        market_type="winner", team="Arsenal",
        ai_prob=0.43, market_prob=0.255, edge_pct=17.5,
        signal="STRONG BUY", kelly=0.12, event_slug="ucl-winner",
        path=tmp_log,
    )
    append_closing(
        market_type="winner", team="Arsenal",
        market_prob=0.30, event_slug="ucl-winner", path=tmp_log,
    )
    entries = read_all(tmp_log)
    assert len(entries) == 2
    assert entries[0]["source"] == "signal"
    assert entries[1]["source"] == "closing"


def test_append_atomically_works_on_interrupt(tmp_log):
    """Each line is self-contained JSON — partial reads drop nothing earlier."""
    for i in range(3):
        append_signal(
            market_type="winner", team=f"Team{i}",
            ai_prob=0.4, market_prob=0.3, edge_pct=10,
            signal="BUY", kelly=0.05, event_slug="x", path=tmp_log,
        )
    entries = read_all(tmp_log)
    assert len(entries) == 3
    assert [e["team"] for e in entries] == ["Team0", "Team1", "Team2"]


# ── CLV math ────────────────────────────────────────────────────────────

def _mk(source, market_type, team, market_prob, signal=None, ai_prob=None,
        edge_pct=None, ts="2026-04-14T10:00:00Z", season="2025-26", kelly=None):
    return {
        "timestamp_utc": ts, "source": source, "market_type": market_type,
        "team": team, "ai_prob": ai_prob, "market_prob": market_prob,
        "edge_pct": edge_pct, "signal": signal, "kelly": kelly,
        "event_slug": "x", "season": season, "extras": None,
    }


def test_buy_signal_with_favorable_move_gives_positive_clv():
    """BUY at 25%, closing at 30% → market moved our way → CLV = +5pp."""
    entries = [
        _mk("signal", "winner", "Arsenal", 0.25, signal="STRONG BUY",
            ai_prob=0.43, edge_pct=18),
        _mk("closing", "winner", "Arsenal", 0.30, ts="2026-04-14T18:00:00Z"),
    ]
    paired = pair_signals_with_closings(entries)
    assert len(paired) == 1
    assert paired[0].clv_pp == pytest.approx(5.0)


def test_sell_signal_with_favorable_move_gives_positive_clv():
    """SELL at 20%, closing at 15% → market moved our way → CLV = +5pp."""
    entries = [
        _mk("signal", "winner", "Barcelona", 0.20, signal="STRONG SELL",
            ai_prob=0.02, edge_pct=-18),
        _mk("closing", "winner", "Barcelona", 0.15, ts="2026-04-14T18:00:00Z"),
    ]
    paired = pair_signals_with_closings(entries)
    assert paired[0].clv_pp == pytest.approx(5.0)


def test_buy_with_adverse_move_gives_negative_clv():
    """BUY at 25%, closing at 20% → market moved away → CLV = -5pp."""
    entries = [
        _mk("signal", "winner", "PSG", 0.25, signal="BUY", ai_prob=0.30, edge_pct=5),
        _mk("closing", "winner", "PSG", 0.20, ts="2026-04-14T18:00:00Z"),
    ]
    paired = pair_signals_with_closings(entries)
    assert paired[0].clv_pp == pytest.approx(-5.0)


def test_pair_uses_latest_closing_snapshot():
    """Two closings for same team: use the latest timestamp."""
    entries = [
        _mk("signal", "winner", "X", 0.30, signal="BUY", ai_prob=0.40, edge_pct=10,
            ts="2026-04-14T09:00:00Z"),
        _mk("closing", "winner", "X", 0.35, ts="2026-04-14T12:00:00Z"),
        _mk("closing", "winner", "X", 0.40, ts="2026-04-14T18:00:00Z"),
    ]
    paired = pair_signals_with_closings(entries)
    assert len(paired) == 1
    # BUY: CLV = 0.40 - 0.30 = +10pp
    assert paired[0].clv_pp == pytest.approx(10.0)


def test_unpaired_signal_is_skipped():
    entries = [
        _mk("signal", "winner", "X", 0.30, signal="BUY", ai_prob=0.4, edge_pct=10),
        _mk("closing", "winner", "Y", 0.40),  # different team → no pairing
    ]
    paired = pair_signals_with_closings(entries)
    assert len(paired) == 0


def test_signal_without_strength_is_skipped():
    """Only BUY/SELL labelled rows count."""
    entries = [
        _mk("signal", "winner", "X", 0.30, signal=None, ai_prob=0.31, edge_pct=1),
        _mk("closing", "winner", "X", 0.40),
    ]
    assert len(pair_signals_with_closings(entries)) == 0


def test_summary_stats_on_trivial_case():
    entries = [
        _mk("signal", "winner", f"T{i}", 0.30, signal="BUY", ai_prob=0.40, edge_pct=10,
            ts=f"2026-04-14T10:{i:02d}:00Z") for i in range(4)
    ]
    entries += [
        _mk("closing", "winner", f"T{i}", 0.34, ts="2026-04-14T18:00:00Z")
        for i in range(4)
    ]
    paired = pair_signals_with_closings(entries)
    s = clv_summary_stats(paired)
    assert s["n"] == 4
    assert s["mean_clv_pp"] == pytest.approx(4.0)
    assert s["sd_clv_pp"] == pytest.approx(0.0, abs=1e-6)
    assert s["pct_positive"] == 100.0


def test_summary_mixed_gives_reasonable_tstat():
    entries = [
        _mk("signal", "winner", "A", 0.30, signal="BUY", ai_prob=0.4, edge_pct=10,
            ts="2026-04-14T10:00:00Z"),
        _mk("closing", "winner", "A", 0.36, ts="2026-04-14T18:00:00Z"),
        _mk("signal", "winner", "B", 0.30, signal="BUY", ai_prob=0.4, edge_pct=10,
            ts="2026-04-14T10:00:00Z"),
        _mk("closing", "winner", "B", 0.32, ts="2026-04-14T18:00:00Z"),
    ]
    paired = pair_signals_with_closings(entries)
    s = clv_summary_stats(paired)
    # CLVs = [+6, +2]; mean=4, sd≈2.83, se≈2, t≈2
    assert s["n"] == 2
    assert s["mean_clv_pp"] == pytest.approx(4.0)
    assert s["t_stat"] == pytest.approx(2.0, abs=0.1)


def test_per_direction_separates_buy_and_sell():
    entries = [
        _mk("signal", "winner", "A", 0.30, signal="BUY", ai_prob=0.4, edge_pct=10),
        _mk("closing", "winner", "A", 0.40, ts="2026-04-14T18:00:00Z"),
        _mk("signal", "winner", "B", 0.40, signal="STRONG SELL", ai_prob=0.05, edge_pct=-35),
        _mk("closing", "winner", "B", 0.30, ts="2026-04-14T18:00:00Z"),
    ]
    paired = pair_signals_with_closings(entries)
    out = per_direction_stats(paired)
    # BUY: A gained 10pp; SELL: B gained 10pp (40→30 with SELL signal)
    buy_row = out[out["direction"] == "BUY"].iloc[0]
    sell_row = out[out["direction"] == "SELL"].iloc[0]
    assert buy_row["mean_clv_pp"] == pytest.approx(10.0)
    assert sell_row["mean_clv_pp"] == pytest.approx(10.0)
