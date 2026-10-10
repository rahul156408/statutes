"""Units -> Chunks.

Rules (in order):
 1. A paragraph that fits the token budget becomes ONE chunk (keeps a duty with its exceptions).
 2. A longer paragraph is split at its points (a), (b)... and the lead-in sentence is repeated
    in front of every point, so each chunk reads as a self-contained provision.
 3. Definition units are always split one-definition-per-chunk.
 4. Anything still over budget is split into sentence windows with one sentence of overlap.
"""
from __future__ import annotations

import re

from .config import MAX_CHUNK_TOKENS, RULES_PHASE, SourceSpec
from .schema import Chunk
from .segmenters import Unit
from .text_utils import Line, approx_tokens, join_lines, sentence_windows, split_by_marker

_TAIL = re.compile(r"^(Illustrations?|Explanation)\b")

# Article 4 GDPR has points numbered (1)...(26), not (a)...(z)
_L2_OVERRIDE = {("GDPR", "4"): "parennum"}


def _citation(spec: SourceSpec, unit: Unit, p: str | None, pt: str | None) -> str:
    n = unit.number
    if unit.kind == "recital":
        return f"{spec.instrument} Recital {n}"
    if unit.kind == "schedule":
        return f"{spec.instrument} {unit.label}"
    base = {
        "GDPR": f"GDPR Art. {n}",
        "DPDP": f"DPDP s.{n}",
        "DPDP-Rules": f"DPDP-Rules r.{n}",
        "CCPA": f"CCPA \u00a7{n}",
    }[spec.instrument]
    cit = base
    if p and p != "lead":
        cit += f"({p})"
    if pt:
        cit += f"({pt})" if pt != "note" else " (explanation/illustration)"
    return cit


def _hierarchy(unit: Unit, p: str | None, pt: str | None) -> list[str]:
    h = [unit.chapter] if unit.chapter else []
    h.append(f"{unit.label} - {unit.title}" if unit.title else unit.label)
    if p and p != "lead":
        h.append(f"({p})")
    if pt:
        h.append(f"({pt})" if pt != "note" else "(explanation/illustration)")
    return h


class _Ctx:
    def __init__(self, spec: SourceSpec, source_sha: str):
        self.spec, self.sha = spec, source_sha

    def make(self, unit: Unit, p, pt, text: str, span: tuple[int, int], window: int | None = None) -> Chunk:
        parts = [self.spec.key, unit.unit_id]
        if p:
            parts.append(f"p{p}")
        if pt:
            parts.append(f"pt{pt}")
        if window is not None:
            parts.append(f"w{window}")
        phase = RULES_PHASE.get(unit.number) if self.spec.instrument == "DPDP-Rules" and unit.kind != "schedule" else None
        return Chunk(
            chunk_id=":".join(parts),
            instrument=self.spec.instrument,
            jurisdiction=self.spec.jurisdiction,
            kind=unit.kind,
            unit_id=f"{self.spec.key}:{unit.unit_id}",
            citation=_citation(self.spec, unit, p, pt),
            hierarchy=_hierarchy(unit, p, pt),
            title=unit.title,
            text=text,
            token_count=approx_tokens(text),
            parent_instrument=self.spec.parent_instrument,
            commencement_phase=phase,
            source_file=self.spec.path,
            source_sha256=self.sha,
            char_start=span[0],
            char_end=span[1],
        )

    def windowed(self, unit, p, pt, text, span, lead: str = "") -> list[Chunk]:
        """Chunk `text`; if a lead-in is given it is repeated in front of every piece.

        Only the body is split into sentence windows, so every window really contains text
        from the cited point (never just the lead-in).
        """
        prefix = f"{lead} " if lead else ""
        if approx_tokens(prefix + text) <= MAX_CHUNK_TOKENS:
            return [self.make(unit, p, pt, (prefix + text).strip(), span)]
        budget = max(MAX_CHUNK_TOKENS - approx_tokens(prefix), 60)
        return [self.make(unit, p, pt, (prefix + w).strip(), span, window=i)
                for i, w in enumerate(sentence_windows(text, budget), start=1)]

def _span(lines: list[Line]) -> tuple[int, int]:
    return lines[0].start, lines[-1].end


def chunk_unit(spec: SourceSpec, unit: Unit, source_sha: str) -> list[Chunk]:
    ctx = _Ctx(spec, source_sha)
    lines = [l for l in unit.lines if l.text.strip()]
    if not lines:
        return []

    if unit.kind in ("recital", "schedule"):
        return ctx.windowed(unit, None, None, join_lines(lines), _span(lines))

    force = unit.kind == "definition" and spec.split_definitions
    l2 = _L2_OVERRIDE.get((spec.instrument, unit.number), spec.l2)

    pre, paras = split_by_marker(lines, spec.l1)
    if not paras:
        paras = [(None, lines)]
    elif pre:
        paras = [("lead", pre)] + paras

    out: list[Chunk] = []
    for p, plines in paras:
        text = join_lines(plines)
        if not force and approx_tokens(text) <= MAX_CHUNK_TOKENS:
            out.append(ctx.make(unit, p, None, text, _span(plines)))
            continue

        body, tail = plines, []
        if spec.tail:
            for k, ln in enumerate(plines):
                if k > 0 and _TAIL.match(ln.text):
                    body, tail = plines[:k], plines[k:]
                    break
        lead_lines, points = split_by_marker(body, l2)
        if len(points) < 2:
            out.extend(ctx.windowed(unit, p, None, text, _span(plines)))
            continue

        lead = join_lines(lead_lines)
        if approx_tokens(lead) > 0.6 * MAX_CHUNK_TOKENS:
            lead = ""          # a very long lead-in would crowd out the point itself
        for label, pl in points:
            if pl:
                out.extend(ctx.windowed(unit, p, label, join_lines(pl), _span(pl), lead=lead))
        if tail:
            out.extend(ctx.windowed(unit, p, "note", join_lines(tail), _span(tail)))
    return [c for c in out if c.text.strip()]