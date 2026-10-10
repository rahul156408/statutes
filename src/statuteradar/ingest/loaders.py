from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_html(path: Path) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n")


def _drop_margin(page, margin_x0: float):
    """Remove whole words that START left of margin_x0 (never leaves word fragments)."""
    boxes = [(w["x0"], w["x1"], w["top"], w["bottom"])
             for w in page.extract_words() if w["x0"] < margin_x0]

    def keep(obj) -> bool:
        if obj.get("object_type") != "char":
            return True
        cx, cy = (obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2
        return not any(x0 <= cx <= x1 and top <= cy <= bottom for x0, x1, top, bottom in boxes)

    return page.filter(keep)


def load_pdf(path: Path, margin_x0: float | None = None) -> str:
    """pdfplumber by default (keeps word spacing in justified Gazette text); pypdf as fallback.

    margin_x0: drop every word that starts left of this x position (in PDF points).
    Indian Acts print each section title in a left margin column; without this the margin
    words get merged into the body lines. Force an engine with STATUTERADAR_PDF_ENGINE.
    """
    engine = os.environ.get("STATUTERADAR_PDF_ENGINE", "pdfplumber")
    if engine == "pdfplumber":
        try:
            import pdfplumber
        except ImportError:
            print("WARNING: pdfplumber not installed, falling back to pypdf", file=sys.stderr)
            engine = "pypdf"
    if engine == "pdfplumber":
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                if margin_x0 is not None:
                    page = _drop_margin(page, margin_x0)
                pages.append(page.extract_text() or "")
        return "\n".join(pages)
    if margin_x0 is not None:
        print("WARNING: margin cropping needs pdfplumber; margin notes will stay in the text", file=sys.stderr)
    from pypdf import PdfReader

    return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)


def load_text(path: Path, margin_x0: float | None = None) -> str:
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return load_html(path)
    if suffix == ".pdf":
        return load_pdf(path, margin_x0)
    return path.read_text(encoding="utf-8", errors="ignore")