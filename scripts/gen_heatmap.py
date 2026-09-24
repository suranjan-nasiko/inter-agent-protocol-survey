#!/usr/bin/env python3
"""
gen_heatmap.py: Figure 5 (protocols × 10 axes rubric heatmap).

Reads data/protocol-scores.yaml, builds a numeric matrix where:
  - ordinal axes (1-3, 5-7, 9) map directly to their 0-3 score
  - threat-surface (axis 8) is rescaled count/12 * 3 to fit the 0-3 scale
  - transport (axis 4) and governance (axis 10) are excluded from the heatmap
    (rendered separately in Table 5: they're not ordinal)

Empty axes (placeholder protocols) render as light grey.
"""

from __future__ import annotations

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
PDF_PATH = REPO / "manuscript" / "figures" / "fig5-heatmap.pdf"

# Axes shown in the heatmap (exclude tuple/composite axes).
HEATMAP_AXES = [1, 2, 3, 5, 6, 7, 8, 9]
AXIS_LABELS = {
    1: "Discovery",
    2: "Identity",
    3: "Auth/Delegation",
    5: "Task Model",
    6: "Async",
    7: "Multi-modal",
    8: "Security (n/12)",
    9: "Semantic Interop",
}


def cell(entry: dict | None, axis: int) -> float:
    if not entry or "score" not in entry:
        return float("nan")
    s = entry["score"]
    if isinstance(s, str):
        return float("nan")
    if axis == 8:
        return (s / 12.0) * 3.0  # rescale n/12 onto the 0-3 ordinal scale
    return float(s)


def build_matrix(scores: dict) -> tuple[np.ndarray, list[str]]:
    rows = []
    labels = []
    for pid, data in scores.items():
        if not isinstance(data, dict):
            continue
        row = [cell(data.get(f"axis_{a}"), a) for a in HEATMAP_AXES]
        if all(np.isnan(v) for v in row):
            continue  # skip placeholders with no scored axes
        rows.append(row)
        labels.append(data.get("name", pid))
    return np.array(rows), labels


def main() -> int:
    scores = yaml.safe_load(YAML_PATH.read_text())
    matrix, labels = build_matrix(scores)
    if matrix.size == 0:
        sys.exit("No scored protocols in protocol-scores.yaml: cannot render heatmap.")

    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.0, max(2.5, 0.45 * len(labels) + 1.2)))
    cmap = matplotlib.colormaps.get_cmap("Blues")
    cmap.set_bad(color="#eeeeee")  # NaN cells

    im = ax.imshow(matrix, cmap=cmap, vmin=0.0, vmax=3.0, aspect="auto")

    ax.set_xticks(range(len(HEATMAP_AXES)))
    ax.set_xticklabels([AXIS_LABELS[a] for a in HEATMAP_AXES], rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)

    # Annotate cells with the integer score (or "-" for NaN).
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v = matrix[i, j]
            text = "-" if np.isnan(v) else f"{int(round(v))}"
            colour = "white" if (not np.isnan(v) and v >= 2.0) else "black"
            ax.text(j, i, text, ha="center", va="center", color=colour, fontsize=7)

    cbar = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label("Score (ordinal 0-3)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    ax.set_title("Rubric heatmap: protocols × axes (ordinal axes only)",
                 fontsize=9, pad=6)
    fig.tight_layout()
    fig.savefig(PDF_PATH, format="pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {PDF_PATH.relative_to(REPO)} ({len(labels)} scored protocols)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
