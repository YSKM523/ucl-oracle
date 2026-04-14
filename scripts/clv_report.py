"""Generate a Closing Line Value (CLV) report from the signal log.

Reads ``results/signal_log.jsonl``, pairs each signal with the latest
closing snapshot for the same (market_type, team, season), and prints:

  - Headline mean CLV + one-sided t-test against 0
  - Per-direction (BUY vs SELL) breakdown
  - Per-strength (STRONG BUY / BUY / SELL / STRONG SELL) breakdown
  - Per-signal table sorted by CLV

Writes the full paired table to ``results/clv_report.csv`` and the markdown
summary to ``results/clv_report.md`` for quoting in README / IG posts.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.clv import load_and_analyze  # noqa: E402
from config import RESULTS_DIR  # noqa: E402


def _fmt_summary(s: dict) -> str:
    n = s["n"]
    if n == 0:
        return "No paired signals yet."
    lines = [
        f"- **N paired signals:** {n}",
        f"- **Mean CLV:** {s['mean_clv_pp']:+.2f} pp",
        f"- **SD:** {s['sd_clv_pp']:.2f} pp  |  SE: {s['se_clv_pp']:.2f} pp",
        f"- **% positive:** {s['pct_positive']}%",
    ]
    if s.get("t_stat") is not None:
        lines.append(
            f"- **One-sided t-test (mean CLV > 0):** t={s['t_stat']:.2f}, "
            f"p={s['p_value_one_sided']:.4f}"
        )
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    out = load_and_analyze()
    summary = out["summary"]
    df = out["per_signal_df"]

    lines = [
        "# CLV (Closing Line Value) Report",
        "",
        "Closing Line Value measures, for each signal, whether the market moved",
        "our way between the time we predicted and the final closing price.",
        "Under an efficient market CLV is mean-zero noise; a consistent positive",
        "mean CLV is the industry-standard evidence of genuine edge.",
        "",
        "## Headline",
        "",
        _fmt_summary(summary),
        "",
    ]
    if summary["n"] == 0:
        lines += [
            "No signals have been paired with closings yet. Workflow:",
            "",
            "```",
            "# Any time predictions run, signals append to results/signal_log.jsonl:",
            "python run_predictions.py --fast",
            "",
            "# ≤10 min before kickoff, snap the closing line:",
            "python scripts/snapshot_closing.py",
            "",
            "# After 15-30 signals accumulate, re-run this report:",
            "python scripts/clv_report.py",
            "```",
        ]
    else:
        lines += [
            "## By direction",
            "",
            out["per_direction"].to_markdown(index=False) if not out["per_direction"].empty else "_none_",
            "",
            "## By signal strength",
            "",
            out["per_strength"].to_markdown(index=False) if not out["per_strength"].empty else "_none_",
            "",
            "## Paired signals",
            "",
            df.to_markdown(index=False) if not df.empty else "_none_",
        ]

    report = "\n".join(lines)
    (RESULTS_DIR / "clv_report.md").write_text(report)
    if not df.empty:
        df.to_csv(RESULTS_DIR / "clv_report.csv", index=False)

    print(report)
    print(f"\nSaved to {RESULTS_DIR / 'clv_report.md'}")


if __name__ == "__main__":
    main()
