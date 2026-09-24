#!/usr/bin/env bash
#
# Build a self-contained Overleaf upload bundle.
#
# Overleaf has no Python, so the generated tables and figures cannot be
# rebuilt there. This script regenerates them locally from data/*.yaml,
# then packages a flat tree that compiles on Overleaf with no build step.
#
# The bundle rewrites the bibliography path: in the repo main.tex reads
# ../refs/references.bib, but the bundle keeps refs/ inside the project root
# so Overleaf resolves it.
#
# jair.cls is not on Overleaf's TeX tree, and neither are the three biblatex
# support files the JAIR preamble names, so all four ship in the bundle.
# acmart, which jair.cls extends, is already on Overleaf.
#
# Usage: scripts/make_overleaf_bundle.sh [output.zip]

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$REPO/a2a-survey-overleaf.zip}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cd "$REPO"

echo "==> Regenerating tables and figures from data/*.yaml"
make tables figures >/dev/null

echo "==> Staging project tree"
BUNDLE="$STAGE/a2a-survey"
mkdir -p "$BUNDLE"
cp -r manuscript/sections "$BUNDLE/"
cp -r manuscript/tables   "$BUNDLE/"
cp -r manuscript/figures  "$BUNDLE/"
cp manuscript/main.tex manuscript/preamble.tex "$BUNDLE/"
# The JAIR class and its biblatex support files are not on Overleaf's TeX tree.
cp manuscript/jair.cls manuscript/acmauthoryear.bbx manuscript/acmauthoryear.cbx \
   manuscript/acmdatamodel.dbx "$BUNDLE/"
# Overleaf also drives the build with latexmk, so it needs the same cold-build
# workaround the local build uses. See the note inside the file.
cp manuscript/.latexmkrc "$BUNDLE/"
mkdir -p "$BUNDLE/refs"
cp refs/references.bib "$BUNDLE/refs/"

# Overleaf compiles from the project root, so ../refs/ does not resolve.
sed -i '' 's|\\addbibresource{\.\./refs/references\.bib}|\\addbibresource{refs/references.bib}|' \
  "$BUNDLE/main.tex"
grep -q '\\addbibresource{refs/references.bib}' "$BUNDLE/main.tex" \
  || { echo "FAIL: bibliography path rewrite did not apply"; exit 1; }

cat > "$BUNDLE/README-OVERLEAF.md" <<'EOF'
# Overleaf project: A Rubric-Based Survey of Inter-Agent Protocols

## Compiler settings

Set these in Overleaf under Menu (top left):

- **Compiler:** pdfLaTeX
- **TeX Live version:** 2024 or newer
- **Main document:** `main.tex`

The paper uses the official JAIR class, `jair.cls`, which extends ACM
`acmart`. `acmart` ships with Overleaf. `jair.cls` does not, so it is included
in this bundle along with the three biblatex files it needs
(`acmauthoryear.bbx`, `acmauthoryear.cbx`, `acmdatamodel.dbx`). All four are
unmodified copies from the official JAIR AuthorKit. Do not edit them: JAIR
does not allow changes to its style, and a modified manuscript is returned for
revision.

**References go through biber, not BibTeX.** Overleaf picks the right backend
automatically from the `\addbibresource` line, so there is nothing to set. If
citations come out as bold question marks, recompile once more; biber needs a
pass to write the `.bbl`.

`.latexmkrc` is a build fix, not a style change. On a cold build latexmk
writes a stub `main.aux` that makes `acmart` believe the paper is one page
long, which raises a spurious "No country present for an affiliation" error
even though every author block has a country. The file removes that one line
from the stub. Keep it.

## IMPORTANT: generated files

These files are generated from YAML in the GitHub repo and must NOT be
hand-edited here. Edits will be overwritten the next time anyone runs
`make tables` upstream:

- `tables/table1-rubric-matrix.tex`   (from `data/protocol-scores.yaml`)
- `tables/table3-threat-surface.tex`  (from `data/threat-coverage.yaml`)
- `tables/table4-industry-adoption.tex` (from `data/industry-adoption.yaml`)
- `figures/fig5-heatmap.pdf`, `figures/fig6-radar.pdf`, `figures/fig-taxonomy.pdf`

To change a rubric score, edit the YAML in the GitHub repo and rerun
`make tables figures`. This reproducibility pipeline is contribution C4
of the paper, so please keep it intact.

Hand-authored and safe to edit here: everything in `sections/`, plus
`tables/table2-commerce-stack.tex` and `tables/table5-governance-license.tex`.

## House style rules

Two rules apply to all prose in this paper:

1. **No em-dashes, en-dashes, or double hyphens.** No `---` and no `--`
   in body text. Use commas, colons, semicolons, parentheses, or start a
   new sentence. For numeric ranges write "X to Y", not "X--Y".
2. **Medium and short sentences.** Target under 25 words. Treat 30+ as a
   smell and split it.

## Before submission

- Fill the JAIR metadata in `main.tex`: `\JAIRAE{}` takes the assigned
  associate editor, and the volume, article, month and year come from the
  acceptance correspondence. `\JAIRTrack{}` stays empty unless the paper
  goes to a special track.
- Add `\received[accepted]{...}` next to `\received{...}` in
  `sections/00-frontmatter.tex` once the acceptance date is known.
- Add an `\orcid{}` to each author block in `sections/00-frontmatter.tex`.
  JAIR strongly recommends one per author, and none are filled yet. Get each
  one from its owner; do not look one up and guess.
- Answer the reproducibility checklist in
  `sections/15-appendix-reproducibility.tex` again if the paper's content
  changes. It is filled in, not left as `[yes/no]` placeholders.
- Delete the unused placeholder author slot at the end of the author list.
- Decide the final author order.
- Drop the `review` class option from `main.tex` for camera-ready, so the
  posted version carries no line numbers.
EOF

echo "==> Zipping"
rm -f "$OUT"
(cd "$STAGE" && zip -qr "$OUT" a2a-survey)

echo "==> Wrote $OUT"
unzip -l "$OUT" | tail -3
