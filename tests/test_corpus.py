"""Structural checks on the REAL corpus. Run `python scripts/run_ingest.py` first.

These checks prove the *structure* is right (counts, order, provenance, anchors).
They do not prove every word is right: that is what the manual spot-check is for.
"""
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from statuteradar.ingest.config import INTERIM, MAX_CHUNK_TOKENS, PROCESSED, SPEC_BY_KEY
from statuteradar.ingest.schema import Chunk

CHUNKS = PROCESSED / "chunks.jsonl"
pytestmark = pytest.mark.skipif(not CHUNKS.exists(), reason="run scripts/run_ingest.py first")


@pytest.fixture(scope="session")
def chunks():
    return [Chunk.model_validate_json(l) for l in CHUNKS.read_text(encoding="utf-8").splitlines()]


def units(chunks, key, kind):
    return {c.unit_id for c in chunks if c.unit_id.startswith(f"{key}:") and c.kind == kind}


def text_of(chunks, citation_prefix):
    return " ".join(c.text for c in chunks if c.citation.startswith(citation_prefix)).lower()


def test_ids_unique_and_schema_valid(chunks):
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(c.token_count > 0 and c.char_end > c.char_start for c in chunks)


def test_gdpr_counts(chunks):
    exp = SPEC_BY_KEY["gdpr"].expected
    arts = units(chunks, "gdpr", "operative") | units(chunks, "gdpr", "definition")
    assert len(arts) == exp["articles"]
    assert len(units(chunks, "gdpr", "recital")) == exp["recitals"]


def test_dpdp_counts(chunks):
    secs = units(chunks, "dpdp", "operative") | units(chunks, "dpdp", "definition")
    assert len(secs) == SPEC_BY_KEY["dpdp"].expected["sections"]
    assert len(units(chunks, "dpdp", "schedule")) >= 1


def test_rules_counts(chunks):
    rules = units(chunks, "dpdp_rules", "operative") | units(chunks, "dpdp_rules", "definition")
    assert len(rules) == SPEC_BY_KEY["dpdp_rules"].expected["rules"]
    assert all(c.parent_instrument == "DPDP" for c in chunks if c.instrument == "DPDP-Rules")


def test_ccpa_range_and_order(chunks):
    nums = []
    for c in chunks:
        if c.instrument == "CCPA" and c.unit_id not in nums:
            nums.append(c.unit_id)
    keys = [tuple(int(x) for x in n.split(":s")[1].split(".")[1:]) for n in nums]
    assert keys == sorted(keys)
    assert nums[0].endswith("1798.100") and nums[-1].endswith("1798.199.100")
    assert {"ccpa:s1798.105", "ccpa:s1798.140"} <= set(nums)


@pytest.mark.parametrize("prefix,needle", [
    ("GDPR Art. 17", "erasure"),
    ("GDPR Art. 33", "72 hours"),
    ("DPDP s.8", "personal data breach"),
    ("DPDP-Rules r.7", "hours"),
    ("CCPA \u00a71798.105", "delete"),
])
def test_anchor_provisions_contain_expected_words(chunks, prefix, needle):
    assert needle in text_of(chunks, prefix)


def _common_suffix_len(a: str, b: str) -> int:
    n = 0
    while n < min(len(a), len(b)) and a[-1 - n] == b[-1 - n]:
        n += 1
    return n


def test_offsets_point_back_into_normalized_text(chunks):
    """The END of every chunk must match the END of the source span it cites.

    A chunk can differ from its span at the START (a repeated lead-in sentence, or a marker or
    title that the span includes but the chunk text drops), so only the end is compared.
    Sentence-window chunks (":w" in the id) cover part of their span, so for those we check
    that their last words occur inside the span.
    """
    cache = {}
    for c in chunks:
        key = c.unit_id.split(":")[0]
        norm = cache.setdefault(key, (INTERIM / f"{key}.txt").read_text(encoding="utf-8"))
        span = re.sub(r"\s+", " ", norm[c.char_start:c.char_end]).strip()
        if ":w" in c.chunk_id:
            assert " ".join(c.text.split()[-3:]) in span, f"{c.chunk_id}: window text not found in its source span"
            continue
        first_word = span.split(" ", 1)[0]
        needed = min(15, max(1, len(span) - len(first_word) - 1))     # skip the leading marker
        ok = span.endswith(c.text) or _common_suffix_len(span, c.text) >= needed
        assert ok, f"{c.chunk_id}: chunk end differs from the end of its source span"

def test_report_oversize_chunks(chunks, capsys):
    over = Counter(c.instrument for c in chunks if c.token_count > 500)
    print("chunks >500 approx tokens per instrument:", dict(over))


def test_no_hindi_or_gazette_junk_in_chunk_text(chunks):
    bad = [c.chunk_id for c in chunks if re.search(r"[\u0900-\u097F]|xxxGID|Uploaded by|UPLOADED BY", c.text)]
    assert not bad, f"junk text in: {bad[:5]}"


def test_chunks_stay_within_twice_the_budget(chunks):
    too_big = [(c.chunk_id, c.token_count) for c in chunks if c.token_count > 2 * MAX_CHUNK_TOKENS]
    assert not too_big, f"oversized chunks: {too_big[:5]}"