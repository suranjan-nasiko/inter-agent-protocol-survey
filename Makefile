# A Rubric-Based Survey of Inter-Agent Protocols, build entry points.
#
# Two PDF paths:
#   pdf-latex   production path; official JAIR class; needs BasicTeX/MacTeX
#               plus biber, because JAIR uses biblatex with the biber backend
#   pdf-typst   fallback; pandoc + typst; no LaTeX install needed
#
# Generated artifacts (tables, figures) are checked out of data/*.yaml
# by scripts under scripts/. Edit YAML, not the generated files.

PYTHON ?= python3
PANDOC ?= pandoc

MANUSCRIPT := manuscript/main.tex
TABLES     := manuscript/tables/table1-rubric-matrix.tex \
              manuscript/tables/table3-threat-surface.tex \
              manuscript/tables/table4-industry-adoption.tex \
              manuscript/tables/table5-governance-license.tex \
              manuscript/tables/table6-severity-coverage.tex
FIGURES    := manuscript/figures/fig5-heatmap.pdf manuscript/figures/fig6-radar.pdf \
              manuscript/figures/fig-taxonomy.pdf

.DEFAULT_GOAL := help

.PHONY: help pdf pdf-latex pdf-typst tables figures clean watch overleaf arxiv check-dashes check-scores check-biber check

help:
	@echo "make pdf-latex   # JAIR build (requires LaTeX install + biber)"
	@echo "make pdf-typst   # pandoc+typst fallback (no LaTeX needed)"
	@echo "make tables      # regenerate Tables 1/3/4/5/6 from data/"
	@echo "make figures     # regenerate Figures 5/6 from data/"
	@echo "make clean       # remove build artifacts"
	@echo "make watch       # latexmk -pvc continuous build"
	@echo "make overleaf    # zip a self-contained Overleaf upload bundle"
	@echo "make arxiv       # zip a verified arXiv submission bundle"
	@echo "make check-dashes # fail if any em/en dash slipped into the prose"
	@echo "make check-scores # fail if Axis 8 counts disagree with the threat matrix"
	@echo "make check       # both checks"

pdf: pdf-latex

# latexmk picks up manuscript/.latexmkrc, which tells it to run biber and
# works around an acmart cold-build error. Read the note in that file before
# changing this line.
pdf-latex: tables figures check-biber
	cd manuscript && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

# JAIR uses biblatex with the biber backend, so a missing biber is a hard stop,
# not a degraded build: bibtex cannot read the .bcf file biblatex writes.
check-biber:
	@command -v biber >/dev/null || { \
	  echo "biber not found. JAIR uses biblatex with the biber backend."; \
	  echo "Install it with: brew install biber"; exit 1; }

watch:
	cd manuscript && latexmk -pdf -pvc -interaction=nonstopmode main.tex

pdf-typst:
	$(PYTHON) scripts/build_typst_draft.py
	$(PANDOC) build/draft.md \
		--pdf-engine=typst \
		-V papersize=a4 \
		-V margin-x=2cm \
		-V margin-y=2cm \
		--toc --toc-depth=3 \
		--number-sections \
		--shift-heading-level-by=-1 \
		--bibliography=refs/references.bib \
		--citeproc \
		-o a2a-survey-draft.pdf
	@echo "Wrote a2a-survey-draft.pdf"

tables: check-scores $(TABLES)

manuscript/tables/table1-rubric-matrix.tex: data/protocol-scores.yaml scripts/gen_table1.py
	$(PYTHON) scripts/gen_table1.py

manuscript/tables/table3-threat-surface.tex: data/threat-coverage.yaml scripts/gen_table3.py
	$(PYTHON) scripts/gen_table3.py

manuscript/tables/table4-industry-adoption.tex: data/industry-adoption.yaml scripts/gen_table4.py
	$(PYTHON) scripts/gen_table4.py

manuscript/tables/table5-governance-license.tex: data/protocol-scores.yaml scripts/gen_table5.py
	$(PYTHON) scripts/gen_table5.py

manuscript/tables/table6-severity-coverage.tex: data/threat-coverage.yaml scripts/gen_table6.py
	$(PYTHON) scripts/gen_table6.py

figures: $(FIGURES)

manuscript/figures/fig5-heatmap.pdf: data/protocol-scores.yaml scripts/gen_heatmap.py
	$(PYTHON) scripts/gen_heatmap.py

manuscript/figures/fig6-radar.pdf: data/protocol-scores.yaml scripts/gen_radar.py
	$(PYTHON) scripts/gen_radar.py

manuscript/figures/fig-taxonomy.pdf: data/protocol-scores.yaml scripts/gen_taxonomy.py
	$(PYTHON) scripts/gen_taxonomy.py

overleaf: tables figures check-biber
	scripts/make_overleaf_bundle.sh

# arXiv runs neither BibTeX nor biber, so the bundle ships a prebuilt main.bbl
# (a biblatex one). The script compiles the staged tree the way arXiv will,
# with no biber run, and fails if the reference count or the
# undefined-reference count is wrong. It also vendors jair.cls and the three
# biblatex support files, which are not on the arXiv TeX tree, and drops the
# `review` class option so the posted PDF carries no line numbers.
arxiv: tables figures check-biber
	scripts/make_arxiv_bundle.sh

# House style: no em-dashes, en-dashes, or double hyphens anywhere in the
# manuscript source or the bib. Numeric ranges are written "X to Y".
check-dashes:
	@fail=0; \
	for f in manuscript/main.tex manuscript/preamble.tex \
	         manuscript/sections/*.tex manuscript/tables/*.tex \
	         refs/references.bib; do \
	  if grep -q -- '---' "$$f" || grep -qE '[^-]--[^-]' "$$f" \
	     || grep -q '—' "$$f" || grep -q '–' "$$f"; then \
	    echo "DASH VIOLATION: $$f"; \
	    grep -n -- '---' "$$f" || true; \
	    grep -nE '[^-]--[^-]' "$$f" || true; \
	    grep -n '—' "$$f" || true; \
	    grep -n '–' "$$f" || true; \
	    fail=1; \
	  fi; \
	done; \
	if [ "$$fail" = "1" ]; then \
	  echo "check-dashes FAILED"; exit 1; \
	else \
	  echo "check-dashes passed: no em/en dashes in manuscript source or bib"; \
	fi

# Axis 8 is a count over the threat matrix, so it can drift away from the
# matrix without anything failing. It did once. This is the guard.
check-scores:
	@$(PYTHON) scripts/check_scores.py

check: check-dashes check-scores

clean:
	cd manuscript && latexmk -C 2>/dev/null || true
	rm -rf build/
	rm -f a2a-survey-draft.pdf
	find . -name '*.aux' -delete
	find . -name '*.log' -delete
	find . -name '*.out' -delete
	find . -name '*.bbl' -delete
	find . -name '*.blg' -delete
	find . -name '*.bcf' -delete
	find . -name '*.run.xml' -delete
	find . -name '*.bcf-SAVE-ERROR' -delete
	find . -name '*.bbl-SAVE-ERROR' -delete
	find . -name '*.fdb_latexmk' -delete
	find . -name '*.fls' -delete
	find . -name '*.synctex.gz' -delete
	find . -name '*.toc' -delete
