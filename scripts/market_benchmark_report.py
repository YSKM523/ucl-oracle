"""Generate the model-vs-market Brier / BSS report from the signal log."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.market_benchmark import (  # noqa: E402
    benchmark_stats,
    build_resolved_sample,
    paired_table,
    per_market_breakdown,
)
from config import RESULTS_DIR  # noqa: E402


def _fmt(stats: dict) -> str:
    n = stats.get("n", 0)
    if n == 0:
        return "_No resolved pairs yet._"
    bss = stats.get("brier_skill_score")
    bss_txt = f"{bss:+.3f}" if bss is not None else "n/a"
    lines = [
        f"- **N resolved events:** {n}",
        f"- **Model Brier:** {stats['model_brier']:.4f}",
        f"- **Market Brier:** {stats['market_brier']:.4f}",
        f"- **Brier Skill Score (BSS):** **{bss_txt}**"
        "  _(positive = model beats market)_",
        f"- **Model wins per-event:** {stats.get('model_wins_per_event', 0)} / {n}",
        f"- **Paired t-test** (H1: model Brier < market Brier): "
        f"t = {stats.get('t_stat', 'n/a')}, p = {stats.get('p_one_sided', 'n/a')}",
    ]
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.WARNING)

    rows = build_resolved_sample()
    stats = benchmark_stats(rows)
    per_mkt = per_market_breakdown(rows)
    table = paired_table(rows)

    lines = [
        "# Model vs Market — Brier Benchmark",
        "",
        "The hard skill test: for every resolved event we've predicted, is our",
        "forecast more accurate than the Polymarket closing implied probability?",
        "",
        "**Brier Skill Score** *BSS = 1 − Brier(model) / Brier(market)*.",
        "BSS > 0 means the model beats the market baseline.",
        "",
        "## Headline",
        "",
        _fmt(stats),
        "",
    ]
    if rows:
        lines += [
            "## Per market type",
            "",
            per_mkt.to_markdown(index=False) if not per_mkt.empty else "_none_",
            "",
            "## Paired events",
            "",
            table.to_markdown(index=False) if not table.empty else "_none_",
        ]
    else:
        lines += [
            "To populate this report, you need all three log entries for the same",
            "(market_type, team, season):",
            "",
            "```",
            "python run_predictions.py --fast           # signal row",
            "python scripts/snapshot_closing.py         # closing row",
            "python scripts/record_outcome.py --market qf_advance --team Arsenal --advanced",
            "```",
        ]

    report = "\n".join(lines)
    (RESULTS_DIR / "market_benchmark.md").write_text(report)
    if not table.empty:
        table.to_csv(RESULTS_DIR / "market_benchmark.csv", index=False)
    print(report)


if __name__ == "__main__":
    main()
