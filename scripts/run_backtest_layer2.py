"""Layer 2 backtest entry: Elo + TSFM ensemble across 5 historical seasons."""

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
from backtest.runner_layer2 import run_backtest_layer2  # noqa: E402

OUT_DIR = ROOT / "backtest" / "results"


def format_report(df: pd.DataFrame, layer1_df: pd.DataFrame | None = None) -> str:
    n = len(df)
    n_correct = int(df["correct"].sum())
    base = baseline_metrics(df)
    pval = binomial_pvalue(n_correct, n, baseline=0.5)

    lines = [
        "# 2025-26 UEFA Oracle Backtest — Layer 2 (Elo + TSFM Ensemble)",
        "",
        f"**Sample**: {n} knockout ties across seasons "
        f"{df['season'].min()} → {df['season'].max()}",
        "",
        "## Headline",
        "",
        "| Metric | Layer 2 | Layer 1 (Elo only) | Coin flip |",
        "|--------|---------|--------------------|-----------|",
    ]
    if layer1_df is not None and not layer1_df.empty:
        lines.extend([
            f"| Hit rate | **{hit_rate(df):.1%}** ({n_correct}/{n}) | "
            f"{hit_rate(layer1_df):.1%} | 50.0% |",
            f"| Brier score | **{brier_score(df):.3f}** | "
            f"{brier_score(layer1_df):.3f} | 0.250 |",
            f"| Log loss | **{avg_log_loss(df):.3f}** | "
            f"{avg_log_loss(layer1_df):.3f} | 0.693 |",
        ])
    else:
        lines.extend([
            f"| Hit rate | **{hit_rate(df):.1%}** ({n_correct}/{n}) | — | 50.0% |",
            f"| Brier score | **{brier_score(df):.3f}** | — | 0.250 |",
            f"| Log loss | **{avg_log_loss(df):.3f}** | — | 0.693 |",
        ])

    lines += [
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
        confidence_bucket_hitrate(df).to_markdown(index=False),
        "",
        "## Calibration (predicted P(home advances) vs actual)",
        "",
        calibration_bins(df, n_bins=5).to_markdown(index=False),
    ]

    if layer1_df is not None:
        # Per-tie comparison: ties where Layer 2 differed from Layer 1 in pick
        merged = df.merge(
            layer1_df[["season", "stage", "home_team", "away_team",
                        "model_pick", "correct", "p_home_advances"]],
            on=["season", "stage", "home_team", "away_team"],
            suffixes=("_l2", "_l1"),
        )
        diff_pick = merged[merged["model_pick_l1"] != merged["model_pick_l2"]]
        lines += [
            "",
            "## Where Layer 2 differs from Layer 1",
            "",
            f"{len(diff_pick)} ties out of {len(merged)} had a different top pick.",
            "",
        ]
        if len(diff_pick) > 0:
            view = diff_pick[[
                "season", "stage", "home_team", "away_team", "actual_winner",
                "p_home_advances_l1", "p_home_advances_l2",
                "correct_l1", "correct_l2",
            ]].rename(columns={
                "actual_winner": "actual",
                "p_home_advances_l1": "P(L1)",
                "p_home_advances_l2": "P(L2)",
                "correct_l1": "L1 ✓",
                "correct_l2": "L2 ✓",
            })
            lines.append(view.to_markdown(index=False))

    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Running Layer 2 backtest (Elo + TSFM ensemble) …\n")
    df = run_backtest_layer2()

    layer1_path = OUT_DIR / "layer1_elo_baseline.csv"
    layer1_df = pd.read_csv(layer1_path) if layer1_path.exists() else None

    df.to_csv(OUT_DIR / "layer2_tsfm_ensemble.csv", index=False)
    report = format_report(df, layer1_df=layer1_df)
    (OUT_DIR / "layer2_tsfm_ensemble.md").write_text(report)

    print("\n" + "=" * 72)
    print(report)
    print("=" * 72)


if __name__ == "__main__":
    main()
