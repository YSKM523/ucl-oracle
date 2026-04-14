"""Append-only signal log for CLV (Closing Line Value) tracking.

Each time the model emits an edge signal OR we capture a closing-line snapshot,
we append one JSON line to ``results/signal_log.jsonl``. This append-only
format is safe under interrupts and trivial to replay for analysis.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

from config import RESULTS_DIR

LOG_PATH = RESULTS_DIR / "signal_log.jsonl"

Source = Literal["signal", "closing", "resolution"]


@dataclass
class LogEntry:
    """One signal or closing-line row.

    For CLV math we pair a ``source="signal"`` row with the latest
    ``source="closing"`` row that shares (market_type, team, event_date).
    """
    timestamp_utc: str
    source: Source
    market_type: str        # 'winner' or 'qf_advance' or later stages
    team: str
    ai_prob: float | None   # null for closing-line-only entries
    market_prob: float
    edge_pct: float | None  # null for closing-line-only entries
    signal: str | None      # 'STRONG BUY' / 'BUY' / 'SELL' / 'STRONG SELL' / None
    kelly: float | None
    event_slug: str
    season: str = "2025-26"
    # free-form extras — kept on the entry so analysis can re-slice
    extras: dict | None = None


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_entry(entry: LogEntry, path: Path = LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")


def append_signal(
    market_type: str,
    team: str,
    ai_prob: float,
    market_prob: float,
    edge_pct: float,
    signal: str,
    kelly: float | None,
    event_slug: str,
    season: str = "2025-26",
    extras: dict | None = None,
    timestamp_utc: str | None = None,
    path: Path = LOG_PATH,
) -> LogEntry:
    entry = LogEntry(
        timestamp_utc=timestamp_utc or _now_utc(),
        source="signal",
        market_type=market_type,
        team=team,
        ai_prob=float(ai_prob),
        market_prob=float(market_prob),
        edge_pct=float(edge_pct),
        signal=signal,
        kelly=float(kelly) if kelly is not None else None,
        event_slug=event_slug,
        season=season,
        extras=extras,
    )
    append_entry(entry, path)
    return entry


def append_resolution(
    market_type: str,
    team: str,
    outcome: bool,
    event_slug: str,
    season: str = "2025-26",
    extras: dict | None = None,
    timestamp_utc: str | None = None,
    path: Path = LOG_PATH,
) -> "LogEntry":
    """Record whether this (market, team) actually resolved true (advanced / won).

    ``outcome=True`` → the event we were betting on happened (team advanced /
    won the tournament). ``market_prob`` is set to ``1.0`` for a resolved
    positive outcome and ``0.0`` for a resolved negative outcome so existing
    pairing code can re-use the same field.
    """
    entry = LogEntry(
        timestamp_utc=timestamp_utc or _now_utc(),
        source="resolution",
        market_type=market_type,
        team=team,
        ai_prob=None,
        market_prob=1.0 if outcome else 0.0,
        edge_pct=None,
        signal=None,
        kelly=None,
        event_slug=event_slug,
        season=season,
        extras=extras,
    )
    append_entry(entry, path)
    return entry


def append_closing(
    market_type: str,
    team: str,
    market_prob: float,
    event_slug: str,
    season: str = "2025-26",
    extras: dict | None = None,
    timestamp_utc: str | None = None,
    path: Path = LOG_PATH,
) -> LogEntry:
    entry = LogEntry(
        timestamp_utc=timestamp_utc or _now_utc(),
        source="closing",
        market_type=market_type,
        team=team,
        ai_prob=None,
        market_prob=float(market_prob),
        edge_pct=None,
        signal=None,
        kelly=None,
        event_slug=event_slug,
        season=season,
        extras=extras,
    )
    append_entry(entry, path)
    return entry


def read_all(path: Path = LOG_PATH) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def filter_entries(
    entries: Iterable[dict],
    source: Source | None = None,
    market_type: str | None = None,
    team: str | None = None,
    season: str | None = None,
) -> list[dict]:
    out = []
    for e in entries:
        if source is not None and e.get("source") != source:
            continue
        if market_type is not None and e.get("market_type") != market_type:
            continue
        if team is not None and e.get("team") != team:
            continue
        if season is not None and e.get("season") != season:
            continue
        out.append(e)
    return out
