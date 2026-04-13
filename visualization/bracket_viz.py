"""UCL bracket visualization with advancement probabilities."""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

from config import FIRST_LEG_RESULTS, PLOTS_DIR


# ── Layout constants (center-based, so lines and boxes stay in sync) ────────
BOX_W = 22
BOX_H = 3.6
LINE_COLOR = "#888"
LINE_KW = dict(color=LINE_COLOR, linewidth=1.1, solid_capstyle="round")

# Column left edges
X_QF = 4
X_SF = 33
X_F = 62
X_CH = 84

# Vertical centers for the 8 QF team boxes, paired tightly
# Pair 1 (QF1): top pair in Silver path
# Pair 2 (QF2): below pair 1 in Silver path
# Gap
# Pair 3 (QF3): top pair in Blue path
# Pair 4 (QF4): below pair 3 in Blue path
QF_PAIR_GAP = 4.5   # vertical gap within a tie (home vs away)
QF_TIE_GAP = 9.0    # vertical gap between consecutive ties in same half
QF_HALF_GAP = 4.5   # extra gap between Silver half and Blue half (visual break)


def _qf_centers() -> list[float]:
    """Return 8 vertical centers (top→bottom) for the 8 QF boxes."""
    # Start from top. Pair means (home, away).
    y0 = 50 - 2            # top anchor a bit below title
    p = QF_PAIR_GAP
    t = QF_TIE_GAP
    h = QF_HALF_GAP
    return [
        y0,                                 # QF1 home
        y0 - p,                             # QF1 away
        y0 - p - t,                         # QF2 home
        y0 - 2 * p - t,                     # QF2 away
        y0 - 2 * p - t - h - t,             # QF3 home
        y0 - 3 * p - t - h - t,             # QF3 away
        y0 - 3 * p - 2 * t - h - t,         # QF4 home
        y0 - 4 * p - 2 * t - h - t,         # QF4 away
    ]


def _pair_mid(a: float, b: float) -> float:
    return (a + b) / 2


