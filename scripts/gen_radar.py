#!/usr/bin/env python3
"""
gen_radar.py: Figure 6 (per-protocol radar small-multiples).

For each scored protocol, render an 8-axis radar over the same ordinal-axis
subset used in the heatmap. Complements Figure 5 by showing the *shape* of
each protocol's strengths rather than the absolute level.

Layout: 2 columns × N rows; one tile per scored protocol; shared axis labels.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

try:
    import yaml
    import matplotlib.pyplot as plt
    import matplotlib
    import numpy as np
except ImportError as e:
    sys.exit(f"Missing dependency: {e.name}: install with: pip install pyyaml matplotlib numpy")

# arXiv asks submitters to avoid Type 3 fonts, which matplotlib's PDF backend
# emits by default. Type 42 embeds TrueType outlines instead, so the figure
# text stays selectable and searchable in the posted PDF.
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42

REPO = Path(__file__).resolve().parent.parent
YAML_PATH = REPO / "data" / "protocol-scores.yaml"
PDF_PATH = REPO / "manuscript" / "figures" / "fig6-radar.pdf"

# Same axis subset as the heatmap.
RADAR_AXES = [1, 2, 3, 5, 6, 7, 8, 9]
AXIS_LABELS = ["Disc.", "Ident.", "Authz.", "Task", "Async", "Multi-modal", "Sec n/12", "Semantic"]


def cell(entry: dict | None, axis: int) -> float | None:
    if not entry or "score" not in entry:
        return None
    s = entry["score"]
    if isinstance(s, str):
        return None
    return (s / 12.0) * 3.0 if axis == 8 else float(s)


def main() -> int:
    scores = yaml.safe_load(YAML_PATH.read_text())
    scored = []
    for pid, data in scores.items():
        if not isinstance(data, dict):
            continue
        vals = [cell(data.get(f"axis_{a}"), a) for a in RADAR_AXES]
        if all(v is None for v in vals):
            continue
        # Fill missing with 0 (renders as collapsed spike).
        vals = [0.0 if v is None else v for v in vals]
        scored.append((data.get("name", pid), vals))

    if not scored:
        sys.exit("No scored protocols in protocol-scores.yaml: cannot render radar charts.")

    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)

    cols = 2
    rows = math.ceil(len(scored) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(7.0, 3.0 * rows),
                             subplot_kw={"projection": "polar"})
    axes_flat = np.array(axes).flatten()

    angles = np.linspace(0, 2 * np.pi, len(RADAR_AXES), endpoint=False).tolist()
    angles += angles[:1]  # close the loop

    for idx, (name, vals) in enumerate(scored):
        ax = axes_flat[idx]
        closed = vals + vals[:1]
        ax.plot(angles, closed, color="#2171b5", linewidth=1.5)
        ax.fill(angles, closed, color="#2171b5", alpha=0.20)
        ax.set_ylim(0, 3.0)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(AXIS_LABELS, fontsize=7)
        ax.set_yticks([1, 2, 3])
        ax.set_yticklabels(["1", "2", "3"], fontsize=6, color="#666")
        ax.set_title(name, fontsize=9, pad=10)
        ax.grid(linewidth=0.5, color="#cccccc")

    for idx in range(len(scored), len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.suptitle("Per-protocol radar: ordinal axes (0-3 scale)", fontsize=10, y=1.00)
    fig.tight_layout()
    fig.savefig(PDF_PATH, format="pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {PDF_PATH.relative_to(REPO)} ({len(scored)} scored protocols)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
