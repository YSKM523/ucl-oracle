"""UCL bracket visualization with advancement probabilities."""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

from config import FIRST_LEG_RESULTS, PLOTS_DIR


def plot_bracket(
    results_df,
    save_path=None,
    subtitle: str = "TSFM Ensemble (Chronos-2 + TimesFM-2.5 + FlowState + Elo)",
):
    """Draw UCL knockout bracket with probabilities.

    Parameters
    ----------
    results_df : DataFrame with columns team, P(qf_advance), P(final), P(champion)
    """
    if save_path is None:
        save_path = PLOTS_DIR / "ucl_bracket.png"

    probs = {}
    for _, row in results_df.iterrows():
        probs[row["team"]] = {
            "qf": row["P(qf_advance)"],
            "final": row["P(final)"],
            "champ": row["P(champion)"],
        }

    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.set_aspect("equal")
    ax.axis("off")

    # Colors
    def prob_color(p):
        """Green gradient based on probability."""
        r = 0.95 - 0.6 * p
        g = 0.95 - 0.2 * p
        b = 0.95 - 0.6 * p
        return (max(r, 0.1), max(g, 0.3), max(b, 0.1))

    def draw_team_box(x, y, team, prob, first_leg_info=None, w=22, h=4):
        color = prob_color(prob)
        rect = patches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.3",
            facecolor=color, edgecolor="#333", linewidth=1.2
        )
        ax.add_patch(rect)
        ax.text(x + 1, y + h/2, team, fontsize=9, fontweight="bold",
                va="center", ha="left", color="#111")
        ax.text(x + w - 1, y + h/2, f"{prob:.0%}", fontsize=9,
                va="center", ha="right", color="#444", fontweight="bold")
        if first_leg_info:
            ax.text(x + w/2, y - 0.8, first_leg_info, fontsize=7,
                    va="top", ha="center", color="#666", style="italic")

    # ── Title ───────────────────────────────────────────────────────────
    ax.text(50, 58, "2025-26 UEFA Champions League", fontsize=16,
            fontweight="bold", ha="center", va="center", color="#1a237e")
    ax.text(50, 55.5, "Knockout Bracket — AI Advancement Probabilities",
            fontsize=11, ha="center", va="center", color="#555")

    # ── QF column (left) ────────────────────────────────────────────────
    fl = FIRST_LEG_RESULTS
    qf_x = 5
    qf_pairs = [
        ("QF1", fl["QF1"]["home"], fl["QF1"]["away"],
         f"1st leg: {fl['QF1']['home_goals']}-{fl['QF1']['away_goals']}"),
        ("QF2", fl["QF2"]["home"], fl["QF2"]["away"],
         f"1st leg: {fl['QF2']['home_goals']}-{fl['QF2']['away_goals']}"),
        ("QF3", fl["QF3"]["home"], fl["QF3"]["away"],
         f"1st leg: {fl['QF3']['home_goals']}-{fl['QF3']['away_goals']}"),
        ("QF4", fl["QF4"]["home"], fl["QF4"]["away"],
         f"1st leg: {fl['QF4']['home_goals']}-{fl['QF4']['away_goals']}"),
    ]

    qf_y_positions = [44, 38, 22, 16]
    for i, (qf_id, home, away, leg_info) in enumerate(qf_pairs):
        y = qf_y_positions[i]
        draw_team_box(qf_x, y, home, probs[home]["qf"], leg_info if i % 2 == 0 else None)
        draw_team_box(qf_x, y - 6, away, probs[away]["qf"], leg_info if i % 2 == 1 else None)

    # QF labels
    ax.text(qf_x + 11, 52, "QUARTER-FINALS", fontsize=10, fontweight="bold",
            ha="center", color="#333")
    ax.text(qf_x + 11, 50.5, "2nd legs: Apr 14-15", fontsize=8, ha="center", color="#777")

    # ── SF column ───────────────────────────────────────────────────────
    sf_x = 33

    # Silver path SF — show P(qf_advance) i.e. "probability of reaching this stage"
    sf1_teams = [fl["QF1"]["home"], fl["QF1"]["away"], fl["QF2"]["home"], fl["QF2"]["away"]]
    sf1_top2 = sorted(sf1_teams, key=lambda t: probs[t]["qf"], reverse=True)[:2]
    draw_team_box(sf_x, 43, sf1_top2[0], probs[sf1_top2[0]]["qf"])
    draw_team_box(sf_x, 37, sf1_top2[1], probs[sf1_top2[1]]["qf"])

    # Blue path SF — same: P(qf_advance)
    sf2_teams = [fl["QF3"]["home"], fl["QF3"]["away"], fl["QF4"]["home"], fl["QF4"]["away"]]
    sf2_top2 = sorted(sf2_teams, key=lambda t: probs[t]["qf"], reverse=True)[:2]
    draw_team_box(sf_x, 21, sf2_top2[0], probs[sf2_top2[0]]["qf"])
    draw_team_box(sf_x, 15, sf2_top2[1], probs[sf2_top2[1]]["qf"])

    ax.text(sf_x + 11, 52, "SEMI-FINALS", fontsize=10, fontweight="bold",
            ha="center", color="#333")
    ax.text(sf_x + 11, 50.5, "Apr 28-29 / May 5-6", fontsize=8, ha="center", color="#777")

    # ── Final column ────────────────────────────────────────────────────
    f_x = 61
    all_teams_sorted = sorted(probs.keys(), key=lambda t: probs[t]["final"], reverse=True)
    draw_team_box(f_x, 33, all_teams_sorted[0], probs[all_teams_sorted[0]]["final"])
    draw_team_box(f_x, 27, all_teams_sorted[1], probs[all_teams_sorted[1]]["final"])

    ax.text(f_x + 11, 52, "FINAL", fontsize=10, fontweight="bold",
            ha="center", color="#333")
    ax.text(f_x + 11, 50.5, "May 30, Budapest", fontsize=8, ha="center", color="#777")

    # ── Champion ────────────────────────────────────────────────────────
    ch_x = 82
    champion = all_teams_sorted[0]
    draw_team_box(ch_x, 30, champion, probs[champion]["champ"], w=15)
    ax.text(ch_x + 7.5, 36, "CHAMPION", fontsize=10, fontweight="bold",
            ha="center", color="#c62828")

    # ── Connection lines ────────────────────────────────────────────────
    line_kw = dict(color="#999", linewidth=1, linestyle="-")
    # QF → SF lines
    ax.plot([27, 33], [46, 45], **line_kw)
    ax.plot([27, 33], [34, 39], **line_kw)
    ax.plot([27, 33], [24, 23], **line_kw)
    ax.plot([27, 33], [12, 17], **line_kw)
    # SF → Final
    ax.plot([55, 61], [42, 35], **line_kw)
    ax.plot([55, 61], [18, 29], **line_kw)
    # Final → Champion
    ax.plot([83, 82], [35, 32], **line_kw)
    ax.plot([83, 82], [29, 32], **line_kw)

    # ── Legend ──────────────────────────────────────────────────────────
    ax.text(50, 3, f"Probabilities from {subtitle} \u00d7 50K Monte Carlo",
            fontsize=8, ha="center", color="#888")
    ax.text(50, 1, "Darker green = higher probability | clubelo.com ratings | No away goals rule",
            fontsize=7, ha="center", color="#aaa")

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved bracket: {save_path}")


def plot_probability_bars(results_df, save_path=None, subtitle: str = "TSFM Ensemble"):
    """Horizontal bar chart of P(champion) for all 8 teams."""
    if save_path is None:
        save_path = PLOTS_DIR / "champion_probabilities.png"

    df = results_df.sort_values("P(champion)", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.YlGn(np.linspace(0.3, 0.9, len(df)))

    bars = ax.barh(df["team"], df["P(champion)"] * 100, color=colors, edgecolor="#333", linewidth=0.5)

    for bar, (_, row) in zip(bars, df.iterrows()):
        width = bar.get_width()
        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2,
                f"{row['P(champion)']:.1%}", va="center", fontsize=10, fontweight="bold")

    ax.set_xlabel("P(Champion) %", fontsize=12)
    ax.set_title(f"2025-26 UCL Winner Probabilities\n({subtitle}, 50K Monte Carlo)",
                 fontsize=13, fontweight="bold")
    ax.set_xlim(0, max(df["P(champion)"] * 100) * 1.15)
    ax.grid(axis="x", alpha=0.3)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved bar chart: {save_path}")
