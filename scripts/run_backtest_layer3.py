"""Layer 3 backtest entry: Elo + first-leg + optional xG adjustment."""

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
    per_stage,
)
from backtest.runner_layer3 import run_backtest_layer3  # noqa: E402

OUT_DIR = ROOT / "backtest" / "results"


def format_combined_report(df_no_xg: pd.DataFrame, df_with_xg: pd.DataFrame) -> str:
    n = len(df_no_xg)
    base = baseline_metrics(df_no_xg)
    lines = [
        "# 2025-26 UEFA Oracle Backtest — Layer 3 (First-leg conditional + xG adjustment)",
        "",
        f"**Sample**: {n} two-legged ties across seasons "
        f"{df_no_xg['season'].min()} → {df_no_xg['season'].max()}.",
        "",
        "Unlike Layers 1/2 (which simulated both legs from scratch), Layer 3 predicts "
        "only the **remaining 2nd leg** given the known first-leg scoreline — matching "
        "the live pipeline's state between QF legs.",
        "",
        "## Headline",
        "",
        "| Metric | L3b (with xG) | L3a (no xG) | Layer 1 (both legs) | Coin flip |",
        "|--------|---------------|-------------|---------------------|-----------|",
        f"| Hit rate | **{hit_rate(df_with_xg):.1%}** "
        f"({int(df_with_xg['correct'].sum())}/{n}) | "
        f"{hit_rate(df_no_xg):.1%} | — | 50.0% |",
        f"| Brier | **{brier_score(df_with_xg):.3f}** | "
        f"{brier_score(df_no_xg):.3f} | — | 0.250 |",
        f"| Log loss | **{avg_log_loss(df_with_xg):.3f}** | "
        f"{avg_log_loss(df_no_xg):.3f} | — | 0.693 |",
        "",
        f"- L3a p-value (hit rate > 50%): **p = "
        f"{binomial_pvalue(int(df_no_xg['correct'].sum()), n):.4f}**",
        f"- L3b p-value (hit rate > 50%): **p = "
        f"{binomial_pvalue(int(df_with_xg['correct'].sum()), n):.4f}**",
        "",
        "## L3b hit rate by stage",
        "",
        per_stage(df_with_xg).to_markdown(index=False),
        "",
        "## L3b confidence-bucketed hit rate",
        "",
        confidence_bucket_hitrate(df_with_xg).to_markdown(index=False),
        "",
        "## L3b calibration",
        "",
        calibration_bins(df_with_xg, n_bins=5).to_markdown(index=False),
        "",
    ]

    merged = df_no_xg.merge(
        df_with_xg[["season", "stage", "home_team", "away_team",
                    "p_home_advances", "model_pick", "correct", "home_elo", "away_elo"]],
        on=["season", "stage", "home_team", "away_team"],
        suffixes=("_a", "_b"),
    )
    diff_pick = merged[merged["model_pick_a"] != merged["model_pick_b"]]
    lines += [
        "## Where xG adjustment changed the top pick",
        "",
        f"**{len(diff_pick)} of {len(merged)}** ties had a different top pick with xG applied.",
        "",
    ]
    if len(diff_pick) > 0:
        view = diff_pick[[
            "season", "stage", "home_team", "away_team", "actual_winner",
            "p_home_advances_a", "p_home_advances_b",
            "correct_a", "correct_b",
        ]].rename(columns={
            "actual_winner": "actual",
            "p_home_advances_a": "P(no xG)",
            "p_home_advances_b": "P(+xG)",
            "correct_a": "no-xG ✓",
            "correct_b": "+xG ✓",
        })
        lines.append(view.to_markdown(index=False))

    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Layer 3a (baseline: Elo + first-leg, no xG)")
    print("=" * 70)
    df_a = run_backtest_layer3(use_xg=False)

    print("\n" + "=" * 70)
    print("Layer 3b (Elo + first-leg + xG adjustment)")
    print("=" * 70)
    df_b = run_backtest_layer3(use_xg=True)

    df_a.to_csv(OUT_DIR / "layer3a_firstleg_no_xg.csv", index=False)
    df_b.to_csv(OUT_DIR / "layer3b_firstleg_with_xg.csv", index=False)
    report = format_combined_report(df_a, df_b)
    (OUT_DIR / "layer3_firstleg_xg.md").write_text(report)

    print("\n" + "=" * 70)
    print(report)
    print("=" * 70)


if __name__ == "__main__":
    main()
