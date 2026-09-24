#!/usr/bin/env python3
"""
check_scores.py: fail if the two score files disagree with each other or with
the rubric definitions.

Axis 8 is a count, not a judgement, so it can silently drift away from the
matrix it is supposed to summarise. It did: a2a, mcp, coral, and loka all
carried counts that included `partial` cells, which the Axis 8 definition in
manuscript/sections/04-rubric.tex excludes. Nothing failed, because nothing
checked. This script is that check.

Run via `make check-scores`, or as part of `make tables`.

Checks:
  1. Every protocol in threat-coverage.yaml has all twelve threat classes,
     scored with a known coverage token.
  2. axis_8.score equals the count of `addressed` cells for that protocol.
     Not addressed-plus-partial, and not addressed-plus-na.
  3. Every rubric-scored protocol appears in the threat matrix, and vice versa.
  4. Ordinal axes stay inside 0 to 3, and Axis 8 inside 0 to 12.
  5. Prose in manuscript/sections/ that writes an Axis 8 count for a named
     protocol agrees with the YAML. Section 8 carried six counts that were
     wrong for months, two of them wrong before the partial-counting bug
     existed, because no check read the prose.
  6. The severity block covers all twelve threat classes exactly once, with a
     known band and the weight that band declares. The severity-weighted view
     of Table 6 is only as trustworthy as this block, and a band added without
     a weight would silently drop a threat out of the denominator.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML missing: install with: pip install pyyaml")

REPO = Path(__file__).resolve().parent.parent
SCORES_PATH = REPO / "data" / "protocol-scores.yaml"
COVERAGE_PATH = REPO / "data" / "threat-coverage.yaml"

THREATS = {
    "prompt_injection_protocol_boundary",
    "agent_impersonation",
    "message_replay",
    "capability_escalation",
    "delegation_token_theft",
    "registry_poisoning",
    "agentcard_supply_chain",
    "message_tampering",
    "side_channel_privacy_leak",
    "denial_of_service",
    "cross_agent_privilege_confusion",
    "audit_log_tampering",
}

COVERAGE_TOKENS = {"addressed", "partial", "not_addressed", "na"}

# Bands and the weight each one carries. The weight lives in the YAML too, per
# threat, so that a reader can see it without reading code; this map is what
# makes disagreement between the two an error rather than a silent reweighting.
SEVERITY_WEIGHTS = {"critical": 3, "high": 2, "moderate": 1}

ORDINAL_AXES = (1, 2, 3, 5, 6, 7, 9)

SECTIONS_DIR = REPO / "manuscript" / "sections"

# Display names as they appear in prose, mapped to their YAML key.
PROSE_NAMES = {
    "A2A": "a2a",
    "MCP": "mcp",
    "ACP": "acp",
    "AGNTCY": "agntcy",
    "ANP": "anp",
    "Coral": "coral",
    "LOKA": "loka",
    "ACNBP": "acnbp",
}

# Which protocol a \subsection is about, so that "Axis 8 = 6 of 12" inside the
# AGNTCY subsection is checked against AGNTCY even though the name is 70 lines
# up. Matched as a substring of the heading text.
SUBSECTION_OWNER = (
    ("Google A2A", "a2a"),
    ("Model Context Protocol", "mcp"),
    ("IBM ACP", "acp"),
    ("AGNTCY", "agntcy"),
    ("Agent Network Protocol", "anp"),
    ("Coral Protocol", "coral"),
    ("LOKA", "loka"),
    ("Agent Capability Negotiation", "acnbp"),
)

_NAMES = "|".join(PROSE_NAMES)

# Counts are written several ways across the manuscript, including spelled out.
NUMERALS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12,
}
_COUNT = r"(?:\d{1,2}|%s)" % "|".join(NUMERALS)

# Two families. The first needs an explicit protocol name near the count. The
# second matches a bare count and is resolved against the enclosing
# subsection, which is how the per-protocol score lists in sections 5 and 6
# are written.
NAMED_PATTERNS = (
    re.compile(
        r"\b(?P<name>%s)(?:'s)?\b[^.;:]{0,32}?(?P<count>%s)\s*(?:of|/|-of-)\s*(?:12|twelve)\b"
        % (_NAMES, _COUNT)
    ),
    re.compile(
        r"\b(?P<name>%s)(?:'s)?\b[^.;:]{0,32}?\((?P<count>%s)\s+addressed\)"
        % (_NAMES, _COUNT)
    ),
    re.compile(
        r"\b(?P<name>%s)(?:'s)?\b[^.;:]{0,32}?(?P<count>%s)\s+of\s+twelve\s+addressed"
        % (_NAMES, _COUNT)
    ),
)

BARE_PATTERNS = (
    re.compile(r"Axis\s+8\s*(?:=|score of|is|at)?\s*(?P<count>%s)\s*(?:of|/)\s*12\b" % _COUNT),
    re.compile(r"Axis\s+8\s*\((?P<count>%s)\s*(?:of|/)\s*12\b" % _COUNT),
)


def as_int(token: str) -> int:
    return NUMERALS.get(token.lower(), -1) if not token.isdigit() else int(token)


def main() -> int:
    scores = yaml.safe_load(SCORES_PATH.read_text())
    coverage = yaml.safe_load(COVERAGE_PATH.read_text())
    matrix = coverage["matrix"]
    errors: list[str] = []

    # 1. Matrix completeness and vocabulary.
    for proto in coverage["protocols"]:
        row = matrix.get(proto)
        if row is None:
            errors.append(f"{proto}: listed in `protocols` but absent from `matrix`")
            continue
        missing = THREATS - set(row)
        extra = set(row) - THREATS
        if missing:
            errors.append(f"{proto}: missing threat classes {sorted(missing)}")
        if extra:
            errors.append(f"{proto}: unknown threat classes {sorted(extra)}")
        for threat, entry in row.items():
            token = (entry or {}).get("coverage")
            if token not in COVERAGE_TOKENS:
                errors.append(f"{proto}.{threat}: bad coverage token {token!r}")

    # 2. Axis 8 is the count of `addressed`, nothing else.
    for proto in coverage["protocols"]:
        row = matrix.get(proto) or {}
        addressed = sum(
            1 for e in row.values() if (e or {}).get("coverage") == "addressed"
        )
        entry = (scores.get(proto) or {}).get("axis_8") or {}
        declared = entry.get("score")
        if declared is None:
            errors.append(f"{proto}: in the threat matrix but has no axis_8.score")
        elif declared != addressed:
            partial = sum(
                1 for e in row.values() if (e or {}).get("coverage") == "partial"
            )
            errors.append(
                f"{proto}: axis_8.score is {declared} but the matrix has "
                f"{addressed} addressed ({partial} partial, which the axis "
                f"definition excludes)"
            )

    # 2b. The severity block is complete and internally consistent.
    severity = coverage.get("severity")
    if not severity:
        errors.append("threat-coverage.yaml: no `severity` block, so Table 6 "
                      "cannot be generated")
    else:
        missing = THREATS - set(severity)
        extra = set(severity) - THREATS
        for threat in sorted(missing):
            errors.append(f"severity.{threat}: missing a band")
        for threat in sorted(extra):
            errors.append(f"severity.{threat}: not one of the twelve threats")
        for threat, entry in severity.items():
            band = (entry or {}).get("band")
            weight = (entry or {}).get("weight")
            if band not in SEVERITY_WEIGHTS:
                errors.append(f"severity.{threat}: bad band {band!r}")
                continue
            if weight != SEVERITY_WEIGHTS[band]:
                errors.append(
                    f"severity.{threat}: band {band} carries weight "
                    f"{SEVERITY_WEIGHTS[band]} but the entry declares {weight!r}"
                )
            if not (entry or {}).get("rationale"):
                errors.append(
                    f"severity.{threat}: band with no rationale; the band is a "
                    f"judgement and has to say what it rests on"
                )

    # 3. Rubric-scored protocols and threat-matrix protocols are the same set.
    rubric_scored = {
        pid for pid, d in scores.items() if isinstance(d, dict) and "axis_8" in d
    }
    only_scores = rubric_scored - set(coverage["protocols"])
    only_matrix = set(coverage["protocols"]) - rubric_scored
    for proto in sorted(only_scores):
        errors.append(f"{proto}: has axis_8 but no row in threat-coverage.yaml")
    for proto in sorted(only_matrix):
        errors.append(f"{proto}: has a threat row but no axis_8 in protocol-scores.yaml")

    # 4. Range checks.
    for pid, data in scores.items():
        if not isinstance(data, dict):
            continue
        for axis in ORDINAL_AXES:
            entry = data.get(f"axis_{axis}") or {}
            s = entry.get("score")
            if s is not None and not (0 <= s <= 3):
                errors.append(f"{pid}.axis_{axis}: score {s} outside 0 to 3")
        s = (data.get("axis_8") or {}).get("score")
        if s is not None and not (0 <= s <= 12):
            errors.append(f"{pid}.axis_8: count {s} outside 0 to 12")

    # 5. Prose counts agree with the YAML.
    checked = 0
    # The two-line window means one claim can match twice, once per window it
    # falls in, and the named and bare patterns can both match it. Report each
    # (protocol, claim) pair once per file.
    prose_seen: set[tuple[str, str, int]] = set()
    for tex in sorted(SECTIONS_DIR.glob("*.tex")):
        owner: str | None = None
        # Prose wraps across lines, so match over a two-line sliding window.
        lines = tex.read_text().splitlines()
        for lineno, line in enumerate(lines, 1):
            if line.lstrip().startswith("%"):
                continue
            if "\\subsection{" in line:
                owner = None
                for needle, proto in SUBSECTION_OWNER:
                    if needle in line:
                        owner = proto
                        break
            window = line
            if lineno < len(lines):
                window = line + " " + lines[lineno].strip()

            hits: list[tuple[str, int, str]] = []
            for pattern in NAMED_PATTERNS:
                for m in pattern.finditer(window):
                    hits.append(
                        (PROSE_NAMES[m.group("name")], as_int(m.group("count")), m.group(0))
                    )
            if owner and not hits:
                for pattern in BARE_PATTERNS:
                    for m in pattern.finditer(window):
                        hits.append((owner, as_int(m.group("count")), m.group(0)))

            for proto, claimed, text in hits:
                if claimed < 0:
                    continue
                actual = ((scores.get(proto) or {}).get("axis_8") or {}).get("score")
                if actual is None:
                    continue
                key = (tex.name, proto, claimed)
                if claimed == actual:
                    # Correct claims are counted per occurrence, since the
                    # count is only there to prove the scan is live.
                    checked += 1
                    continue
                if key in prose_seen:
                    continue
                prose_seen.add(key)
                checked += 1
                if claimed != actual:
                    errors.append(
                        f"{tex.name}:{lineno}: prose says {proto} Axis 8 is "
                        f"{claimed}, YAML says {actual} "
                        f"({' '.join(text.split())!r})"
                    )

    if errors:
        print("check-scores FAILED")
        for e in errors:
            print(f"  {e}")
        return 1

    counts = {
        p: sum(
            1
            for e in (matrix.get(p) or {}).values()
            if (e or {}).get("coverage") == "addressed"
        )
        for p in coverage["protocols"]
    }
    if checked == 0:
        print("check-scores FAILED")
        print("  the prose scan matched no Axis 8 count at all, so it is not "
              "checking anything: fix the patterns, do not ignore this")
        return 1

    print(
        "check-scores passed: %d protocols, Axis 8 counts match the matrix (%s); "
        "%d prose count(s) verified"
        % (len(counts), ", ".join(f"{p} {n}" for p, n in counts.items()), checked)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
