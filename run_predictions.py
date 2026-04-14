"""Main orchestrator for 2025-26 UEFA Oracle predictions."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    FIRST_LEG_ADJUSTMENT_ENABLED,
    FIRST_LEG_RESULTS,
    FIRST_LEG_XG,
    INJURY_ADJUSTMENT_ENABLED,
    MONTE_CARLO_SIMULATIONS,
    RESULTS_DIR,
    UCL_TEAMS,
    UCL_WINNER_EVENT_SLUG,
    UCL_SEMIS_EVENT_SLUG,
)
from data.fetcher_clubelo import fetch_current_elos
from data.fetcher_injuries import fetch_all_injuries
from data.fetcher_xg import fetch_first_leg_xg
from markets.edge_detector import detect_edges, format_edge_report, kelly_fraction
from markets.signal_log import append_signal
from prediction.elo_adjuster import (
    adjust_elos_for_first_legs,
    apply_injury_penalties,
    compute_injury_penalties,
    format_adjustments_report,
    format_injury_report,
)
from prediction.knockout_simulator import run_monte_carlo

log = logging.getLogger(__name__)


def _log_edges(edges_df: pd.DataFrame, market_type: str, event_slug: str) -> None:
    """Append every actionable edge row to the CLV signal log."""
    logged = 0
    for _, row in edges_df.iterrows():
        signal = row.get("strength") or ""
        # detect_edges stores a coarse "edge"/"STRONG EDGE" tag; recover the
        # direction + strength the user sees in the tables
        direction = row.get("direction")
        if not direction:
            continue
        if signal == "STRONG EDGE":
            label = f"STRONG {direction}"
        elif signal == "edge":
            label = direction
        else:
            label = direction
        try:
            append_signal(
                market_type=market_type,
                team=row["team"],
                ai_prob=row["ai_prob"],
                market_prob=row["market_prob"],
                edge_pct=row["edge_pct"],
                signal=label,
                kelly=row.get("half_kelly"),
                event_slug=event_slug,
            )
            logged += 1
        except Exception as exc:
            log.warning("Signal log append failed for %s: %s", row.get("team"), exc)
    if logged:
        print(f"  ▸ Logged {logged} signals to results/signal_log.jsonl (for CLV tracking)")


def run_elo_baseline() -> tuple[pd.DataFrame, dict[str, float]]:
    """Phase 1: Elo-baseline predictions."""
    print("=" * 70)
    print("UCL ORACLE — 2025-26 Champions League Predictions")
    print("=" * 70)

    # Fetch current Elo
    print("\n[1/3] Fetching club Elo ratings …")
    elos = fetch_current_elos()
    print(f"\n{'Team':20s} {'Elo':>8s}")
    print("-" * 30)
    for team in sorted(elos, key=elos.get, reverse=True):
        print(f"  {team:20s} {elos[team]:7.1f}")

    # Show first-leg context
    print("\n[2/3] QF First-Leg Results (already played):")
    xg_data = fetch_first_leg_xg() if FIRST_LEG_ADJUSTMENT_ENABLED else {}
    for qf_id, fl in FIRST_LEG_RESULTS.items():
        h, a = fl["home"], fl["away"]
        hg, ag = fl["home_goals"], fl["away_goals"]
        xg = xg_data.get(qf_id)
        xg_str = (
            f"  (xG: {xg['home_xg']:.2f}-{xg['away_xg']:.2f})" if xg else ""
        )
        print(f"  {qf_id}: {h} {hg}-{ag} {a}{xg_str}")

    # First-leg Elo adjustment (feeds SF/Final sims; QF aggregates still use goals)
    if FIRST_LEG_ADJUSTMENT_ENABLED:
        print("\n  Applying first-leg Elo adjustments (xG-weighted performance residual):")
        before = dict(elos)
        elos, adjustments = adjust_elos_for_first_legs(elos, xg_data=xg_data)
        print(format_adjustments_report(adjustments, before, elos))

    # Injury-based Elo penalty (feeds every stage from here on)
    if INJURY_ADJUSTMENT_ENABLED:
        print("\n  Fetching injury lists from FotMob …")
        injuries = fetch_all_injuries()
        team_deltas, breakdown = compute_injury_penalties(injuries)
        elos = apply_injury_penalties(elos, team_deltas)
        print(format_injury_report(team_deltas, breakdown))

    # Monte Carlo
    print(f"\n[3/3] Running {MONTE_CARLO_SIMULATIONS:,} Monte Carlo simulations …")
    results_df = run_monte_carlo(elos, n_simulations=MONTE_CARLO_SIMULATIONS)

    print(f"\n{'Team':20s} {'QF Adv':>8s} {'Final':>8s} {'Champion':>8s}")
    print("-" * 48)
    for _, row in results_df.iterrows():
        print(
            f"  {row['team']:20s}"
            f" {row['P(qf_advance)']:7.1%}"
            f" {row['P(final)']:7.1%}"
            f" {row['P(champion)']:7.1%}"
        )

    total = results_df["P(champion)"].sum()
    print(f"\n  P(champion) sum: {total:.4f}")

    # Save
    results_df.to_csv(RESULTS_DIR / "predictions" / "elo_baseline.csv", index=False)

    # Extract champion probabilities as dict
    champion_probs = dict(zip(results_df["team"], results_df["P(champion)"]))
    return results_df, champion_probs


def run_polymarket_comparison(
    results_df: pd.DataFrame,
    champion_probs: dict[str, float],
) -> None:
    """Phase 2: Fetch Polymarket odds and detect edges."""
    from data.fetcher_polymarket import fetch_all_ucl_odds

    print("\n" + "=" * 70)
    print("POLYMARKET COMPARISON")
    print("=" * 70)

    odds = fetch_all_ucl_odds()

    # ── Winner market ───────────────────────────────────────────────────
    winner_df = odds.get("winner")
    if winner_df is not None and not winner_df.empty:
        print(f"\n--- UCL WINNER MARKET ---")
        print(f"Event: {winner_df['event_title'].iloc[0]}")
        print(f"Volume: ${winner_df['volume'].iloc[0]:,.0f}")

        winner_market_probs = dict(zip(winner_df["team"], winner_df["implied_prob"]))

        print(f"\n{'Team':20s} {'AI Win%':>8s} {'Mkt Win%':>8s} {'Edge':>8s} {'Signal':>12s}")
        print("-" * 60)
        for team in sorted(champion_probs, key=champion_probs.get, reverse=True):
            ai_p = champion_probs[team]
            mkt_p = winner_market_probs.get(team, 0.0)
            edge = (ai_p - mkt_p) * 100 if mkt_p > 0 else float("nan")
            signal = ""
            if mkt_p > 0:
                if abs(edge) >= 5:
                    signal = "STRONG BUY" if edge > 0 else "STRONG SELL"
                elif abs(edge) >= 3:
                    signal = "BUY" if edge > 0 else "SELL"
            mkt_str = f"{mkt_p:7.1%}" if mkt_p > 0 else "    N/A"
            edge_str = f"{edge:+7.1f}%" if mkt_p > 0 else "    N/A"
            print(f"  {team:20s} {ai_p:7.1%} {mkt_str} {edge_str} {signal:>12s}")

        # Edge detection
        edges = detect_edges(champion_probs, winner_market_probs)
        if not edges.empty:
            print(f"\n--- WINNER MARKET EDGES ---")
            print(format_edge_report(edges))
            edges.to_csv(RESULTS_DIR / "edges" / "winner_edges.csv", index=False)
            # Append every actionable edge to the CLV signal log
            _log_edges(edges, market_type="winner", event_slug=UCL_WINNER_EVENT_SLUG)
    else:
        print("\n  UCL winner market: not found on Polymarket")

    # ── QF advancement / Semis market ───────────────────────────────────
    semis_df = odds.get("semis")
    if semis_df is not None and not semis_df.empty:
        print(f"\n--- QF ADVANCEMENT MARKET (Who reaches semis?) ---")
        print(f"Event: {semis_df['event_title'].iloc[0]}")
        print(f"Volume: ${semis_df['volume'].iloc[0]:,.0f}")

        semis_market_probs = dict(zip(semis_df["team"], semis_df["implied_prob"]))
        qf_advance_probs = dict(zip(results_df["team"], results_df["P(qf_advance)"]))

        print(f"\n{'Team':20s} {'AI Adv%':>8s} {'Mkt Adv%':>8s} {'Edge':>8s} {'Signal':>12s}")
        print("-" * 60)
        for team in sorted(qf_advance_probs, key=qf_advance_probs.get, reverse=True):
            ai_p = qf_advance_probs[team]
            mkt_p = semis_market_probs.get(team, 0.0)
            edge = (ai_p - mkt_p) * 100 if mkt_p > 0 else float("nan")
            signal = ""
            if mkt_p > 0:
                if abs(edge) >= 5:
                    signal = "STRONG BUY" if edge > 0 else "STRONG SELL"
                elif abs(edge) >= 3:
                    signal = "BUY" if edge > 0 else "SELL"
            mkt_str = f"{mkt_p:7.1%}" if mkt_p > 0 else "    N/A"
            edge_str = f"{edge:+7.1f}%" if mkt_p > 0 else "    N/A"
            print(f"  {team:20s} {ai_p:7.1%} {mkt_str} {edge_str} {signal:>12s}")

        # Edge detection for advancement
        adv_edges = detect_edges(qf_advance_probs, semis_market_probs)
        if not adv_edges.empty:
            print(f"\n--- QF ADVANCEMENT EDGES ---")
            print(format_edge_report(adv_edges))
            adv_edges.to_csv(RESULTS_DIR / "edges" / "qf_advance_edges.csv", index=False)
            _log_edges(adv_edges, market_type="qf_advance", event_slug=UCL_SEMIS_EVENT_SLUG)
    else:
        print("\n  QF advancement market: not found on Polymarket")


def run_tsfm_predictions() -> tuple[pd.DataFrame, dict[str, float]]:
    """Phase 3: TSFM-enhanced predictions with ensemble."""
    import numpy as np
    from data.fetcher_clubelo import fetch_all_histories, fetch_current_elos
    from data.elo import build_all_weekly_series
    from prediction.strength_forecaster import forecast_all_teams, get_elo_at_week
    from prediction.ensemble import ensemble_tournament_probs

    print("\n" + "=" * 70)
    print("TSFM-ENHANCED PREDICTIONS")
    print("=" * 70)

    # Fetch Elo histories and build weekly series
    print("\n[1/4] Fetching club Elo histories from clubelo.com …")
    histories = fetch_all_histories()
    weekly_series = build_all_weekly_series(histories)

    # Run TSFM models
    print("\n[2/4] Running TSFM models (Chronos-2, TimesFM-2.5, FlowState) …")
    forecasts = forecast_all_teams(weekly_series)

    # Extract forecasted Elo at QF time (week 0 = first forecast week)
    model_elos = get_elo_at_week(forecasts, week_index=0)

    # Also include Elo baseline as a "model"
    current_elos = fetch_current_elos()
    model_elos["Elo-Baseline"] = current_elos

    # Apply first-leg Elo adjustment to every model's Elo dict
    if FIRST_LEG_ADJUSTMENT_ENABLED:
        xg_data = fetch_first_leg_xg()
        print("\n  Applying first-leg Elo adjustments to each model:")
        for mn, elos_m in list(model_elos.items()):
            adjusted, _ = adjust_elos_for_first_legs(elos_m, xg_data=xg_data)
            model_elos[mn] = adjusted

    # Apply injury penalty to every model's Elo dict (fetched once, shared)
    if INJURY_ADJUSTMENT_ENABLED:
        print("\n  Applying injury penalties to each model:")
        injuries = fetch_all_injuries()
        team_deltas, _ = compute_injury_penalties(injuries)
        for mn in list(model_elos.keys()):
            model_elos[mn] = apply_injury_penalties(model_elos[mn], team_deltas)

    # Run Monte Carlo for each model
    print("\n[3/4] Running Monte Carlo per model …")
    model_tournament_probs = {}
    for model_name, elos in model_elos.items():
        mc_df = run_monte_carlo(elos, n_simulations=MONTE_CARLO_SIMULATIONS, seed=42)
        model_tournament_probs[model_name] = {}
        for _, row in mc_df.iterrows():
            model_tournament_probs[model_name][row["team"]] = {
                s: row[f"P({s})"] for s in ["qf_advance", "final", "champion"]
            }
        champ_top = mc_df.iloc[0]
        print(f"  {model_name:15s}: top pick = {champ_top['team']} ({champ_top['P(champion)']:.1%})")

    # Ensemble
    print("\n[4/4] Ensembling models …")
    ensemble_probs = ensemble_tournament_probs(model_tournament_probs)

    # Build results DataFrame
    rows = []
    for team in sorted(ensemble_probs.keys()):
        row = {"team": team}
        for stage in ["qf_advance", "final", "champion"]:
            row[f"P({stage})"] = ensemble_probs[team][stage]
        rows.append(row)
    ensemble_df = pd.DataFrame(rows).sort_values("P(champion)", ascending=False).reset_index(drop=True)

    # Print per-model breakdown
    print(f"\n{'Team':20s}", end="")
    for mn in model_elos:
        print(f" {mn[:10]:>10s}", end="")
    print(f" {'ENSEMBLE':>10s}")
    print("-" * (22 + 11 * (len(model_elos) + 1)))
    for _, row in ensemble_df.iterrows():
        team = row["team"]
        print(f"  {team:20s}", end="")
        for mn in model_elos:
            p = model_tournament_probs[mn][team]["champion"]
            print(f" {p:9.1%}", end="")
        print(f" {row['P(champion)']:9.1%}")

    total = ensemble_df["P(champion)"].sum()
    print(f"\n  Ensemble P(champion) sum: {total:.4f}")

    # Save
    ensemble_df.to_csv(RESULTS_DIR / "predictions" / "ensemble.csv", index=False)

    # Per-model CSV
    for model_name in model_elos:
        model_rows = []
        for team in sorted(model_tournament_probs[model_name].keys()):
            row = {"team": team}
            row.update(model_tournament_probs[model_name][team])
            model_rows.append(row)
        pd.DataFrame(model_rows).to_csv(
            RESULTS_DIR / "predictions" / f"{model_name.replace(' ', '_').replace('.', '_').lower()}.csv",
            index=False,
        )

    champion_probs = dict(zip(ensemble_df["team"], ensemble_df["P(champion)"]))

    # Also save per-model champion probs for edge detector model agreement
    model_champion_probs = {}
    for mn in model_elos:
        model_champion_probs[mn] = {
            team: model_tournament_probs[mn][team]["champion"]
            for team in model_tournament_probs[mn]
        }

    return ensemble_df, champion_probs, model_champion_probs, model_tournament_probs


def run_full_pipeline():
    """Run complete pipeline: Elo baseline → Polymarket → TSFM → Final comparison."""
    from data.fetcher_polymarket import fetch_all_ucl_odds

    # Phase 1: Elo baseline
    results_df, champion_probs = run_elo_baseline()

    # Phase 2: Polymarket comparison (Elo baseline)
    run_polymarket_comparison(results_df, champion_probs)

    # Phase 3: TSFM enhancement
    try:
        ensemble_df, ensemble_champ, model_champ, model_tourn = run_tsfm_predictions()

        # Final Polymarket comparison with TSFM ensemble
        print("\n" + "=" * 70)
        print("FINAL COMPARISON: TSFM ENSEMBLE vs POLYMARKET")
        print("=" * 70)

        odds = fetch_all_ucl_odds()

        # Winner market with model agreement
        winner_df = odds.get("winner")
        if winner_df is not None and not winner_df.empty:
            winner_market_probs = dict(zip(winner_df["team"], winner_df["implied_prob"]))

            print(f"\n--- UCL WINNER MARKET (TSFM Ensemble) ---")
            print(f"\n{'Team':20s} {'Ensemble':>8s} {'Market':>8s} {'Edge':>8s} {'Signal':>12s}")
            print("-" * 60)
            for team in sorted(ensemble_champ, key=ensemble_champ.get, reverse=True):
                ai_p = ensemble_champ[team]
                mkt_p = winner_market_probs.get(team, 0.0)
                edge = (ai_p - mkt_p) * 100 if mkt_p > 0 else float("nan")
                signal = ""
                if mkt_p > 0:
                    if abs(edge) >= 5:
                        signal = "STRONG BUY" if edge > 0 else "STRONG SELL"
                    elif abs(edge) >= 3:
                        signal = "BUY" if edge > 0 else "SELL"
                mkt_str = f"{mkt_p:7.1%}" if mkt_p > 0 else "    N/A"
                edge_str = f"{edge:+7.1f}%" if mkt_p > 0 else "    N/A"
                print(f"  {team:20s} {ai_p:7.1%} {mkt_str} {edge_str} {signal:>12s}")

            edges = detect_edges(ensemble_champ, winner_market_probs, model_probs=model_champ)
            if not edges.empty:
                print(f"\n--- ENSEMBLE EDGES (with model agreement) ---")
                print(format_edge_report(edges))
                edges.to_csv(RESULTS_DIR / "edges" / "ensemble_winner_edges.csv", index=False)

        # QF advancement with ensemble
        semis_df = odds.get("semis")
        if semis_df is not None and not semis_df.empty:
            semis_market_probs = dict(zip(semis_df["team"], semis_df["implied_prob"]))
            qf_advance_probs = dict(zip(ensemble_df["team"], ensemble_df["P(qf_advance)"]))

            # Model QF advance probs
            model_qf_probs = {}
            for mn in model_champ:
                model_qf_probs[mn] = {
                    team: model_tourn[mn][team]["qf_advance"]
                    for team in model_tourn[mn]
                }

            print(f"\n--- QF ADVANCEMENT (TSFM Ensemble) ---")
            print(f"\n{'Team':20s} {'Ensemble':>8s} {'Market':>8s} {'Edge':>8s} {'Signal':>12s}")
            print("-" * 60)
            for team in sorted(qf_advance_probs, key=qf_advance_probs.get, reverse=True):
                ai_p = qf_advance_probs[team]
                mkt_p = semis_market_probs.get(team, 0.0)
                edge = (ai_p - mkt_p) * 100 if mkt_p > 0 else float("nan")
                signal = ""
                if mkt_p > 0:
                    if abs(edge) >= 5:
                        signal = "STRONG BUY" if edge > 0 else "STRONG SELL"
                    elif abs(edge) >= 3:
                        signal = "BUY" if edge > 0 else "SELL"
                mkt_str = f"{mkt_p:7.1%}" if mkt_p > 0 else "    N/A"
                edge_str = f"{edge:+7.1f}%" if mkt_p > 0 else "    N/A"
                print(f"  {team:20s} {ai_p:7.1%} {mkt_str} {edge_str} {signal:>12s}")

            adv_edges = detect_edges(qf_advance_probs, semis_market_probs, model_probs=model_qf_probs)
            if not adv_edges.empty:
                print(f"\n--- ENSEMBLE QF ADVANCEMENT EDGES ---")
                print(format_edge_report(adv_edges))
                adv_edges.to_csv(RESULTS_DIR / "edges" / "ensemble_qf_advance_edges.csv", index=False)

    except Exception as e:
        log.error("TSFM pipeline failed: %s", e, exc_info=True)
        print(f"\n[!] TSFM pipeline failed: {e}")
        print("    Elo-baseline predictions remain valid above.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
    )

    import argparse
    parser = argparse.ArgumentParser(
        description="2025-26 UEFA Oracle Predictions",
        epilog=(
            "Default runs the production stack (Elo + first-leg xG + injuries + "
            "Monte Carlo → Polymarket). Add --with-tsfm to additionally run the "
            "3 foundation-model ensemble as an ablation; it added ≤1pp hit rate "
            "in the Layer 2 backtest, so it's kept purely for research/comparison."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--with-tsfm", "--full",
        dest="with_tsfm",
        action="store_true",
        help="ALSO run the TSFM ensemble (Chronos-2 + TimesFM-2.5 + FlowState). "
             "Slow (~5-7 min extra). Use for ablation / research / uncertainty "
             "bands, not for point-prediction quality.",
    )
    # Kept for backwards-compatibility; --fast is now the default behavior
    mode.add_argument(
        "--fast", "--elo-only",
        dest="fast_legacy",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if args.with_tsfm:
        print("▸ Full mode: running TSFM ensemble in addition to Elo-stack.")
        print("  (Layer 2 backtest: TSFM adds ≤1pp hit rate; here as ablation.)\n")
        run_full_pipeline()
    else:
        # Default: production Elo-stack only (no TSFM)
        results_df, champion_probs = run_elo_baseline()
        run_polymarket_comparison(results_df, champion_probs)
