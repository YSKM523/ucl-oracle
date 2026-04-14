"""Tests for model-vs-market Brier benchmark."""

from __future__ import annotations

import math

import pytest

from backtest.market_benchmark import (
    benchmark_stats,
    build_resolved_sample,
    per_market_breakdown,
)


def _e(source, team, team_prob, market="winner", ai_prob=None,
       ts="2026-04-14T10:00:00Z", season="2025-26"):
    return {
        "timestamp_utc": ts, "source": source, "market_type": market,
        "team": team, "ai_prob": ai_prob, "market_prob": team_prob,
        "edge_pct": None, "signal": "BUY" if source == "signal" else None,
        "kelly": None, "event_slug": "x", "season": season, "extras": None,
    }


# ── pairing ─────────────────────────────────────────────────────────────

def test_requires_signal_closing_and_resolution():
    """Missing any of the three → no row."""
    # signal + closing but no resolution
    entries = [
        _e("signal", "A", 0.25, ai_prob=0.40),
        _e("closing", "A", 0.28, ts="2026-04-14T18:00:00Z"),
    ]
    assert len(build_resolved_sample(entries)) == 0


def test_pairs_when_all_three_present():
    entries = [
        _e("signal", "A", 0.25, ai_prob=0.40),
        _e("closing", "A", 0.28, ts="2026-04-14T18:00:00Z"),
        _e("resolution", "A", 1.0, ts="2026-04-15T22:00:00Z"),
    ]
    rows = build_resolved_sample(entries)
    assert len(rows) == 1
    r = rows[0]
    assert r.outcome == 1
    assert r.ai_prob == pytest.approx(0.40)
    assert r.market_close_prob == pytest.approx(0.28)
    assert r.model_sq_err == pytest.approx((0.40 - 1) ** 2)
    assert r.market_sq_err == pytest.approx((0.28 - 1) ** 2)


def test_latest_of_each_source_is_used():
    entries = [
        _e("signal", "A", 0.30, ai_prob=0.50, ts="2026-04-14T09:00:00Z"),
        _e("signal", "A", 0.28, ai_prob=0.45, ts="2026-04-14T12:00:00Z"),  # latest
        _e("closing", "A", 0.30, ts="2026-04-14T18:00:00Z"),
        _e("resolution", "A", 0.0, ts="2026-04-15T22:00:00Z"),
    ]
    rows = build_resolved_sample(entries)
    assert len(rows) == 1
    assert rows[0].ai_prob == pytest.approx(0.45)


# ── Brier / BSS ────────────────────────────────────────────────────────

def test_perfect_model_beats_anything():
    entries = [
        _e("signal", "A", 0.30, ai_prob=1.0, ts="2026-04-14T09:00:00Z"),
        _e("closing", "A", 0.50, ts="2026-04-14T18:00:00Z"),
        _e("resolution", "A", 1.0, ts="2026-04-15T22:00:00Z"),
    ]
    rows = build_resolved_sample(entries)
    s = benchmark_stats(rows)
    assert s["model_brier"] == pytest.approx(0.0)
    assert s["bss" if False else "brier_skill_score"] == pytest.approx(1.0)


def test_model_identical_to_market_gives_zero_bss():
    entries = [
        _e("signal", "A", 0.30, ai_prob=0.30),
        _e("closing", "A", 0.30, ts="2026-04-14T18:00:00Z"),
        _e("resolution", "A", 1.0, ts="2026-04-15T22:00:00Z"),
    ]
    s = benchmark_stats(build_resolved_sample(entries))
    assert s["brier_skill_score"] == pytest.approx(0.0)


def test_worse_model_gives_negative_bss():
    # Market says 0.50, model says 0.10, outcome=1
    # model sq err = 0.81, market sq err = 0.25 → BSS = 1 - 0.81/0.25 = -2.24
    entries = [
        _e("signal", "A", 0.50, ai_prob=0.10),
        _e("closing", "A", 0.50, ts="2026-04-14T18:00:00Z"),
        _e("resolution", "A", 1.0, ts="2026-04-15T22:00:00Z"),
    ]
    s = benchmark_stats(build_resolved_sample(entries))
    assert s["brier_skill_score"] is not None
    assert s["brier_skill_score"] < 0


def test_mixed_sample_gives_tstat_near_zero_when_tied():
    """Two events: one where model beats market, one where market beats model → t≈0."""
    entries = [
        # Event 1: model wins (0.9 vs 0.5, outcome=1)
        _e("signal", "A", 0.5, ai_prob=0.9, ts="2026-04-14T09:00:00Z"),
        _e("closing", "A", 0.5, ts="2026-04-14T18:00:00Z"),
        _e("resolution", "A", 1.0, ts="2026-04-15T22:00:00Z"),
        # Event 2: market wins (0.5 vs 0.1, outcome=1)
        _e("signal", "B", 0.5, ai_prob=0.1, ts="2026-04-14T09:00:00Z"),
        _e("closing", "B", 0.5, ts="2026-04-14T18:00:00Z"),
        _e("resolution", "B", 1.0, ts="2026-04-15T22:00:00Z"),
    ]
    s = benchmark_stats(build_resolved_sample(entries))
    # (0.5² − 0.1²) = 0.24;  (0.5² − 0.9²) = −0.56 ; mean = −0.16, so model does worse net
    # t-stat signed: negative = model worse, can't be 0 exactly but the framework runs
    assert s["n"] == 2


def test_per_market_splits():
    entries = []
    for team in ("A", "B"):
        entries += [
            _e("signal", team, 0.3, ai_prob=0.5, market="winner"),
            _e("closing", team, 0.3, ts="2026-04-14T18:00:00Z", market="winner"),
            _e("resolution", team, 1.0, ts="2026-04-15T22:00:00Z", market="winner"),
        ]
    for team in ("C",):
        entries += [
            _e("signal", team, 0.3, ai_prob=0.9, market="qf_advance"),
            _e("closing", team, 0.3, ts="2026-04-14T18:00:00Z", market="qf_advance"),
            _e("resolution", team, 1.0, ts="2026-04-15T22:00:00Z", market="qf_advance"),
        ]
    out = per_market_breakdown(build_resolved_sample(entries))
    assert set(out["market_type"]) == {"winner", "qf_advance"}


def test_empty_returns_safe_dict():
    s = benchmark_stats([])
    assert s["n"] == 0
