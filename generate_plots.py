"""Generate all 2025-26 UEFA Oracle visualizations.

By default, uses the production Elo-stack (Elo + xG adjustment + injuries).
Pass ``--with-tsfm`` to additionally run the 3-model TSFM ensemble for the
ablation-variant plots (champion forecast fan charts are only available in
this mode, since they need TSFM forecasts).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import PLOTS_DIR
from data.fetcher_clubelo import fetch_all_histories
from data.fetcher_polymarket import fetch_all_ucl_odds
from data.elo import build_all_weekly_series
from markets.edge_detector import detect_edges
from run_predictions import run_elo_baseline, run_tsfm_predictions
from visualization.bracket_viz import plot_bracket, plot_probability_bars
from visualization.odds_comparison import plot_scatter, plot_side_by_side, plot_edge_bars
from visualization.team_form import plot_team_elo_trajectories, plot_team_forecast


def main():
    parser = argparse.ArgumentParser(description="Generate 2025-26 UEFA Oracle plots")
    parser.add_argument(
        "--with-tsfm",
        action="store_true",
        help="Also run the 3-model TSFM ensemble and render its forecast "
             "fan charts. Slow (~5-7 min extra). Default uses Elo-stack only.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")

    print("Generating 2025-26 UEFA Oracle plots …\n")

    if args.with_tsfm:
        # Full TSFM ablation run
        ensemble_df, champion_probs, model_champ, model_tourn = run_tsfm_predictions()
        histories = fetch_all_histories()
        weekly_series = build_all_weekly_series(histories)
        # Lazy import — TSFM models only needed in this branch
        from prediction.strength_forecaster import forecast_all_teams
        forecasts = forecast_all_teams(weekly_series)
        predictions_df = ensemble_df
        per_model_champ = model_champ
        per_model_tourn = model_tourn
    else:
        # Default: production Elo-stack
        predictions_df, champion_probs = run_elo_baseline()
        histories = fetch_all_histories()
        weekly_series = build_all_weekly_series(histories)
        forecasts = None
        per_model_champ = None
        per_model_tourn = None

    odds = fetch_all_ucl_odds()

    print("\n--- Generating plots ---")

    # 1. Bracket
    plot_bracket(
        predictions_df,
        subtitle="TSFM Ensemble + Elo" if args.with_tsfm else
                 "Elo + first-leg xG + injury-weighted Elo",
    )

    # 2. Champion probability bars
    plot_probability_bars(
        predictions_df,
        subtitle="TSFM Ensemble" if args.with_tsfm else "Elo-stack",
    )

    # 3. Elo trajectories (always useful, no TSFM needed)
    plot_team_elo_trajectories(weekly_series)

    # 4. Per-team TSFM forecast fan charts — only meaningful with TSFM
    if args.with_tsfm and forecasts is not None:
        for team in weekly_series:
            team_forecasts = {mn: forecasts[mn][team] for mn in forecasts}
            plot_team_forecast(team, weekly_series[team], team_forecasts)

    # 5. AI vs Polymarket scatter/bars
    qf_advance_probs = dict(zip(predictions_df["team"], predictions_df["P(qf_advance)"]))

    winner_df = odds.get("winner")
    if winner_df is not None and not winner_df.empty:
        winner_market = dict(zip(winner_df["team"], winner_df["implied_prob"]))
        plot_scatter(champion_probs, winner_market, "AI vs Polymarket — UCL Winner")
        plot_side_by_side(champion_probs, winner_market, "AI vs Polymarket — UCL Winner")

        edges = detect_edges(champion_probs, winner_market, model_probs=per_model_champ)
        if not edges.empty:
            plot_edge_bars(edges, "UCL Winner — Edge Detection",
                           PLOTS_DIR / "winner_edges.png")

    semis_df = odds.get("semis")
    if semis_df is not None and not semis_df.empty:
        semis_market = dict(zip(semis_df["team"], semis_df["implied_prob"]))
        plot_scatter(qf_advance_probs, semis_market,
                     "AI vs Polymarket — QF Advancement",
                     PLOTS_DIR / "ai_vs_polymarket_qf_scatter.png")
        plot_side_by_side(qf_advance_probs, semis_market,
                          "AI vs Polymarket — QF Advancement",
                          PLOTS_DIR / "ai_vs_polymarket_qf_bars.png")

        if per_model_tourn is not None:
            model_qf_probs = {
                mn: {t: per_model_tourn[mn][t]["qf_advance"] for t in per_model_tourn[mn]}
                for mn in per_model_tourn
            }
        else:
            model_qf_probs = None
        adv_edges = detect_edges(qf_advance_probs, semis_market, model_probs=model_qf_probs)
        if not adv_edges.empty:
            plot_edge_bars(adv_edges, "QF Advancement — Edge Detection",
                           PLOTS_DIR / "qf_advance_edges.png")

    print(f"\nAll plots saved to {PLOTS_DIR}/")


if __name__ == "__main__":
    main()
