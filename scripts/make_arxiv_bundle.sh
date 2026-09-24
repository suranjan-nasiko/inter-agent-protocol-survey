#!/usr/bin/env bash
#
# Build a self-contained arXiv submission bundle.
#
# arXiv differs from a local build in four ways that matter here:
#
#   1. It runs neither BibTeX nor biber. Whatever bibliography you get is the
#      one in main.bbl, so the .bbl must ship and must be current. We
#      regenerate it with biber in the staging tree rather than trusting the
#      repo copy. Note the paper is on biblatex now, not BibTeX: the .bbl is
#      a biblatex .bbl and pairs with the biblatex version that wrote it.
#   2. It compiles from a flat project root, so \addbibresource{../refs/...}
#      does not resolve. The path is rewritten to a sibling file.
#   3. jair.cls is not on arXiv's TeX tree, and neither are the three
#      biblatex support files the JAIR preamble names. All four ship in the
#      bundle. acmart itself is on arXiv, so it is not vendored.
#   4. Line numbers are a review artifact, not something to publish. The
#      `review` class option is dropped for the posted version.
#
# The bundle is verified before it is zipped: it is compiled from scratch in a
# clean directory with no biber run, exactly as arXiv will do it, and the
# build must produce a PDF with zero undefined references or citations.
#
# Usage: scripts/make_arxiv_bundle.sh [output.zip]

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$REPO/a2a-survey-arxiv.zip}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cd "$REPO"

command -v biber >/dev/null \
  || { echo "FAIL: biber not found. JAIR uses biblatex with the biber backend."
       echo "      Install it with: brew install biber"; exit 1; }

echo "==> Regenerating tables and figures from data/*.yaml"
make tables figures >/dev/null

echo "==> Staging submission tree"
BUNDLE="$STAGE/bundle"
mkdir -p "$BUNDLE"
cp -r manuscript/sections "$BUNDLE/"
cp -r manuscript/tables   "$BUNDLE/"
cp -r manuscript/figures  "$BUNDLE/"
cp manuscript/main.tex manuscript/preamble.tex "$BUNDLE/"
# The JAIR class and its biblatex support files are not on arXiv's TeX tree.
cp manuscript/jair.cls manuscript/acmauthoryear.bbx manuscript/acmauthoryear.cbx \
   manuscript/acmdatamodel.dbx "$BUNDLE/"
cp refs/references.bib "$BUNDLE/references.bib"

# arXiv compiles from the project root; ../refs/ does not exist there.
perl -pi -e 's|\\addbibresource\{\.\./refs/references\.bib\}|\\addbibresource{references.bib}|' \
  "$BUNDLE/main.tex"
grep -q '\\addbibresource{references.bib}' "$BUNDLE/main.tex" \
  || { echo "FAIL: bibliography path rewrite did not apply"; exit 1; }

# Line numbers are for reviewers, not for readers of the posted version.
perl -pi -e 's|\\documentclass\[manuscript, screen, review\]\{jair\}|\\documentclass[manuscript, screen]{jair}|' \
  "$BUNDLE/main.tex"
grep -q '\\documentclass\[manuscript, screen\]{jair}' "$BUNDLE/main.tex" \
  || { echo "FAIL: review option was not dropped"; exit 1; }

# A preprint must not display a venue or a publication date it does not have.
# main.tex gates all of that on \ifarxiv: the DOI, the JAIR reference-format
# block, the associate-editor line, the "Publication date" footer, and the
# venue name in the appendix heading. Flipping the switch here is what makes
# the posted PDF venue-neutral. See the comment block in main.tex.
perl -pi -e 's|^\\arxivfalse$|\\arxivtrue|' "$BUNDLE/main.tex"
grep -q '^\\arxivtrue$' "$BUNDLE/main.tex" \
  || { echo "FAIL: \\arxivtrue was not set; the bundle would claim a JAIR"
       echo "      volume, article number and publication date it does not have"
       exit 1; }

echo "==> Compiling in staging tree (with biber, to build a current .bbl)"
(
  cd "$BUNDLE"
  # Seed a trivial aux so acmart does not see TotPages=1 on pass 1. See the
  # long note in manuscript/.latexmkrc: with TotPages=1 the page-1 layout
  # shrinks enough to re-run acmart's affiliation check on consumed state,
  # which raises a spurious "No country present" ClassError.
  printf '\\relax \n' > main.aux
  pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1 || true
  biber main >/dev/null 2>&1
  pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1 || true
  pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1 || true
)
[ -s "$BUNDLE/main.bbl" ] || { echo "FAIL: no main.bbl produced"; exit 1; }

# Now prove it compiles the way arXiv will: no biber, .bbl taken as given.
echo "==> Verifying the arXiv build path (no biber run)"
VERIFY="$STAGE/verify"
mkdir -p "$VERIFY"
(cd "$BUNDLE" && tar cf - \
   main.tex preamble.tex main.bbl references.bib \
   jair.cls acmauthoryear.bbx acmauthoryear.cbx acmdatamodel.dbx \
   sections tables figures) \
  | (cd "$VERIFY" && tar xf -)
