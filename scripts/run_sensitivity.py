"""Run Layer 1 sensitivity sweep over canonical Poisson constants."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.sensitivity import sweep_params  # noqa: E402

OUT_DIR = ROOT / "backtest" / "results"


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = sweep_params()
    csv_path = OUT_DIR / "sensitivity_sweep.csv"
    md_path = OUT_DIR / "sensitivity_sweep.md"
    df.to_csv(csv_path, index=False)

    # Markdown summary
    lines = [
        "# Layer 1 Sensitivity Sweep",
        "",
        "How much does the 83-tie hit rate move when we perturb each canonical",
        "Poisson constant? If the model's edge lives on a knife-edge of some",
        "parameter value, hit rate should wobble. If not, the 63.9% is robust.",
        "",
    ]
    for param in df["param"].unique():
        sub = df[df["param"] == param].copy()
        min_hr = sub["hit_rate"].min()
        max_hr = sub["hit_rate"].max()
        spread = (max_hr - min_hr) * 100
        lines.append(f"## {param}")
        lines.append("")
        lines.append(sub[["value", "hit_rate", "brier", "delta_hit_rate"]].to_markdown(index=False))
        lines.append("")
        lines.append(f"**Spread across grid: {spread:.1f}pp**")
        lines.append("")
    md_path.write_text("\n".join(lines))

    print(f"\nSaved: {csv_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
