#!/usr/bin/env python3
"""
build_typst_draft.py: produce a draft markdown for the typst fallback build.

The manuscript source is LaTeX targeted at ACM acmart. When LaTeX is not
installed, we still want a working PDF. This script reads the section
.tex stubs, strips the ACM-specific commands, converts the LaTeX section
structure to markdown, resolves \\ref{} cross-references against a
two-pass label registry, and writes `build/draft.md` for pandoc to
render via typst.

Two-pass design:
  1. scan_labels() walks every section file in order and assigns numbers
     to each \\label{} based on the structural element it attaches to
     (section, subsection, subsubsection, figure environment, or
     \\input-included table).
  2. latex_to_md() converts a single section file, consulting the
     registry to expand \\ref{X} into the assigned number.

Limitations (acceptable for a draft):
  - Loses ACM-specific layout (two-column, ACM-Reference-Format bib style).
  - LaTeX-only macros (e.g. \\rubricAxis, \\protocolBadge) are passed
    through as bold italics.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANUSCRIPT = REPO / "manuscript"
SECTIONS_DIR = MANUSCRIPT / "sections"
OUT = REPO / "build" / "draft.md"

# Order of section files matches manuscript/main.tex.
SECTION_FILES = [
    "00-frontmatter.tex",
    "01-introduction.tex",
    "02-background.tex",
    "03-taxonomy.tex",
    "04-rubric.tex",
    "05-industry-protocols.tex",
    "06-emerging-protocols.tex",
    "07-comparison.tex",
    "08-security.tex",
    "09-semantic-interop.tex",
    "10-industry-adoption.tex",
    "11-governance.tex",
    "12-open-problems.tex",
    "13-proposals.tex",
    "14-conclusion.tex",
]

# Drop these top-level LaTeX commands entirely (with their argument).
ACM_ONLY = {
    "title", "author", "affiliation", "email", "maketitle",
    "keywords", "ccsxml", "ccsdesc",
}


# --------------------------------------------------------------------------
# Pass 1: label registry
# --------------------------------------------------------------------------

def _resolve_input_path(target_rel: str) -> Path | None:
    if not target_rel.endswith(".tex"):
        target_rel += ".tex"
    candidates = [
        (SECTIONS_DIR / target_rel).resolve(),
        (MANUSCRIPT / target_rel).resolve(),
    ]
    return next((p for p in candidates if p.is_file()), None)


def scan_labels(section_files: list[Path]) -> dict[str, str]:
    """Walk every section in order and build the label-to-number map.

    Returns a dict mapping each label name to the human-readable number
    of the structural element it attaches to (e.g. "3.2", "Figure 1",
    "Table 1"). For section labels the returned value is just the number;
    callers prefix with "§" or "Section" as appropriate.
    """
    sec = [0, 0, 0]  # section, subsection, subsubsection counters
    fig_n = 0
    tab_n = 0
    labels: dict[str, str] = {}

    # Token alternatives processed in left-to-right order across the
    # concatenated source. The figure environment is matched as a whole
    # block so we can pull the inner \label{} out without conflating with
    # the section-level label.
    token_re = re.compile(
        r"\\section\*?\{[^}]*\}\s*(?:\\label\{([^}]+)\})?|"
        r"\\subsection\*?\{[^}]*\}\s*(?:\\label\{([^}]+)\})?|"
        r"\\subsubsection\*?\{[^}]*\}\s*(?:\\label\{([^}]+)\})?|"
        r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}|"
        r"\\begin\{table\*?\}(.*?)\\end\{table\*?\}|"
        r"\\input\{([^}]+)\}",
        re.DOTALL,
    )

    current_section_label: str | None = None

    for path in section_files:
        if not path.is_file():
            continue
        text = path.read_text()
        text = "\n".join(
            ln for ln in text.splitlines() if not ln.lstrip().startswith("%")
        )
        for m in token_re.finditer(text):
            head = m.group(0)
            if head.startswith("\\section"):
                sec = [sec[0] + 1, 0, 0]
                num = f"{sec[0]}"
                if m.group(1):
                    labels[m.group(1)] = num
                current_section_label = num
            elif head.startswith("\\subsection"):
                sec[1] += 1
                sec[2] = 0
                num = f"{sec[0]}.{sec[1]}"
                if m.group(2):
                    labels[m.group(2)] = num
                current_section_label = num
            elif head.startswith("\\subsubsection"):
                sec[2] += 1
                num = f"{sec[0]}.{sec[1]}.{sec[2]}"
                if m.group(3):
                    labels[m.group(3)] = num
                current_section_label = num
            elif head.startswith("\\begin{figure"):
                fig_n += 1
                block = m.group(4)
                for lbl in re.findall(r"\\label\{([^}]+)\}", block):
                    labels[lbl] = str(fig_n)
            elif head.startswith("\\begin{table"):
                tab_n += 1
                block = m.group(5)
                for lbl in re.findall(r"\\label\{([^}]+)\}", block):
                    labels[lbl] = str(tab_n)
            elif head.startswith("\\input"):
                target_rel = m.group(6).strip()
                if "table" not in target_rel.lower():
                    continue
                target = _resolve_input_path(target_rel)
                if target is None:
                    continue
                tab_n += 1
                content = target.read_text()
                for lbl in re.findall(r"\\label\{([^}]+)\}", content):
                    labels[lbl] = str(tab_n)
        # After consuming all structural tokens, any leftover \label{} on
        # a line of its own (no immediate section header) attaches to the
        # nearest enclosing section.
        for lbl in re.findall(r"\\label\{([^}]+)\}", text):
            if lbl not in labels and current_section_label is not None:
                labels[lbl] = current_section_label

    return labels


# --------------------------------------------------------------------------
# Pass 2: per-file conversion (uses the label registry)
# --------------------------------------------------------------------------

def _strip_inline_macros(cell: str) -> str:
    cell = re.sub(r"\\textbf\{([^}]+)\}", r"**\1**", cell)
    cell = re.sub(r"\\textit\{([^}]+)\}", r"*\1*", cell)
    cell = re.sub(r"\\emph\{([^}]+)\}", r"*\1*", cell)
    cell = re.sub(r"\\texttt\{([^}]+)\}", r"`\1`", cell)
    cell = re.sub(r"\\score\{([^}]+)\}", r"\1", cell)
    cell = re.sub(r"\\scriptsize\b", "", cell)
    cell = re.sub(r"\\footnotesize\b", "", cell)
    cell = re.sub(r"\\small\b", "", cell)
    cell = re.sub(r"\\linebreak\b\s*", " ", cell)
    cell = re.sub(r"\\S\b\s*", "§", cell)
    cell = cell.replace("---", "-").replace("--", "-")
    cell = re.sub(r"\\&", "&", cell)
    return cell.strip()


def tabular_to_md(tex: str) -> str:
    # Brace-balanced column-spec capture: column specs may contain p{2.4cm},
    # m{3in}, b{1.5cm}, etc., where the inner braces are not table-body braces.
    # Bare `[^}]*` here would stop at the first inner `}` and the rest of the
    # column spec would leak into the table body.
    m = re.search(
        r"\\begin\{tabular\}\{((?:[^{}]|\{[^}]*\})*)\}(.*?)\\end\{tabular\}",
        tex, re.DOTALL)
    if not m:
        return tex
    body = m.group(2)
    body = re.sub(r"\\toprule|\\midrule|\\bottomrule", "", body)
    body = re.sub(r"\\cmidrule\{[^}]*\}", "", body)
    rows_raw = [r.strip() for r in body.split(r"\\") if r.strip()]
    # A row may begin with a LaTeX vertical-space specifier left over from
    # the row terminator (e.g. `\\[6pt]`), which our `\\`-split deposits as
    # `[6pt]` at the head of the next row. Strip such leading bracket
    # arguments before splitting into cells.
    rows_raw = [re.sub(r"^\s*\[[^\]]*\]\s*", "", r) for r in rows_raw]
    rows_raw = [r for r in rows_raw if r.strip()]
    # Split cells on `&` but NOT on escaped `\&` (used in cell labels like
    # "Commerce \& payments"). The negative lookbehind preserves the escape
    # so _strip_inline_macros can decode it to "&".
    rows = [
        [_strip_inline_macros(c) for c in re.split(r"(?<!\\)&", r)]
        for r in rows_raw
    ]
    if not rows:
        return tex
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    header = rows[0]
    sep = ["---"] * ncols
    out = ["| " + " | ".join(header) + " |",
           "| " + " | ".join(sep) + " |"]
    for row in rows[1:]:
        out.append("| " + " | ".join(row) + " |")
    return "\n" + "\n".join(out) + "\n"


def make_resolve_input(tab_counter: list[int], labels: dict[str, str]):
    def resolve_input(match: "re.Match[str]") -> str:
        target_rel = match.group(1).strip()
        target = _resolve_input_path(target_rel)
        if target is None:
            return (f"\n> *[Table/figure include: `{match.group(1)}`: "
                    f"missing on disk]*\n")
        raw = target.read_text()
        # Brace-balanced caption extraction. The inner alternation matches
        # either a non-brace char or a single-nested `{...}` group, so an
        # internal \textit{X} or \ref{Y} doesn't terminate the caption early.
        caption_m = re.search(r"\\caption\{((?:[^{}]|\{[^}]*\})*)\}",
                              raw, re.DOTALL)
        caption = caption_m.group(1).strip() if caption_m else None
        if caption:
            caption = re.sub(r"\s+", " ", caption)
            caption = _strip_inline_macros(caption)
        is_table = "table" in target_rel.lower()
        if is_table:
            tab_counter[0] += 1
            n = tab_counter[0]
            md_table = tabular_to_md(raw)
            tag = f"**Table {n}.** "
            cap_block = f"\n\n{tag}{caption or ''}\n" if caption or True else ""
            return f"\n{md_table}\n{cap_block}"
        return f"\n{tabular_to_md(raw)}\n"
    return resolve_input


def make_convert_table_block(tab_counter: list[int]):
    """Inline \\begin{table*?}…\\end{table*?} → markdown pipe table + caption.

    Authored tables (as opposed to \\input{} table includes) appear directly
    in section sources; this converter mirrors resolve_input's tabular-to-md
    behaviour for that case. The counter must be the same shared counter
    that resolve_input increments so the numbering stays consistent.
    """
    def convert_table_block(match: "re.Match[str]") -> str:
        block = match.group(0)
        cap_m = re.search(r"\\caption\{((?:[^{}]|\{[^}]*\})*)\}", block,
                          re.DOTALL)
        caption = cap_m.group(1).strip() if cap_m else None
        if caption:
            caption = re.sub(r"\s+", " ", caption)
            caption = _strip_inline_macros(caption)
        tab_counter[0] += 1
        n = tab_counter[0]
        md_table = tabular_to_md(block)
        tag = f"**Table {n}.** "
        cap_block = f"\n\n{tag}{caption or ''}\n"
        return f"\n{md_table}\n{cap_block}"
    return convert_table_block


def make_convert_figure_block(fig_counter: list[int]):
    def convert_figure_block(match: "re.Match[str]") -> str:
        block = match.group(0)
        img_m = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", block)
        cap_m = re.search(r"\\caption\{((?:[^{}]|\{[^}]*\})*)\}", block,
                          re.DOTALL)
        caption = cap_m.group(1).strip() if cap_m else ""
        caption = re.sub(r"\s+", " ", caption)
        caption = _strip_inline_macros(caption)
        fig_counter[0] += 1
        n = fig_counter[0]
        if img_m:
            img_rel = img_m.group(1).strip()
            img_path = (MANUSCRIPT / img_rel).resolve()
            # Pandoc + typst draws the caption from the markdown image
            # alt-text and prefixes "Figure N:" automatically; we override
            # by writing the prefix into the caption so it always reads as
            # "Figure N. ..." with the survey's preferred punctuation.
            return (f"\n\n![**Figure {n}.** {caption}]"
                    f"({img_path})\n\n")
        # No image: emit a labelled text block (placeholder figures).
        # Use brace-balanced caption stripping so a nested \textit{} or
        # \ref{} doesn't terminate the match prematurely.
        body = re.sub(r"\\caption\{(?:[^{}]|\{[^}]*\})*\}", "", block,
                      flags=re.DOTALL)
        # Match \begin{figure}, optionally followed by a bracketed
        # placement argument, OR \end{figure}. The optional argument is
        # *grouped* so it only fires when the brackets are actually
        # present: earlier a stray \[?[^\]]*\]? alternation greedy-
        # matched the entire body when no [ existed.
        body = re.sub(
            r"\\begin\{figure\*?\}(?:\[[^\]]*\])?|\\end\{figure\*?\}",
            "", body)
        body = re.sub(r"\\label\{[^}]+\}", "", body)
        body = body.strip()
        return f"\n\n> {body}\n\n**Figure {n}.** {caption}\n\n"
    return convert_figure_block


def latex_to_md(tex: str,
                labels: dict[str, str],
                fig_counter: list[int],
                tab_counter: list[int]) -> str:
    lines = [ln for ln in tex.splitlines() if not ln.lstrip().startswith("%")]
    body = "\n".join(lines)

    # Em/en-dash replacements run early so they don't mangle the `---`
    # separator row injected by table includes.
    body = body.replace("---", "-")
    body = body.replace("--", "-")

    # Resolve \input{...}, inline table*, and figure environments.
    body = re.sub(r"\\input\{([^}]+)\}",
                  make_resolve_input(tab_counter, labels), body)
    body = re.sub(r"\\begin\{table\*?\}.*?\\end\{table\*?\}",
                  make_convert_table_block(tab_counter), body, flags=re.DOTALL)
    body = re.sub(r"\\begin\{figure\*?\}.*?\\end\{figure\*?\}",
                  make_convert_figure_block(fig_counter), body, flags=re.DOTALL)

    # Cross-references: resolve \ref / \Cref / \autoref against the registry.
    def resolve_ref(m: "re.Match[str]") -> str:
        lbl = m.group(1).strip()
        return labels.get(lbl, f"?{lbl}?")
    body = re.sub(r"\\(?:ref|Cref|autoref|cref)\{([^}]+)\}", resolve_ref, body)
    body = re.sub(r"\\pageref\{[^}]+\}", "", body)

    # Headings.
    body = re.sub(r"\\section\*?\{([^}]*)\}", r"\n## \1\n", body)
    body = re.sub(r"\\subsection\*?\{([^}]*)\}", r"\n### \1\n", body)
    body = re.sub(r"\\subsubsection\*?\{([^}]*)\}", r"\n#### \1\n", body)
    # Brace-balanced capture: paragraph headings often nest \texttt{X}
    # (and occasionally \emph{}, \cite{}, etc.). A bare `[^}]*` would stop
    # at the first inner `}` and amputate the heading there, producing
    # half-bold markdown that breaks the rendered title (the +suffix /
    # <org> / <workspace> headings in OWA's URI-syntax subsection all
    # tripped this).
    body = re.sub(
        r"\\paragraph\{((?:[^{}]|\{[^}]*\})*)\}",
        lambda m: f"\n**{m.group(1).rstrip('.')}**",
        body,
    )

    # quote environments → markdown blockquote.
    # Without this handler, pandoc sees raw \begin{quote} as LaTeX it
    # cannot represent in the typst output target, drops the whole
    # environment, and the wrapped content vanishes silently: every
    # \texttt{} URI example in OWA's §13.1.6 tripped this.
    def _quote_to_md(m: "re.Match[str]") -> str:
        inner = m.group(1).strip()
        # Prefix every line with `> ` so pandoc parses it as a blockquote.
        return "\n\n" + "\n".join(f"> {ln}" for ln in inner.splitlines()) + "\n\n"
    body = re.sub(
        r"\\begin\{quote\}(.*?)\\end\{quote\}",
        _quote_to_md,
        body,
        flags=re.DOTALL,
    )

    # description environments → bullet-style paragraphs.
    # \begin{description}\item[X] Y\item[A] B\end{description} →
    # - **X** Y\n- **A** B\n
    body = re.sub(r"\\begin\{description\}\s*", "\n", body)
    body = re.sub(r"\\end\{description\}\s*", "\n", body)
    body = re.sub(
        r"\\item\[((?:[^\[\]]|\[[^\]]*\])*)\]\s*",
        r"\n- **\1** ",
        body,
    )

    # enumerate + itemize environments → markdown bulleted lists.
    # Without this, pandoc's typst engine silently drops the entire block
    # (same failure mode as \begin{quote} above): the "Two tightenings"
    # enumerate in §13 vanished from the rendered PDF until this handler
    # was added. Note the semantics-flattening: enumerate becomes bullets
    # rather than a numbered list, which is acceptable for a draft.
    body = re.sub(r"\\begin\{enumerate\}\s*", "\n\n", body)
    body = re.sub(r"\\end\{enumerate\}\s*", "\n\n", body)
    body = re.sub(r"\\begin\{itemize\}\s*", "\n\n", body)
    body = re.sub(r"\\end\{itemize\}\s*", "\n\n", body)
    # Bare \item (not \item[X], handled above) → bullet marker.
    body = re.sub(r"\\item\s+", "\n- ", body)

    # Mark LaTeX page-break commands with a sentinel; the real raw-typst
    # fenced block is substituted in below, *after* the ``→" replacement,
    # so the backtick fence is not mangled.
    body = re.sub(r"\\clearpage\b\s*", "\n\n@@TYPST_PAGEBREAK@@\n\n", body)
    body = re.sub(r"\\newpage\b\s*", "\n\n@@TYPST_PAGEBREAK@@\n\n", body)
    body = re.sub(r"\\pagebreak(?:\[[0-9]+\])?\s*", "\n\n@@TYPST_PAGEBREAK@@\n\n", body)

    # Drop labels and acm-only metadata commands.
    body = re.sub(r"\\label\{[^}]*\}", "", body)
    body = re.sub(r"\\maketitle", "", body)
    for cmd in ACM_ONLY:
        body = re.sub(
            rf"\\{cmd}\s*\{{[^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)*\}}",
            "",
            body,
            flags=re.DOTALL,
        )
        body = re.sub(rf"\\{cmd}\b\s*\{{[^}}]*\}}", "", body, flags=re.DOTALL)

    # Abstract.
    body = re.sub(r"\\begin\{abstract\}", "\n**Abstract.** ", body)
    body = re.sub(r"\\end\{abstract\}", "\n", body)

    # Acknowledgments: acmart's acks environment. In the LaTeX build acmart
    # styles this as an unnumbered section; in the typst fallback we emit a
    # plain heading so pandoc/citeproc still resolves any \cite{} keys inside.
    body = re.sub(r"\\begin\{acks\}", "\n### Acknowledgments\n\n", body)
    body = re.sub(r"\\end\{acks\}", "\n", body)

    # Inline LaTeX formatting.
    body = re.sub(r"\\textbf\{([^}]+)\}", r"**\1**", body)
    body = re.sub(r"\\textit\{([^}]+)\}", r"*\1*", body)
    body = re.sub(r"\\emph\{([^}]+)\}", r"*\1*", body)
    body = re.sub(r"\\texttt\{([^}]+)\}", r"`\1`", body)
    body = re.sub(r"\\textsc\{([^}]+)\}", r"\1", body)
    body = re.sub(r"\\rubricAxis\{([^}]+)\}", r"***\1***", body)
    body = re.sub(r"\\protocolBadge\{([^}]+)\}", r"**\1**", body)
    body = re.sub(r"\\score\{([^}]+)\}", r"**\1**", body)
    # \cite{a, b, c} must become [@a; @b; @c] for pandoc citeproc to
    # resolve all keys: the comma-separated form leaves keys after the
    # first as raw text in the bibliography output.
    def _cite_to_pandoc(m: "re.Match[str]") -> str:
        keys = [k.strip() for k in m.group(1).split(",") if k.strip()]
        return "[" + "; ".join(f"@{k}" for k in keys) + "]"
    body = re.sub(r"\\cite\{([^}]+)\}", _cite_to_pandoc, body)
    body = re.sub(r"\\noindent\b\s*", "", body)
    body = re.sub(r"\\S\b\s*", "§", body)

    # Special characters and arrows.
    body = body.replace("\\&", "&")
    body = body.replace("\\#", "#")
    body = body.replace("\\_", "_")
    body = body.replace("``", "\"").replace("''", "\"")
    body = re.sub(r"\\\((.*?)\\\)", r"\1", body)
    body = body.replace("\\rightarrow", "→").replace("\\leftarrow", "←")
    body = body.replace("\\(", "").replace("\\)", "")
    body = re.sub(r"~", " ", body)  # LaTeX non-breaking space

    # Substitute page-break sentinels with the raw-typst fenced block.
    # This runs *after* the ``→" replacement so the backtick fence survives.
    body = body.replace(
        "@@TYPST_PAGEBREAK@@",
        "```{=typst}\n#pagebreak()\n```",
    )

    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip() + "\n"


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    section_paths = [SECTIONS_DIR / name for name in SECTION_FILES]
    labels = scan_labels(section_paths)

    out_lines = [
        "---",
        "title: A Rubric-Based Survey of Inter-Agent Protocols",
        "subtitle: Industry Standards, Security Posture, Open Problems, and Three Co-Designed Protocol Extensions",
        "author: Suranjan Goswami (Nasiko Labs)",
        "date: 2026-Q1",
        "---",
        "",
        # Suppress typst's default figure numbering so the script-emitted
        # "**Figure N.** caption" prefix is the authoritative source. Without
        # this, captions render as "Figure 1: Figure 2. Rubric heatmap…".
        # Shrink table text so the wide rubric matrix fits on one page.
        "```{=typst}",
        "#set figure(numbering: none)",
        "#show table: set text(size: 6pt)",
        "#set table(inset: 3pt)",
        "```",
        "",
    ]

    fig_counter = [0]
    tab_counter = [0]

    for path in section_paths:
        if not path.is_file():
            print(f"warn: {path.name} missing: skipping", file=sys.stderr)
            continue
        out_lines.append(
            latex_to_md(path.read_text(), labels, fig_counter, tab_counter)
        )
        out_lines.append("")

    # Append a header so citeproc's auto-generated bibliography is anchored
    # under a numbered "## References" heading rather than floating loose.
    out_lines.append("")
    out_lines.append("## References")
    out_lines.append("")

    OUT.write_text("\n".join(out_lines))
    print(f"Wrote {OUT.relative_to(REPO)} "
          f"({len(SECTION_FILES)} section files, "
          f"{len(labels)} labels, "
          f"{fig_counter[0]} figures, {tab_counter[0]} tables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
