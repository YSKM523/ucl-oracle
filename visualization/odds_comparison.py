"""AI vs Polymarket odds comparison plots."""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from config import PLOTS_DIR


def plot_scatter(
    ai_probs: dict[str, float],
    market_probs: dict[str, float],
    title: str = "AI vs Polymarket — UCL Winner",
    save_path=None,
):
    """Scatter plot: AI probability vs Polymarket probability."""
    if save_path is None:
        save_path = PLOTS_DIR / "ai_vs_polymarket_scatter.png"

    # Only include teams present in both
    teams = [t for t in ai_probs if t in market_probs and market_probs[t] > 0]
    ai_vals = [ai_probs[t] * 100 for t in teams]
    mkt_vals = [market_probs[t] * 100 for t in teams]
    edges = [ai_probs[t] * 100 - market_probs[t] * 100 for t in teams]

    fig, ax = plt.subplots(figsize=(9, 9))

    # Diagonal (perfect agreement)
    max_val = max(max(ai_vals), max(mkt_vals)) * 1.1
    ax.plot([0, max_val], [0, max_val], "k--", alpha=0.3, linewidth=1)

    # Color by edge magnitude
    abs_edges = [abs(e) for e in edges]
    colors = ["#2e7d32" if e > 0 else "#c62828" for e in edges]
    sizes = [max(80, abs(e) * 30) for e in edges]

    for i, team in enumerate(teams):
        ax.scatter(mkt_vals[i], ai_vals[i], c=colors[i], s=sizes[i],
                   alpha=0.8, edgecolors="#333", linewidth=0.5, zorder=5)
        ax.annotate(team, (mkt_vals[i], ai_vals[i]),
                    textcoords="offset points", xytext=(8, 4),
                    fontsize=9, fontweight="bold", color=colors[i])

    # Shade regions
    ax.fill_between([0, max_val], [0, max_val], [max_val, max_val],
                    alpha=0.04, color="green", label="AI says BUY")
    ax.fill_between([0, max_val], [0, 0], [0, max_val],
                    alpha=0.04, color="red", label="AI says SELL")

    ax.set_xlabel("Polymarket Implied Probability (%)", fontsize=12)
    ax.set_ylabel("AI Prediction (%)", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.legend(loc="lower right", fontsize=10)
    ax.grid(alpha=0.2)
    ax.set_xlim(0, max_val)
    ax.set_ylim(0, max_val)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved scatter: {save_path}")


def plot_side_by_side(
    ai_probs: dict[str, float],
    market_probs: dict[str, float],
    title: str = "AI vs Polymarket — UCL Winner",
    save_path=None,
):
    """Grouped bar chart: AI vs Polymarket side by side."""
    if save_path is None:
        save_path = PLOTS_DIR / "ai_vs_polymarket_bars.png"

    teams = sorted(ai_probs.keys(), key=ai_probs.get, reverse=True)
    ai_vals = [ai_probs[t] * 100 for t in teams]
    mkt_vals = [market_probs.get(t, 0) * 100 for t in teams]

    x = np.arange(len(teams))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))
    bars1 = ax.bar(x - width/2, ai_vals, width, label="AI Ensemble", color="#1565c0", alpha=0.85)
    bars2 = ax.bar(x + width/2, mkt_vals, width, label="Polymarket", color="#ef6c00", alpha=0.85)

    ax.set_ylabel("Probability (%)", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(teams, rotation=30, ha="right", fontsize=10)
    ax.legend(fontsize=11)
    ax.grid(axis="y", alpha=0.3)

    # Value labels
    for bar in bars1:
        h = bar.get_height()
        if h > 1:
            ax.text(bar.get_x() + bar.get_width()/2, h + 0.3, f"{h:.1f}%",
                    ha="center", fontsize=8, color="#1565c0")
    for bar in bars2:
        h = bar.get_height()
        if h > 1:
            ax.text(bar.get_x() + bar.get_width()/2, h + 0.3, f"{h:.1f}%",
                    ha="center", fontsize=8, color="#ef6c00")

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved bar chart: {save_path}")


def plot_edge_bars(
    edges_df,
    title: str = "Edges: AI vs Polymarket",
    save_path=None,
):
    """Horizontal bar chart of edges."""
    if save_path is None:
        save_path = PLOTS_DIR / "edge_bars.png"

    if edges_df.empty:
        return

    df = edges_df.sort_values("edge_pct", ascending=True)

    fig, ax = plt.subplots(figsize=(11, max(4, len(df) * 0.8)))

    colors = ["#2e7d32" if e > 0 else "#c62828" for e in df["edge_pct"]]
    bars = ax.barh(df["team"], df["edge_pct"], color=colors,
                   edgecolor="#333", linewidth=0.5)

    max_abs = max(df["edge_pct"].abs().max(), 1.0)
    pad = max_abs * 0.06

    for bar, (_, row) in zip(bars, df.iterrows()):
        w = bar.get_width()
        label = f"{row['edge_pct']:+.1f}%"
        if row["strength"] == "STRONG EDGE":
            label += " ★"
        # Always place the numeric label just BEYOND the bar's tip,
        # on the same side as the bar's direction. Never overlaps the
        # team-name axis label, which lives on the other side of zero.
        if w >= 0:
            ax.text(w + pad, bar.get_y() + bar.get_height() / 2,
                    label, va="center", ha="left",
                    fontsize=10, fontweight="bold", color="#1b5e20")
        else:
            ax.text(w - pad, bar.get_y() + bar.get_height() / 2,
                    label, va="center", ha="right",
                    fontsize=10, fontweight="bold", color="#b71c1c")

    # Expand x-axis so labels always fit
    ax.set_xlim(-max_abs * 1.35, max_abs * 1.35)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Edge (percentage points)", fontsize=12)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    ax.tick_params(axis="y", labelsize=11)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved edge bars: {save_path}")
