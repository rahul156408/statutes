"""Turn normalized lines into top-level legal Units (Article / Section / Rule / ...).

One function per source. They are deliberately strict (sequence-aware) and the counts are
checked by tests, so a format surprise fails loudly instead of silently corrupting the corpus.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .text_utils import MARKERS, Line


class SegmentationError(RuntimeError):
    pass


@dataclass
class Unit:
    unit_id: str            # "art17", "rec5", "s8", "r7", "sched-first", "s1798.105"
    number: str             # "17"
    label: str              # "Article 17"
    title: str | None
    kind: str               # operative | definition | recital | schedule
    chapter: str | None
    lines: list[Line] = field(default_factory=list)


# ====================================================================== GDPR
_ART = re.compile(r"^Article\s+(\d{1,3})$")
_CHAP = re.compile(r"^CHAPTER\s+([IVXL]+)$")
_SECT = re.compile(r"^Section\s+\d+$")
_ADOPTED = re.compile(r"have adopted this regulation", re.I)
_DONE = re.compile(r"^Done at Brussels", re.I)


def segment_gdpr(lines: list[Line]) -> list[Unit]:
    adopted = next((i for i, l in enumerate(lines) if _ADOPTED.search(l.text)), None)
    if adopted is None:
        raise SegmentationError("GDPR: could not find 'HAVE ADOPTED THIS REGULATION' (recitals/articles divider)")

    units: list[Unit] = []

    # --- recitals: "(n) text", strictly 1,2,3...
    pat, prev, cur = MARKERS["parennum"], 0, None
    for ln in lines[:adopted]:
        m = pat.match(ln.text)
        if m and int(m.group(1)) == prev + 1:
            prev += 1
            cur = Unit(f"rec{prev}", str(prev), f"Recital {prev}", None, "recital", None,
                       [Line(m.group(2), ln.start, ln.end)])
            units.append(cur)
        elif cur:
            cur.lines.append(ln)

    # --- articles
    chapter, cur, prev, i = None, None, 0, adopted + 1
    while i < len(lines):
        t = lines[i].text
        if _DONE.match(t):
            break
        if (mc := _CHAP.match(t)):
            cur = None
            title = lines[i + 1].text if i + 1 < len(lines) else ""
            chapter = f"Chapter {mc.group(1)} - {title}"
            i += 2
            continue
        if _SECT.match(t):
            cur = None
            i += 2          # skip "Section N" and its title line
            continue
        if (ma := _ART.match(t)) and int(ma.group(1)) == prev + 1:
            prev += 1
            title = lines[i + 1].text if i + 1 < len(lines) else None
            n = str(prev)
            cur = Unit(f"art{n}", n, f"Article {n}", title,
                       "definition" if n == "4" else "operative", chapter)
            units.append(cur)
            i += 2
            continue
        if cur:
            cur.lines.append(lines[i])
        i += 1
    return units


# ====================================================================== India (Act + Rules)
_SEC_START = re.compile(r"^(\d{1,2})\s*\.(?!\d)\s*(.*)$")
_TITLE_DASH = re.compile(r"^\d{1,2}\s*\.\s*(?P<title>[A-Z][^()\u2014\u2013]{2,150}?)\.\s*[\u2014\u2013]+\s*(?P<rest>.*)$")
_CHAP_IN = re.compile(r"^CHAPTER\s+([IVXL]+)\b")
_ORD = r"(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)"
_SCHED = re.compile(rf"^(?:THE\s+)?(?:{_ORD}\s+)?SCHEDULE\b")
_SCHED_ORD = re.compile(_ORD)


def _parse_start(text: str) -> tuple[str | None, str]:
    if (m := _TITLE_DASH.match(text)):
        return m["title"].strip(), m["rest"]
    return None, _SEC_START.match(text).group(2)


def _find_first_provision(lines: list[Line]) -> int:
    """Index of the real '1.' line (skips an 'Arrangement of Sections' contents list).

    The real first provision carries body text ('1. (1) ...' or '1. Title.-...'),
    whereas a contents entry is a bare '1. Title.'.
    """
    cands = [i for i, l in enumerate(lines) if (m := _SEC_START.match(l.text)) and m.group(1) == "1"]
    if not cands:
        raise SegmentationError("India: no line starting with '1.' found")
    for i in cands:
        t = lines[i].text
        if "\u2014" in t or "\u2013" in t or re.match(r"^1\s*\.\s*\(1\)", t):
            return i
    return cands[0]


def segment_india(lines: list[Line], prefix: str, label: str, definition_numbers: set[str]) -> list[Unit]:
    """prefix/label: ('s', 'Section') for the Act, ('r', 'Rule') for the Rules."""
    start = _find_first_provision(lines)
    units: list[Unit] = []
    chapter, cur, prev = None, None, 0
    i, end = start, len(lines)

    while i < end:
        t = lines[i].text
        if i > start and _SCHED.match(t):
            end = i
            break
        if (mc := _CHAP_IN.match(t)):
            cur = None
            nxt = lines[i + 1].text if i + 1 < len(lines) else ""
            if nxt.isupper():
                chapter, i = f"Chapter {mc.group(1)} - {nxt.title()}", i + 2
            else:
                chapter, i = f"Chapter {mc.group(1)}", i + 1
            continue
        m = _SEC_START.match(t)
        if m and int(m.group(1)) == prev + 1:
            prev += 1
            n = str(prev)
            title, rest = _parse_start(t)
            cur = Unit(f"{prefix}{n}", n, f"{label} {n}", title,
                       "definition" if n in definition_numbers else "operative", chapter,
                       [Line(rest, lines[i].start, lines[i].end)] if rest else [])
            units.append(cur)
        elif cur:
            cur.lines.append(lines[i])
        i += 1

    # --- schedules: from the first schedule heading after the last provision
    heads = [j for j in range(end, len(lines)) if _SCHED.match(lines[j].text)]
    for k, j in enumerate(heads):
        stop = heads[k + 1] if k + 1 < len(heads) else len(lines)
        o = _SCHED_ORD.search(lines[j].text)
        name = o.group(1).lower() if o else "the"
        pretty = f"{name.capitalize()} Schedule" if o else "The Schedule"
        units.append(Unit(f"sched-{name}", name, pretty, None, "schedule", None, lines[j + 1:stop]))
    return units


def segment_dpdp(lines: list[Line]) -> list[Unit]:
    return segment_india(lines, "s", "Section", {"2"})


def segment_dpdp_rules(lines: list[Line]) -> list[Unit]:
    return segment_india(lines, "r", "Rule", {"2"})


# ====================================================================== CCPA
_CCPA = re.compile(r"^(1798\.\d+(?:\.\d+)?)\.\s*(.*)$")
_HISTORY = re.compile(r"^\((?:Added|Amended|Repealed|Renumbered|Enacted|Heading|Section)\b")
_LO, _HI = (100,), (199, 100)


def segment_ccpa(lines: list[Line]) -> list[Unit]:
    units: list[Unit] = []
    prev, cur = (0,), None
    for ln in lines:
        m = _CCPA.match(ln.text)
        if m:
            key = tuple(int(x) for x in m.group(1).split("."))[1:]
            if key > prev and _LO <= key <= _HI:       # monotonic guard against cross-references
                prev = key
                num = m.group(1)
                rest = m.group(2).strip()
                title, body = (None, rest) if (not rest or rest.startswith("(")) else (rest, "")
                cur = Unit(f"s{num}", num, f"\u00a7{num}", title,
                           "definition" if num == "1798.140" else "operative", "Title 1.81.5",
                           [Line(body, ln.start, ln.end)] if body else [])
                units.append(cur)
                continue
        if _HISTORY.match(ln.text):
            continue
        if cur:
            cur.lines.append(ln)
    return units


SEGMENTERS = {
    "gdpr": segment_gdpr,
    "dpdp": segment_dpdp,
    "dpdp_rules": segment_dpdp_rules,
    "ccpa": segment_ccpa,
}
