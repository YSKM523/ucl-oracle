"""Generate all UCL Oracle visualizations."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import RESULTS_DIR, PLOTS_DIR
from data.fetcher_clubelo import fetch_current_elos, fetch_all_histories
from data.fetcher_polymarket import fetch_all_ucl_odds
from data.elo import build_all_weekly_series
from prediction.knockout_simulator import run_monte_carlo
from prediction.strength_forecaster import forecast_all_teams
from markets.edge_detector import detect_edges
from visualization.bracket_viz import plot_bracket, plot_probability_bars
from visualization.odds_comparison import plot_scatter, plot_side_by_side, plot_edge_bars
from visualization.team_form import plot_team_elo_trajectories, plot_team_forecast


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")

    print("Generating UCL Oracle plots …\n")

    # Load data
    elos = fetch_current_elos()
    histories = fetch_all_histories()
    weekly_series = build_all_weekly_series(histories)

    # Run Monte Carlo
    results_df = run_monte_carlo(elos, n_simulations=50_000)

    # Run TSFM forecasts
    print("\nRunning TSFM forecasts …")
    forecasts = forecast_all_teams(weekly_series)

    # Fetch Polymarket
    odds = fetch_all_ucl_odds()

    # ── Generate plots ──────────────────────────────────────────────────
    print("\n--- Generating plots ---")

    # 1. Bracket
    plot_bracket(results_df)

    # 2. Champion probability bars
    plot_probability_bars(results_df)

    # 3. Elo trajectories
    plot_team_elo_trajectories(weekly_series)

    # 4. Per-team TSFM forecast fan charts
    for team in weekly_series:
        team_forecasts = {mn: forecasts[mn][team] for mn in forecasts}
        plot_team_forecast(team, weekly_series[team], team_forecasts)

    # 5. AI vs Polymarket scatter/bars
    champion_probs = dict(zip(results_df["team"], results_df["P(champion)"]))
    qf_advance_probs = dict(zip(results_df["team"], results_df["P(qf_advance)"]))

    winner_df = odds.get("winner")
    if winner_df is not None and not winner_df.empty:
        winner_market = dict(zip(winner_df["team"], winner_df["implied_prob"]))
        plot_scatter(champion_probs, winner_market, "AI vs Polymarket — UCL Winner")
        plot_side_by_side(champion_probs, winner_market, "AI vs Polymarket — UCL Winner")

        edges = detect_edges(champion_probs, winner_market)
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

        adv_edges = detect_edges(qf_advance_probs, semis_market)
        if not adv_edges.empty:
            plot_edge_bars(adv_edges, "QF Advancement — Edge Detection",
                          PLOTS_DIR / "qf_advance_edges.png")

    print(f"\nAll plots saved to {PLOTS_DIR}/")


if __name__ == "__main__":
    main()
