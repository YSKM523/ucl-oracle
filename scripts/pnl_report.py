"""Forward-test Half-Kelly PnL report from the signal log."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.pnl import (  # noqa: E402
    bets_to_dataframe,
    pnl_summary,
    simulate_pnl,
)
from config import RESULTS_DIR  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bankroll", type=float, default=100.0,
                    help="Starting bankroll in abstract units (default 100)")
    ap.add_argument("--kelly", type=float, default=0.5,
                    help="Kelly multiplier (default 0.5 = Half-Kelly)")
    ap.add_argument("--min-edge", type=float, default=3.0,
                    help="Minimum |edge_pct| to place a bet (default 3.0)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.WARNING)

    bets, traj = simulate_pnl(
        starting_bankroll=args.bankroll,
        kelly_multiplier=args.kelly,
        min_edge_pct=args.min_edge,
    )
    summary = pnl_summary(bets, starting_bankroll=args.bankroll)

    lines = [
        "# Half-Kelly PnL — Forward Test",
        "",
        f"**Starting bankroll:** {args.bankroll}  |  "
        f"**Kelly multiplier:** {args.kelly}  |  "
        f"**Min |edge|:** {args.min_edge}%",
        "",
        "## Headline",
        "",
        f"- **Bets placed:** {summary['n_bets']}",
        f"- **Total staked (sum of position sizes):** {summary['total_staked']}",
        f"- **Final bankroll:** {summary['final_bankroll']}",
        f"- **Total PnL:** {summary['total_pnl']}",
        f"- **ROI on bankroll:** {summary['roi_pct']}%",
        f"- **Return on turnover:** {summary.get('return_on_turnover_pct', 0.0)}%",
        f"- **Max drawdown:** {summary['max_drawdown_pct']}%",
        f"- **Per-bet Sharpe** (risk-free = 0): {summary['per_bet_sharpe']}",
        f"- **Win rate (direction-aware):** {summary['win_rate_pct']}%",
        "",
    ]

    if summary["n_bets"] == 0:
        lines += [
            "## No resolved bets yet",
            "",
            "Populate the signal log with all three entry types for at least a",
            "few teams:",
            "",
            "```",
            "python run_predictions.py                        # 'signal' rows",
            "python scripts/snapshot_closing.py               # 'closing' rows",
            "python scripts/record_outcome.py --market qf_advance \\",
            "    --team Arsenal --advanced                    # 'resolution' row",
            "",
            "python scripts/pnl_report.py                     # re-run this",
            "```",
        ]
    else:
        df = bets_to_dataframe(bets)
        lines += [
            "## Every bet (ordered by settlement time)",
            "",
            df[[
                "ts_signal", "ts_resolution", "market_type", "team", "direction",
                "entry_prob", "ai_prob", "kelly_fraction", "stake", "decimal_odds",
                "outcome", "bet_wins", "pnl", "bankroll_at_placement",
                "bankroll_after",
            ]].to_markdown(index=False),
            "",
            "## Bankroll trajectory",
            "",
            traj.to_markdown(index=False),
        ]

    report = "\n".join(lines)
    (RESULTS_DIR / "pnl_report.md").write_text(report)
    if summary["n_bets"] > 0:
        bets_to_dataframe(bets).to_csv(RESULTS_DIR / "pnl_report.csv", index=False)
    print(report)


if __name__ == "__main__":
    main()
