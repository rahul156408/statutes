from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    text: str
    start: int   # char offset in the normalized text
    end: int


# ---------------------------------------------------------------- normalization
_LONE_MARKER = re.compile(r"^(?:\([A-Za-z0-9]{1,4}\)|\d{1,3}\.)$")
_PUNCT_ONLY = re.compile(r"^[.,;:]+$")


def normalize(raw: str, noise_patterns: tuple[str, ...] = ()) -> str:
    """Raw extracted text -> one logical line per row, noise removed, lone markers merged.

    HTML tables and PDFs often put a marker like "(a)" on its own line; we glue it to the
    following line so every provision starts with its marker.
    """
    text = unicodedata.normalize("NFKC", raw).replace("\u00ad", "")
    noise = [re.compile(p) for p in noise_patterns]
    kept: list[str] = []
    for ln in text.splitlines():
        ln = re.sub(r"\s+", " ", ln).strip()
        if not ln or any(p.search(ln) for p in noise):
            continue
        if kept and _PUNCT_ONLY.match(ln):      # a lone "." / ";" line belongs to the line before
            kept[-1] += ln
            continue
        kept.append(ln)

    merged: list[str] = []
    pending = ""
    for ln in kept:
        if _LONE_MARKER.match(ln):
            pending = f"{pending} {ln}".strip()
            continue
        if pending:
            ln, pending = f"{pending} {ln}", ""
        merged.append(ln)
    if pending:
        merged.append(pending)
    return "\n".join(merged) + "\n"

    merged: list[str] = []
    pending = ""
    for ln in kept:
        if _LONE_MARKER.match(ln):
            pending = f"{pending} {ln}".strip()
            continue
        if pending:
            ln, pending = f"{pending} {ln}", ""
        merged.append(ln)
    if pending:
        merged.append(pending)
    return "\n".join(merged) + "\n"


def to_lines(text: str) -> list[Line]:
    lines, pos = [], 0
    for raw in text.split("\n"):
        if raw:
            lines.append(Line(raw, pos, pos + len(raw)))
        pos += len(raw) + 1
    return lines


def join_lines(lines: list[Line]) -> str:
    return re.sub(r"\s+", " ", " ".join(l.text for l in lines)).strip()


_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def approx_tokens(text: str) -> int:
    """Dependency-free token estimate (words + punctuation). Slightly conservative."""
    return len(_TOKEN_RE.findall(text))


# ---------------------------------------------------------------- marker splitting
MARKERS = {
    "dotnum":   re.compile(r"^(\d{1,3})\.\s+(.*)$"),
    "parennum": re.compile(r"^\((\d{1,3})\)\s*(.*)$"),
    "alpha":    re.compile(r"^\(([a-z]{1,2})\)\s*(.*)$"),
}


def next_alpha_labels(prev: str) -> set[str]:
    """Acceptable successors of an alphabetic label.

    a..z, then California style (aa, ab, ...) or Indian style (za, zb, ...).
    """
    if not prev:
        return {"a"}
    if len(prev) == 1:
        return {"aa", "za"} if prev == "z" else {chr(ord(prev) + 1)}
    if prev[-1] == "z":
        return set()
    return {prev[:-1] + chr(ord(prev[-1]) + 1)}


def _expected(kind: str, prev: str) -> set[str]:
    if kind in ("dotnum", "parennum"):
        return {str(int(prev) + 1)} if prev else {"1"}
    return next_alpha_labels(prev)


def split_by_marker(lines: list[Line], kind: str):
    """Split lines at markers that continue the expected sequence (1,2,3 / a,b,c).

    Sequence-awareness is what stops stray "(1)" or "2." inside running text being
    mistaken for a new provision. Returns (preamble_lines, [(label, lines), ...]).
    The marker itself is stripped from the first line of each item.
    """
    pat = MARKERS[kind]
    pre: list[Line] = []
    items: list[tuple[str, list[Line]]] = []
    prev = ""
    for ln in lines:
        m = pat.match(ln.text)
        if m and m.group(1) in _expected(kind, prev):
            prev = m.group(1)
            items.append((prev, [Line(m.group(2), ln.start, ln.end)]))
        elif items:
            items[-1][1].append(ln)
        else:
            pre.append(ln)
    return pre, items


# ---------------------------------------------------------------- long-text fallback
_SENT_SPLIT = re.compile(r"(?<=[.;:])\s+(?=[A-Z\u2018\u201c(])")


def sentence_windows(text: str, max_tokens: int, overlap: int = 1) -> list[str]:
    sents = _SENT_SPLIT.split(text)
    out: list[str] = []
    cur: list[str] = []
    for s in sents:
        if cur and approx_tokens(" ".join(cur + [s])) > max_tokens:
            out.append(" ".join(cur))
            cur = cur[-overlap:] if overlap else []
        cur.append(s)
    if cur:
        out.append(" ".join(cur))
    return out