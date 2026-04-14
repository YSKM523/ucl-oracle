"""Capture a closing-line snapshot of Polymarket before match kickoff.

Run this within ~10 minutes of the earliest QF / SF / Final kickoff on a
match day. It reads ``results/signal_log.jsonl``, identifies every
(market_type, team, season) where we have logged a signal, fetches the
current Polymarket price, and appends a ``source="closing"`` row for each.

The closest ``source="closing"`` row per (market_type, team, season) is
later used by ``backtest.clv`` to compute Closing Line Value.

Usage
-----
    python scripts/snapshot_closing.py
    python scripts/snapshot_closing.py --only winner
    python scripts/snapshot_closing.py --label "QF2 legs"   # stored in extras
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.fetcher_polymarket import fetch_all_ucl_odds  # noqa: E402
from markets.signal_log import append_closing, filter_entries, read_all  # noqa: E402

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    parser = argparse.ArgumentParser(description="Snapshot Polymarket as closing line")
    parser.add_argument("--only", choices=["winner", "qf_advance"], default=None,
                        help="Only snapshot this market type")
    parser.add_argument("--label", default=None,
                        help="Free-form tag stored in extras (e.g. 'QF2 legs')")
    args = parser.parse_args()

    entries = read_all()
    existing_signals = filter_entries(entries, source="signal")
    if not existing_signals:
        print("No signals in log yet. Run `python run_predictions.py` first.")
        return

    # Unique (market_type, team, season) triples we've signalled
    to_snapshot = {
        (e["market_type"], e["team"], e["season"])
        for e in existing_signals
    }
    if args.only:
        to_snapshot = {t for t in to_snapshot if t[0] == args.only}

    print(f"Snapshotting closing prices for {len(to_snapshot)} logged teams …")

    # Fetch current odds once; price map per market type
    odds = fetch_all_ucl_odds()
    price_maps = {}
    if odds.get("winner") is not None and not odds["winner"].empty:
        price_maps["winner"] = dict(zip(odds["winner"]["team"], odds["winner"]["implied_prob"]))
    if odds.get("semis") is not None and not odds["semis"].empty:
        price_maps["qf_advance"] = dict(zip(odds["semis"]["team"], odds["semis"]["implied_prob"]))

    appended = 0
    missing = 0
    for market_type, team, season in sorted(to_snapshot):
        price = price_maps.get(market_type, {}).get(team)
        if price is None:
            print(f"  ⚠  {market_type}/{team}: market no longer listed, skipping")
            missing += 1
            continue
        extras = {"label": args.label} if args.label else None
        append_closing(
            market_type=market_type,
            team=team,
            market_prob=float(price),
            event_slug="auto",       # not used for CLV pairing
            season=season,
            extras=extras,
        )
        appended += 1
        print(f"  ▸ {market_type}/{team}: {price:.1%} closing")

    print(f"\nDone. {appended} closings appended, {missing} missing.")
    print("Run `python scripts/clv_report.py` to see CLV stats.")


if __name__ == "__main__":
    main()
