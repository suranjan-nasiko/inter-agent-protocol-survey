# A Rubric-Based Survey of Inter-Agent Protocols

Companion repository for the survey by Suranjan Goswami, Manu Ghulyani, Karan
Bharadwaj, Roland R. Rodriguez Jr., Faouzi El Yagoubi, Alejandro Quintero, and
Ranwa Al Mallah.

The survey applies one ten-axis rubric to thirteen inter-agent protocols across
three layers: tool-binding, peer-messaging, and commerce settlement. Eight are
scored on the rubric (A2A, MCP, ANP, IBM ACP, AGNTCY/SLIM, Coral, LOKA, ACNBP).
Five commerce-settlement protocols are surveyed but not scored (AP2, Visa TAP,
Mastercard Agent Pay, ERC-8004, UCP), and the paper states why. The declared
source cutoff is 2026-Q1.

This repository holds the rubric scores as data, the scripts that turn them into
the paper's tables and figures, and the LaTeX source of the paper.

## What is here

```
data/
  protocol-scores.yaml      rubric scores: one entry per protocol and axis,
                            each with a score, an evidence sentence, and a
                            citation key. Source of truth for Table 1 and
                            Figures 5 and 6.
  threat-coverage.yaml      the twelve-class threat matrix behind Axis 8
  industry-adoption.yaml    documented production deployments by vertical
scripts/
  gen_table*.py             YAML to LaTeX tables
  gen_heatmap.py            YAML to Figure 5
  gen_radar.py              YAML to Figure 6
  gen_taxonomy.py           the three-layer taxonomy figure
  check_scores.py           fails the build if a count in the prose or the
                            YAML disagrees with the score matrix
manuscript/                 LaTeX source; sections/ holds one file per section
refs/references.bib         bibliography
```

## Using the data

Every score names the specification version it was read against
(`spec_version`) and the date it was retrieved (`retrieved`). Protocols move
faster than a review cycle, so reproducing a score means reading the version the
entry names, not the current one. To score a ninth protocol, add an entry with
the same fields and run `make tables figures`.

Every score is one rater's judgement. The paper states what agreement evidence
that does and does not provide. Corrections are welcome as issues or pull
requests; please cite the specification section the correction rests on.

## Building

Requires Python 3 with PyYAML and matplotlib, a TeX distribution with the
`acmart` class, and `biber`.

```sh
make check       # dash check and score-consistency check
make tables      # regenerate manuscript/tables/ from data/
make figures     # regenerate manuscript/figures/ from data/
make pdf-latex   # full build
```

If your default `python3` lacks PyYAML, pass an interpreter that has it:
`make check PYTHON=/path/to/python3`.

Generated tables and figures are not hand-edited. Change the YAML and rerun.

On macOS:

```sh
brew install --cask basictex
sudo tlmgr update --self && sudo tlmgr install acmart latexmk booktabs colortbl xcolor tikz pgfplots microtype longtable
brew install biber
```

`manuscript/.latexmkrc` is a build fix, not a style change. On a cold build
latexmk seeds a stub `main.aux` that makes `acmart` raise a spurious "No country
present for an affiliation" error. The file drops that one line from the stub.

## The JAIR class files

`manuscript/jair.cls`, `acmauthoryear.bbx`, `acmauthoryear.cbx`, and
`acmdatamodel.dbx` come from the Journal of Artificial Intelligence Research
AuthorKit (https://www.jair.org). They are copied unmodified, only so that
`make pdf` works from a fresh clone. They are not part of this work and are
not covered by the MIT or CC BY 4.0 licenses above. JAIR's own terms apply to
them. For the current version, download the AuthorKit from JAIR.

## License

Code under `scripts/` and the `Makefile` are released under the MIT License
(`LICENSE`). The data under `data/` is released under Creative Commons
Attribution 4.0 (`data/LICENSE`). The paper text under `manuscript/` is
copyright its authors.

## Citing

If you use the rubric or the data, please cite the paper. A citation entry will
be added here once the preprint identifier is assigned.
