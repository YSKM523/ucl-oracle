"""Run the 2025-26 UEFA Oracle backtest on 5 historical seasons (2020-21 to 2024-25).

Only uses clubelo.com Elo snapshots at each tie's first-leg date — i.e. the
pure Layer 1 baseline (no TSFM, no xG, no injuries). This establishes the
'how well does Elo alone do?' benchmark before layering signals on top.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.metrics import (  # noqa: E402
    avg_log_loss,
    baseline_metrics,
    binomial_pvalue,
    brier_score,
    calibration_bins,
    confidence_bucket_hitrate,
    hit_rate,
    per_season,
    per_stage,
)
from backtest.runner import run_backtest  # noqa: E402

OUT_DIR = ROOT / "backtest" / "results"


def format_report(df: pd.DataFrame) -> str:
    n = len(df)
    n_correct = int(df["correct"].sum())
    base = baseline_metrics(df)
    pval = binomial_pvalue(n_correct, n, baseline=0.5)

    lines = [
        "# 2025-26 UEFA Oracle Backtest — Layer 1 (Elo baseline)",
        "",
        f"**Sample**: {n} knockout ties across seasons "
        f"{df['season'].min()} → {df['season'].max()}",
        "",
        "## Headline",
        "",
        f"| Metric | Model | Coin-flip baseline |",
        f"|--------|-------|--------------------|",
        f"| Hit rate | **{hit_rate(df):.1%}** "
        f"({n_correct}/{n}) | {base['hit_rate']:.1%} |",
        f"| Brier score | **{brier_score(df):.3f}** | {base['brier']:.3f} |",
        f"| Log loss   | **{avg_log_loss(df):.3f}** | {base['log_loss']:.3f} |",
        "",
        f"One-sided binomial p-value (hit rate > 50%): **p = {pval:.4f}**",
        "",
        "## Hit rate by stage",
        "",
        per_stage(df).to_markdown(index=False),
        "",
        "## Hit rate by season",
        "",
        per_season(df).to_markdown(index=False),
        "",
        "## Confidence-bucketed hit rate",
        "",
        "*Does the model get it right more often when it's confident?*",
        "",
        confidence_bucket_hitrate(df).to_markdown(index=False),
        "",
        "## Calibration (predicted P(home advances) vs actual)",
        "",
        "*A well-calibrated model's predicted bucket and actual rate should match.*",
        "",
        calibration_bins(df, n_bins=5).to_markdown(index=False),
        "",
        "## Interpretation",
        "",
        "- **Hit rate > 60%** → Elo has real signal (50% is coin flip; top-pick home advantage isn't a free 60%)",
        "- **Brier < 0.22** → substantially better calibrated than coin flip",
        "- **p < 0.05** → statistically unlikely to be chance",
        "- **Confidence buckets**: if 'high confidence (≥75%)' isn't >80% hit rate, model is overconfident",
    ]
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Running backtest over all fixture seasons …\n")
    df = run_backtest()

    df.to_csv(OUT_DIR / "layer1_elo_baseline.csv", index=False)
    report = format_report(df)
    (OUT_DIR / "layer1_elo_baseline.md").write_text(report)

    print("\n" + "=" * 72)
    print(report)
    print("=" * 72)
    print(f"\nCSV:    {OUT_DIR / 'layer1_elo_baseline.csv'}")
    print(f"Report: {OUT_DIR / 'layer1_elo_baseline.md'}")


if __name__ == "__main__":
    main()