def plot_bracket(
    results_df,
    save_path=None,
    subtitle: str = "TSFM Ensemble (Chronos-2 + TimesFM-2.5 + FlowState + Elo)",
):
    """Draw UCL knockout bracket with probabilities."""
    if save_path is None:
        save_path = PLOTS_DIR / "ucl_bracket.png"

    probs = {
        row["team"]: {
            "qf": row["P(qf_advance)"],
            "final": row["P(final)"],
            "champ": row["P(champion)"],
        }
        for _, row in results_df.iterrows()
    }

    # Derive plot height from the QF layout to avoid hand-tuning magic numbers
    qf_cy = _qf_centers()
    plot_top = 58
    plot_bottom = min(qf_cy) - BOX_H / 2 - 4

    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 100)
    ax.set_ylim(plot_bottom, plot_top)
    ax.set_aspect("auto")
    ax.axis("off")

    # ── Helpers ─────────────────────────────────────────────────────────
    def prob_color(p):
        r = 0.95 - 0.6 * p
        g = 0.95 - 0.2 * p
        b = 0.95 - 0.6 * p
        return (max(r, 0.1), max(g, 0.35), max(b, 0.1))

    def draw_team_box(x_left, cy, team, prob, w=BOX_W, h=BOX_H, leg=None, bold_name=True):
        """Draw a box whose vertical center is at `cy`."""
        y = cy - h / 2
        rect = patches.FancyBboxPatch(
            (x_left, y), w, h,
            boxstyle=f"round,pad=0.25,rounding_size=0.5",
            facecolor=prob_color(prob), edgecolor="#333", linewidth=1.0,
        )
        ax.add_patch(rect)
        ax.text(x_left + 1.0, cy, team, fontsize=9,
                fontweight="bold" if bold_name else "normal",
                va="center", ha="left", color="#111")
        ax.text(x_left + w - 1.0, cy, f"{prob:.0%}", fontsize=9,
                va="center", ha="right", color="#333", fontweight="bold")
        if leg:
            ax.text(x_left + w / 2, y - 0.9, leg, fontsize=7,
                    va="top", ha="center", color="#555", style="italic")

    def box_right(x_left, w=BOX_W):
        return x_left + w

    def draw_bracket_connector(src1_right, src1_cy, src2_right, src2_cy,
                               dst_left, dst_cy):
        """Draw the standard bracket ├── connector: two horizontals + one vertical + one horizontal."""
        mid_x = (max(src1_right, src2_right) + dst_left) / 2
        # Horizontal segments from each source to the vertical join
        ax.plot([src1_right, mid_x], [src1_cy, src1_cy], **LINE_KW)
        ax.plot([src2_right, mid_x], [src2_cy, src2_cy], **LINE_KW)
        # Vertical join
        ax.plot([mid_x, mid_x], [src1_cy, src2_cy], **LINE_KW)
        # Horizontal trunk into destination
        ax.plot([mid_x, dst_left], [dst_cy, dst_cy], **LINE_KW)

    # ── Title ───────────────────────────────────────────────────────────
    ax.text(50, plot_top - 1.2, "2025-26 UEFA Champions League",
            fontsize=17, fontweight="bold", ha="center", va="center", color="#1a237e")
    ax.text(50, plot_top - 3.0, "Knockout Bracket — AI Advancement Probabilities",
            fontsize=11, ha="center", va="center", color="#555")

    # ── QF column ───────────────────────────────────────────────────────
    fl = FIRST_LEG_RESULTS
    qf_pairs = [
        ("QF1", fl["QF1"]["home"], fl["QF1"]["away"], fl["QF1"]),
        ("QF2", fl["QF2"]["home"], fl["QF2"]["away"], fl["QF2"]),
        ("QF3", fl["QF3"]["home"], fl["QF3"]["away"], fl["QF3"]),
        ("QF4", fl["QF4"]["home"], fl["QF4"]["away"], fl["QF4"]),
    ]

    # Map team name → qf center for line-drawing later
    team_cy_qf: dict[str, float] = {}
    pair_mid_cy: dict[str, float] = {}

    for pair_idx, (qf_id, home, away, leg) in enumerate(qf_pairs):
        cy_home = qf_cy[pair_idx * 2]
        cy_away = qf_cy[pair_idx * 2 + 1]
        team_cy_qf[home] = cy_home
        team_cy_qf[away] = cy_away
        pair_mid_cy[qf_id] = _pair_mid(cy_home, cy_away)

        leg_str = f"1st leg: {leg['home_goals']}-{leg['away_goals']}"
        draw_team_box(X_QF, cy_home, home, probs[home]["qf"])
        draw_team_box(X_QF, cy_away, away, probs[away]["qf"])
        # Put 1st-leg caption centered between the pair, to the right of the boxes
        ax.text(X_QF + BOX_W / 2, _pair_mid(cy_home, cy_away),
                leg_str, fontsize=7, ha="center", va="center",
                color="#4a148c", style="italic", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="#f3e5f5",
                          edgecolor="#b39ddb", linewidth=0.6))

    # ── Column headers ──────────────────────────────────────────────────
    header_y = plot_top - 5.0
    header_sub_y = header_y - 1.6
    ax.text(X_QF + BOX_W / 2, header_y, "QUARTER-FINALS",
            fontsize=11, fontweight="bold", ha="center", color="#333")
    ax.text(X_QF + BOX_W / 2, header_sub_y, "2nd legs: Apr 14-15",
            fontsize=8, ha="center", color="#777")

    ax.text(X_SF + BOX_W / 2, header_y, "SEMI-FINALS",
            fontsize=11, fontweight="bold", ha="center", color="#333")
    ax.text(X_SF + BOX_W / 2, header_sub_y, "Apr 28-29 / May 5-6",
            fontsize=8, ha="center", color="#777")

    ax.text(X_F + BOX_W / 2, header_y, "FINAL",
            fontsize=11, fontweight="bold", ha="center", color="#333")
    ax.text(X_F + BOX_W / 2, header_sub_y, "May 30, Budapest",
            fontsize=8, ha="center", color="#777")

    ax.text(X_CH + 7.5, header_y, "CHAMPION",
            fontsize=11, fontweight="bold", ha="center", color="#c62828")

    # ── SF column ───────────────────────────────────────────────────────
    # SF slot centered between its two source QF pair midpoints
    sf_cy = {
        "SF1_top":    pair_mid_cy["QF1"],
        "SF1_bottom": pair_mid_cy["QF2"],
        "SF2_top":    pair_mid_cy["QF3"],
        "SF2_bottom": pair_mid_cy["QF4"],
    }

    # For each SF slot, pick the team most likely to reach SF based on QF advance prob
    def top_from_pair(home, away):
        return home if probs[home]["qf"] >= probs[away]["qf"] else away

    sf_occupants = {
        "SF1_top":    top_from_pair(fl["QF1"]["home"], fl["QF1"]["away"]),
        "SF1_bottom": top_from_pair(fl["QF2"]["home"], fl["QF2"]["away"]),
        "SF2_top":    top_from_pair(fl["QF3"]["home"], fl["QF3"]["away"]),
        "SF2_bottom": top_from_pair(fl["QF4"]["home"], fl["QF4"]["away"]),
    }
    for slot, team in sf_occupants.items():
        draw_team_box(X_SF, sf_cy[slot], team, probs[team]["qf"])

    # Connectors: each QF pair → its SF slot
    pair_to_slot = {
        "QF1": "SF1_top", "QF2": "SF1_bottom",
        "QF3": "SF2_top", "QF4": "SF2_bottom",
    }
    for pair_idx, (qf_id, home, away, _) in enumerate(qf_pairs):
        cy_home = qf_cy[pair_idx * 2]
        cy_away = qf_cy[pair_idx * 2 + 1]
        slot = pair_to_slot[qf_id]
        draw_bracket_connector(
            box_right(X_QF), cy_home,
            box_right(X_QF), cy_away,
            X_SF, sf_cy[slot],
        )

    # ── Final column ────────────────────────────────────────────────────
    # Two Final slots centered on each SF pair midpoint
    final_cy = {
        "F_top":    _pair_mid(sf_cy["SF1_top"], sf_cy["SF1_bottom"]),
        "F_bottom": _pair_mid(sf_cy["SF2_top"], sf_cy["SF2_bottom"]),
    }

    # Pick top likely-finalist per path: highest P(final) among SF1 / SF2 occupants
    sf1_teams = [sf_occupants["SF1_top"], sf_occupants["SF1_bottom"]]
    sf2_teams = [sf_occupants["SF2_top"], sf_occupants["SF2_bottom"]]
    f_top_team = max(sf1_teams, key=lambda t: probs[t]["final"])
    f_bot_team = max(sf2_teams, key=lambda t: probs[t]["final"])

    draw_team_box(X_F, final_cy["F_top"], f_top_team, probs[f_top_team]["final"])
    draw_team_box(X_F, final_cy["F_bottom"], f_bot_team, probs[f_bot_team]["final"])

    # SF → Final connectors
    draw_bracket_connector(
        box_right(X_SF), sf_cy["SF1_top"],
        box_right(X_SF), sf_cy["SF1_bottom"],
        X_F, final_cy["F_top"],
    )
    draw_bracket_connector(
        box_right(X_SF), sf_cy["SF2_top"],
        box_right(X_SF), sf_cy["SF2_bottom"],
        X_F, final_cy["F_bottom"],
    )

    # ── Champion column ─────────────────────────────────────────────────
    ch_cy = _pair_mid(final_cy["F_top"], final_cy["F_bottom"])
    # Highest P(champion) overall
    all_teams_sorted = sorted(probs.keys(), key=lambda t: probs[t]["champ"], reverse=True)
    champion = all_teams_sorted[0]
    draw_team_box(X_CH, ch_cy, champion, probs[champion]["champ"], w=15)

    # Final → Champion connector (same ├── pattern)
    draw_bracket_connector(
        box_right(X_F), final_cy["F_top"],
        box_right(X_F), final_cy["F_bottom"],
        X_CH, ch_cy,
    )

    # ── Footer ──────────────────────────────────────────────────────────
    ax.text(50, plot_bottom + 2.2,
            f"Probabilities from {subtitle} \u00d7 50K Monte Carlo",
            fontsize=8, ha="center", color="#666")
    ax.text(50, plot_bottom + 0.8,
            "Darker green = higher probability  |  clubelo.com ratings  |  No away goals rule",
            fontsize=7, ha="center", color="#999")

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

    bars = ax.barh(df["team"], df["P(champion)"] * 100, color=colors,
                   edgecolor="#333", linewidth=0.5)

    for bar, (_, row) in zip(bars, df.iterrows()):
        width = bar.get_width()
        ax.text(width + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{row['P(champion)']:.1%}", va="center",
                fontsize=10, fontweight="bold")

    ax.set_xlabel("P(Champion) %", fontsize=12)
    ax.set_title(f"2025-26 UCL Winner Probabilities\n({subtitle}, 50K Monte Carlo)",
                 fontsize=13, fontweight="bold")
    ax.set_xlim(0, max(df["P(champion)"] * 100) * 1.15)
    ax.grid(axis="x", alpha=0.3)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved bar chart: {save_path}")
