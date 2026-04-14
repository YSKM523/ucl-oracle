"""Record the actual outcome of a market after it resolves.

Usage
-----
    # Team advanced to SFs:
    python scripts/record_outcome.py --market qf_advance --team "Arsenal" --advanced

    # Team did NOT advance:
    python scripts/record_outcome.py --market qf_advance --team "Barcelona" --no

    # Winner market settles only once at tournament end:
    python scripts/record_outcome.py --market winner --team "Arsenal" --yes

Each call appends one ``source="resolution"`` row to
``results/signal_log.jsonl``. The market-benchmark Brier comparison
pairs each resolution with the latest signal + closing for the same key.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from markets.signal_log import append_resolution  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", required=True,
                    choices=["winner", "qf_advance"])
    ap.add_argument("--team", required=True)
    out = ap.add_mutually_exclusive_group(required=True)
    out.add_argument("--advanced", "--yes", dest="outcome",
                     action="store_const", const=True)
    out.add_argument("--eliminated", "--no", dest="outcome",
                     action="store_const", const=False)
    ap.add_argument("--season", default="2025-26")
    ap.add_argument("--event-slug", default="auto")
    args = ap.parse_args()

    entry = append_resolution(
        market_type=args.market,
        team=args.team,
        outcome=args.outcome,
        event_slug=args.event_slug,
        season=args.season,
    )
    verb = "advanced / won" if args.outcome else "eliminated / lost"
    print(f"▸ {args.market}/{args.team}: recorded as '{verb}' at {entry.timestamp_utc}")


if __name__ == "__main__":
    main()