(
  cd "$VERIFY"
  printf '\\relax \n' > main.aux
  for _ in 1 2 3; do
    pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1 || true
  done
)
[ -s "$VERIFY/main.pdf" ] || { echo "FAIL: arXiv-path build produced no PDF"; exit 1; }

BAD=0
if grep -q "Citation.*undefined" "$VERIFY/main.log"; then
  echo "FAIL: undefined citations in the arXiv-path build"
  grep -n "Citation.*undefined" "$VERIFY/main.log" | head; BAD=1
fi
if grep -q "Reference.*undefined" "$VERIFY/main.log"; then
  echo "FAIL: undefined references in the arXiv-path build"
  grep -n "Reference.*undefined" "$VERIFY/main.log" | head; BAD=1
fi
if grep -q "^! " "$VERIFY/main.log"; then
  echo "FAIL: TeX errors in the arXiv-path build"
  grep -n "^! " "$VERIFY/main.log" | head; BAD=1
fi
[ "$BAD" = "0" ] || exit 1

# Prove the venue and date are gone from the rendered text, not merely gated in
# the source. A flag that silently fails to apply would otherwise ship a PDF
# claiming a JAIR volume, article number and publication date. Checked against
# the extracted text, which is what a reader and an arXiv moderator see.
if command -v pdftotext >/dev/null; then
  pdftotext "$VERIFY/main.pdf" "$STAGE/verify.txt" 2>/dev/null
  # Collapse all whitespace to single spaces first. The venue name is long
  # enough to wrap, and a line-wrapped occurrence is just as visible to a
  # reader as an unwrapped one, so a line-oriented grep would miss it.
  tr '\n' ' ' < "$STAGE/verify.txt" | tr -s '[:space:]' ' ' > "$STAGE/verify1.txt"
  for phrase in "Publication date" "JAIR Reference Format" \
                "JAIR Associate Editor" "Journal of Artificial Intelligence Research" \
                "10.1613/jair" "Received 14 September 2026" \
                "Manuscript submitted to ACM"; do
    if grep -qF "$phrase" "$STAGE/verify1.txt"; then
      echo "FAIL: the posted PDF still contains \"$phrase\""
      echo "      A preprint must not assert a venue or publication date."
      grep -oF -- "$phrase" "$STAGE/verify1.txt" | head -3
      exit 1
    fi
  done
  echo "    venue check: no JAIR reference block, editor line, venue name,"
  echo "                 DOI or publication date in the rendered text"
else
  echo "WARN: pdftotext not found; could not verify the venue strings are gone"
fi

PAGES="$(pdfinfo "$VERIFY/main.pdf" | awk '/^Pages:/ {print $2}')"
# biblatex .bbl: one \entry per reference, where BibTeX used \bibitem.
CITES="$(grep -c '^ *\\entry{' "$VERIFY/main.bbl")"
KEYS="$(grep -rhoE '\\cite[a-zA-Z]*\{[^}]*\}' \
          "$BUNDLE/main.tex" "$BUNDLE"/sections/*.tex "$BUNDLE"/tables/*.tex \
        | grep -oE '\{[^}]*\}' | tr -d '{}' | tr ',' '\n' | tr -d ' ' \
        | sort -u | grep -cv '^$')"
[ "$CITES" = "$KEYS" ] \
  || { echo "FAIL: $KEYS keys cited but $CITES in the bibliography"; exit 1; }

echo "    verified: $PAGES pages, $CITES references, no undefined refs or citations"

echo "==> Zipping submission files only"
SUB="$STAGE/sub"
mkdir -p "$SUB"
(cd "$BUNDLE" && tar cf - \
   main.tex preamble.tex main.bbl references.bib \
   jair.cls acmauthoryear.bbx acmauthoryear.cbx acmdatamodel.dbx \
   sections tables figures) \
  | (cd "$SUB" && tar xf -)

# arXiv rejects nothing here, but a stray .aux or .log wastes a review cycle.
find "$SUB" -type f \
  \( -name '*.aux' -o -name '*.log' -o -name '*.out' -o -name '*.blg' \
     -o -name '*.bcf' -o -name '*.run.xml' \
     -o -name '*.toc' -o -name '*.fls' -o -name '*.fdb_latexmk' \
     -o -name '*.synctex.gz' -o -name '.DS_Store' -o -name '*.cut' \) -delete

cat > "$SUB/00README.XXX" <<'EOF'
% arXiv processing directives.
%
% main.tex is the top-level file. The bibliography ships pre-built in
% main.bbl, because arXiv runs neither BibTeX nor biber; references.bib is
% included for provenance only and is not compiled. Note main.bbl is a
% biblatex .bbl, not a BibTeX one.
%
% jair.cls (the Journal of Artificial Intelligence Research class) and the
% three biblatex support files it needs, acmauthoryear.bbx, acmauthoryear.cbx
% and acmdatamodel.dbx, are included because they are not on the arXiv TeX
% tree. All four are unmodified copies from the official JAIR AuthorKit.
% acmart, which jair.cls extends, is taken from the arXiv TeX tree.
toplevelfile main.tex
EOF

rm -f "$OUT"
(cd "$SUB" && zip -qr "$OUT" .)

echo "==> Wrote $OUT"
unzip -l "$OUT"
