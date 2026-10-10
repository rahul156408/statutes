from __future__ import annotations

import json
import platform
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .chunker import chunk_unit
from .config import INTERIM, MAX_CHUNK_TOKENS, PROCESSED, ROOT, SPECS, SourceSpec
from .loaders import load_text, sha256_of
from .schema import Chunk
from .segmenters import SEGMENTERS, Unit
from .text_utils import approx_tokens, join_lines, normalize, to_lines


def build(spec: SourceSpec, root: Path = ROOT, interim: Path = INTERIM):
    """raw file -> normalized text (saved) -> units -> chunks. Returns (norm, units, chunks, meta)."""
    src = root / spec.path
    if not src.exists():
        raise FileNotFoundError(f"{src} not found - download it first (see Phase 1 instructions)")
    raw = load_text(src, spec.pdf_margin_x0)
    norm = normalize(raw, spec.noise)
    interim.mkdir(parents=True, exist_ok=True)
    norm_path = interim / f"{spec.key}.txt"
    norm_path.write_bytes(norm.encode("utf-8"))   # bytes: no CRLF translation on Windows

    units = SEGMENTERS[spec.key](to_lines(norm))
    sha = sha256_of(src)
    chunks = [c for u in units for c in chunk_unit(spec, u, sha)]
    meta = {"source_file": spec.path, "source_sha256": sha, "normalized_sha256": sha256_of(norm_path)}
    return norm, units, chunks, meta


def run_all(root: Path = ROOT):
    PROCESSED.mkdir(parents=True, exist_ok=True)
    all_chunks: list[Chunk] = []
    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "python": platform.python_version(), "max_chunk_tokens": MAX_CHUNK_TOKENS, "sources": {}}
    for spec in SPECS:
        _, units, chunks, meta = build(spec, root)
        all_chunks += chunks
        meta.update(n_units=len(units), n_chunks=len(chunks),
                    units_by_kind=dict(Counter(u.kind for u in units)),
                    chunks_by_kind=dict(Counter(c.kind for c in chunks)))
        manifest["sources"][spec.key] = meta
    with (PROCESSED / "chunks.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for c in all_chunks:
            f.write(c.model_dump_json() + "\n")
    (PROCESSED / "manifest.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    return all_chunks, manifest


def _compress(nums: list[str]) -> str:
    return ", ".join(nums) if len(nums) <= 40 else ", ".join(nums[:20]) + " ... " + ", ".join(nums[-10:])


def diagnose(spec: SourceSpec, root: Path = ROOT) -> str:
    norm, units, chunks, _ = build(spec, root)
    lines = norm.splitlines()
    out = [f"=== {spec.key} ===", f"normalized lines: {len(lines)}", "--- first 12 normalized lines ---"]
    out += [f"  {l[:110]}" for l in lines[:12]]
    kinds = Counter(u.kind for u in units)
    out += ["--- units ---", f"  by kind: {dict(kinds)}", f"  expected (from config): {spec.expected}"]
    for kind in kinds:
        out.append(f"  {kind} numbers: {_compress([u.number for u in units if u.kind == kind])}")
    sized = sorted(((approx_tokens(join_lines(u.lines)), u.label) for u in units))
    out.append("--- 5 SMALLEST units (tiny = suspicious, e.g. a contents list) ---")
    out += [f"  {t:>5} tok  {lab}" for t, lab in sized[:5]]
    out.append("--- 3 LARGEST units ---")
    out += [f"  {t:>5} tok  {lab}" for t, lab in sized[-3:]]
    if units:
        last = units[-1]
        out.append(f"--- last 3 lines of the final unit ({last.label}); footer junk shows here ---")
        out += [f"  {l.text[:110]}" for l in last.lines[-3:]]
    nums = [int(u.number) for u in units if u.kind in ("operative", "definition") and u.number.isdigit()]
    if nums and spec.expected and max(nums) < max(v for v in spec.expected.values() if isinstance(v, int)) and max(nums) != 99:
        nxt = max(nums) + 1
        hits = [(i, l) for i, l in enumerate(lines) if re.match(rf"^\W*{nxt}\b", l)]
        out.append(f"--- !! numbering stops at {max(nums)}. Lines that look like marker {nxt} ---")
        out += [f"  line {i}: {l[:110]}" for i, l in hits[:6]] or ["  (none found: the text may be missing or split oddly)"]
    over = [c for c in chunks if c.token_count > MAX_CHUNK_TOKENS]
    out += ["--- chunks ---", f"  total: {len(chunks)}  | over {MAX_CHUNK_TOKENS} tokens: {len(over)}"]
    out += [f"  over-limit: {c.citation} ({c.token_count} tok)" for c in over[:5]]
    return "\n".join(out)
