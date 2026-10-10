from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# src/statuteradar/ingest/config.py -> parents[3] is the repo root
ROOT = Path(__file__).resolve().parents[3]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"

# Approximate token budget per chunk (words + punctuation, see text_utils.approx_tokens).
# .env.example names sentence-transformers/all-MiniLM-L6-v2, which silently truncates input
# beyond 256 word-pieces. Legal text yields roughly 1.2-1.3 word-pieces per counted token,
# so 200 keeps chunks under that limit. Phase 2 verifies this with the real tokenizer.
# (If the team switches to a 512-token embedding model, this can go back up to ~400.)
MAX_CHUNK_TOKENS = 200

# Gazette / website furniture that must not leak into legal text.
GAZETTE_NOISE = (
    r"GAZETTE OF INDIA",
    r"^\[?PART II",
    r"^REGD\. NO",
    r"^CG-DL",
    r"^\d{1,3}$",                         # lone page numbers
    r"[\u0900-\u097F]",                    # any line containing Hindi (Devanagari) text
    r"^xxxGID",                            # Gazette watermark tokens
    r"^\(\d\)(\s+\(\d\))+$",               # column-number furniture such as "(1) (2) (3) (4)"
    r"Uploaded by Dte\. of Printing",      # printer footer
    r"Published by the Controller of Publications",
    r"Jt\. ?Secy",                         # signature line
    r"UPLOADED BY THE MANAGER",
    r"AND PUBLISHED BY THE CONTROLLER OF PUBLICATIONS",
    r"^MGIPMRND",
    r"^\[F\. ?No\.",
    r"BY THE MANAGER, GOVERNMENT OF INDIA PRESS",   # printer footer, Act (upper case)
    r"^DR\. REETA VASISHTA",                        # signature block, Act
    r"^Secretary to the Govt\. of India",
)
LEGINFO_NOISE = (
    r"^(Home|Bill Information|California Law|Publications|Other Resources)$",
    r"^(My Subscriptions|My Favorites|Code:|Section:|Search Phrase)",
    r"^CIV$",                              # leginfo footer
    r"^Civil Code - CIV$",
)
# DPDP Rules 2025 commencement phases (two independent secondary sources agree).
# Still glance at Rule 1(2)-(4) in the notified PDF to confirm.
#   phase 1: on publication; phase 2: one year later; phase 3: eighteen months later
_RULES_PHASE_1 = (1, 2, 17, 18, 19, 20, 21)
_RULES_PHASE_2 = (4,)
_RULES_PHASE_3 = (3, *range(5, 17), 22, 23)
RULES_PHASE: dict[str, int] = {
    **{str(n): 1 for n in _RULES_PHASE_1},
    **{str(n): 2 for n in _RULES_PHASE_2},
    **{str(n): 3 for n in _RULES_PHASE_3},
}


@dataclass(frozen=True)
class SourceSpec:
    key: str
    instrument: str
    jurisdiction: str
    path: str                       # relative to repo root
    l1: str                         # marker style of paragraphs: dotnum | parennum | alpha
    l2: str                         # marker style of points inside a paragraph
    tail: bool = False              # split off trailing Explanation/Illustration text
    split_definitions: bool = True  # force one chunk per definition in definition units
    parent_instrument: str | None = None
    noise: tuple[str, ...] = ()
    pdf_margin_x0: float | None = None   # PDF only: drop the left margin-note column
    expected: dict = field(default_factory=dict)  # sanity targets, used by tests


SPECS: list[SourceSpec] = [
    SourceSpec("gdpr", "GDPR", "EU", "data/raw/gdpr/gdpr_eurlex.html",
               l1="dotnum", l2="alpha", expected={"articles": 99, "recitals": 173}),
    SourceSpec("dpdp", "DPDP", "IN", "data/raw/dpdp/dpdp_act_2023.pdf",
               l1="parennum", l2="alpha", tail=True, noise=GAZETTE_NOISE,
               pdf_margin_x0=114, expected={"sections": 44}),
    SourceSpec("dpdp_rules", "DPDP-Rules", "IN", "data/raw/dpdp/dpdp_rules_2025.pdf",
               l1="parennum", l2="alpha", tail=True, noise=GAZETTE_NOISE,
               parent_instrument="DPDP", expected={"rules": 23}),
    SourceSpec("ccpa", "CCPA", "US-CA", "data/raw/ccpa/ccpa_civil_code.html",
               l1="alpha", l2="parennum", split_definitions=False, noise=LEGINFO_NOISE),
]
SPEC_BY_KEY = {s.key: s for s in SPECS}
