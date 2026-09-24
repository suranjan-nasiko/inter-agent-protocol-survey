#!/usr/bin/env python3
"""
gen_taxonomy.py: Figure 1 (three-layer taxonomy tree).

Renders the taxonomy referenced in section 3.3: a top-down tree where the
root splits into three architectural layers (Tool binding, Peer messaging,
Commerce settlement), and each layer's column lists the protocols assigned
to it. Each leaf carries the orthogonal-axes triple (governance, discovery,
async) introduced in section 3.2.

Layer assignment and triples are sourced from the manuscript prose;
data/protocol-scores.yaml carries the per-axis scores that justify the
classifications. The YAML is loaded only to verify that every leaf id has
a corresponding entry, not to drive the layout.

Triple codes:
  Gov:   L = Linux Foundation / AAIF
         W = W3C
         V = vendor / single-vendor authorship
         I = individual / academic authors
         E = Ethereum EIP process
  Disc:  R = registry-based (well-known endpoint or directory service)
         P = peer-discovery (DID-resolver-based)
  Async: S = synchronous-first
         A = async-first
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
    import matplotlib.pyplot as plt
    import matplotlib
except ImportError as e:
    sys.exit(f"Missing dependency: {e.name}: install with: pip install pyyaml matplotlib")

# arXiv asks submitters to avoid Type 3 fonts, which matplotlib's PDF backend
# emits by default. Type 42 embeds TrueType outlines instead, so the figure
# text stays selectable and searchable in the posted PDF.
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42

REPO = Path(__file__).resolve().parent.parent
YAML_PATH = REPO / "data" / "protocol-scores.yaml"
PDF_PATH = REPO / "manuscript" / "figures" / "fig-taxonomy.pdf"

# Layer columns: (label, x-center, [(yaml-id, display-name, (gov, disc, async))]).
COLUMNS = [
    ("Layer 1\n(Tool binding)", 1.5, [
        ("mcp", "MCP", ("L", "R", "S")),
        ("acp", "ACP", ("L", "R", "S")),
    ]),
    ("Layer 2\n(Peer messaging)", 5.0, [
        ("a2a",    "A2A",         ("L", "R", "A")),
        ("anp",    "ANP",         ("W", "P", "S")),
        ("agntcy", "AGNTCY/SLIM", ("L", "R", "A")),
        ("coral",  "Coral",       ("V", "R", "A")),
        ("loka",   "LOKA",        ("I", "P", "A")),
        ("acnbp",  "ACNBP",       ("I", "R", "A")),
    ]),
    ("Layer 3\n(Commerce settlement)", 8.5, [
        ("ap2",                  "AP2",                  ("V", "R", "A")),
        ("visa_tap",             "Visa TAP",             ("V", "R", "A")),
        ("mastercard_agentpay",  "Mastercard Agent Pay", ("V", "R", "A")),
        ("erc_8004",             "ERC-8004",             ("E", "P", "A")),
        ("ucp",                  "UCP",                  ("V", "R", "A")),
    ]),
]

ROOT_X = 5.0
ROOT_Y = 5.6
BUS_Y = 4.85
LAYER_Y = 4.1
LEAF_TOP_Y = 3.05
LEAF_STEP = -0.42

LINE_COLOR = "#666"
ROOT_BORDER = "#000"
LAYER_BORDER = "#1f4f8a"
LAYER_BG = "#eaf0f8"
LEAF_COLOR = "#222"

LEGEND = (
    "Triple = (governance, discovery, async).   "
    "Gov: L=LF/AAIF · W=W3C · V=vendor · I=individual/academic · E=EIP process.\n"
    "Discovery: R=registry · P=peer/DID.    "
    "Async: S=sync-first · A=async-first."
)


def main() -> int:
    # Cross-check: every leaf id must have a YAML entry.
    scores = yaml.safe_load(YAML_PATH.read_text())
    for _, _, leaves in COLUMNS:
        for pid, _, _ in leaves:
            if pid not in scores:
                sys.exit(f"taxonomy leaf '{pid}' has no entry in protocol-scores.yaml")

    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.axis("off")

    # Root
    ax.text(ROOT_X, ROOT_Y, "Inter-Agent Protocols",
            ha="center", va="center", fontsize=11, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", fc="white",
                      ec=ROOT_BORDER, lw=1.2))

    # Root → bus → layers
    ax.plot([ROOT_X, ROOT_X], [ROOT_Y - 0.28, BUS_Y],
            color=LINE_COLOR, lw=0.9)
    xs = [x for _, x, _ in COLUMNS]
    ax.plot([min(xs), max(xs)], [BUS_Y, BUS_Y], color=LINE_COLOR, lw=0.9)
    for _, x, _ in COLUMNS:
        ax.plot([x, x], [BUS_Y, LAYER_Y + 0.24], color=LINE_COLOR, lw=0.9)

    # Layer nodes
    for label, x, _ in COLUMNS:
        ax.text(x, LAYER_Y, label,
                ha="center", va="center", fontsize=9.5, fontweight="bold",
                color=LAYER_BORDER,
                bbox=dict(boxstyle="round,pad=0.3", fc=LAYER_BG,
                          ec=LAYER_BORDER, lw=0.8))

    # Leaves under each column
    bottom_y = LEAF_TOP_Y
    for _, x, leaves in COLUMNS:
        for i, (_, name, triple) in enumerate(leaves):
            y = LEAF_TOP_Y + i * LEAF_STEP
            ax.text(x, y, f"{name}  ({', '.join(triple)})",
                    ha="center", va="center", fontsize=8.5,
                    color=LEAF_COLOR)
            if y < bottom_y:
                bottom_y = y

    # Legend
    ax.text(ROOT_X, bottom_y - 0.55, LEGEND,
            ha="center", va="top", fontsize=7.0, color="#444",
            linespacing=1.35)

    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(bottom_y - 1.6, ROOT_Y + 0.65)

    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PDF_PATH, format="pdf", bbox_inches="tight")
    plt.close(fig)
    n_leaves = sum(len(leaves) for _, _, leaves in COLUMNS)
    print(f"Wrote {PDF_PATH.relative_to(REPO)} ({len(COLUMNS)} layers, {n_leaves} leaves)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
