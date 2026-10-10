"""Unit tests on tiny inline documents. They need no downloaded files, so they run in CI."""
from statuteradar.ingest.chunker import chunk_unit
from statuteradar.ingest.config import SPEC_BY_KEY
from statuteradar.ingest.segmenters import Unit, segment_ccpa, segment_dpdp, segment_gdpr
from statuteradar.ingest.text_utils import (
    Line, approx_tokens, next_alpha_labels, normalize, sentence_windows, split_by_marker, to_lines,
)


def L(*texts):
    return to_lines("\n".join(texts) + "\n")


def test_lone_markers_are_merged_and_noise_dropped():
    out = normalize("(a)\nthe data\n12\n\n  (b)  \nmore   text\n", noise_patterns=(r"^\d{1,3}$",))
    assert out.splitlines() == ["(a) the data", "(b) more text"]


def test_alpha_successors_cover_both_conventions():
    assert next_alpha_labels("") == {"a"}
    assert next_alpha_labels("c") == {"d"}
    assert next_alpha_labels("z") == {"aa", "za"}   # California / Indian styles
    assert next_alpha_labels("aa") == {"ab"}
    assert next_alpha_labels("za") == {"zb"}


def test_split_by_marker_ignores_out_of_sequence_markers():
    pre, items = split_by_marker(L("lead-in:", "(a) one", "(1) stray number", "(b) two", "(a) restart?"), "alpha")
    assert [p.text for p in pre] == ["lead-in:"]
    assert [lab for lab, _ in items] == ["a", "b"]
    assert len(items[1][1]) == 2        # "(a) restart?" stayed inside (b)


GDPR_MINI = """Whereas:
(1) First recital.
(2) Second recital.
HAVE ADOPTED THIS REGULATION:
CHAPTER I
General provisions
Article 1
Subject-matter
1. First paragraph.
2. Second paragraph.
CHAPTER II
Principles
Section 1
Heading to skip
Article 2
Another
Unnumbered text.
Done at Brussels, 27 April 2016.
"""


def test_gdpr_segmentation_recitals_articles_chapters():
    units = segment_gdpr(to_lines(GDPR_MINI))
    assert [u.unit_id for u in units] == ["rec1", "rec2", "art1", "art2"]
    art1, art2 = units[2], units[3]
    assert art1.title == "Subject-matter" and art1.chapter == "Chapter I - General provisions"
    assert art2.chapter == "Chapter II - Principles"
    assert all("Heading to skip" not in l.text for l in art2.lines)
    assert all("Done at Brussels" not in l.text for l in art2.lines)


DPDP_MINI = """ARRANGEMENT OF SECTIONS
1. Short title and commencement.
2. Definitions.
THE SCHEDULE.
CHAPTER I
PRELIMINARY
1. (1) This Act may be called the Test Act.
(2) It commences on notification.
2. Definitions.—In this Act, unless the context otherwise requires,—
(a) "Board" means the Board;
(b) "child" means under eighteen.
THE SCHEDULE
1. A table row.
"""


def test_india_segmentation_skips_contents_list_and_schedule_rows():
    units = segment_dpdp(to_lines(DPDP_MINI))
    assert [u.unit_id for u in units] == ["s1", "s2", "sched-the"]
    assert units[1].kind == "definition" and units[1].title == "Definitions"
    assert any("A table row" in l.text for l in units[2].lines)


CCPA_MINI = """Home
1798.100.
(a) First.
(Added by Stats. 2018.)
1798.105.
(a) Delete. Mentions
1798.100. in a wrapped cross reference.
1798.199.100.
Last section.
"""


def test_ccpa_segmentation_is_monotonic_and_drops_history():
    units = segment_ccpa(to_lines(CCPA_MINI))
    assert [u.number for u in units] == ["1798.100", "1798.105", "1798.199.100"]
    assert all("Added by Stats" not in l.text for u in units for l in u.lines)


def test_long_paragraph_splits_at_points_and_repeats_lead_in():
    spec = SPEC_BY_KEY["gdpr"]
    pts = [f"({c}) " + ("word " * 70).strip() + "." for c in "abcdef"]
    unit = Unit("art9", "9", "Article 9", "Long", "operative", None, L("1. Lead-in sentence:", *pts, "2. Short second paragraph."))
    chunks = chunk_unit(spec, unit, "sha")
    cits = [c.citation for c in chunks]
    assert cits[:3] == ["GDPR Art. 9(1)(a)", "GDPR Art. 9(1)(b)", "GDPR Art. 9(1)(c)"]
    assert cits[-1] == "GDPR Art. 9(2)"
    assert all(c.text.startswith("Lead-in sentence:") for c in chunks if "(1)(" in c.citation)
    assert len({c.chunk_id for c in chunks}) == len(chunks)


def test_explanation_tail_becomes_its_own_chunk_for_indian_acts():
    spec = SPEC_BY_KEY["dpdp"]
    pts = [f"({c}) " + ("term " * 120).strip() + ";" for c in "abcd"]
    unit = Unit("s9", "9", "Section 9", None, "operative", None, L("(1) Lead:", *pts, "Explanation.—Means something.", "(2) Second."))
    chunks = chunk_unit(spec, unit, "sha")
    assert any(c.citation == "DPDP s.9(1) (explanation/illustration)" for c in chunks)
    assert any(c.citation == "DPDP s.9(2)" for c in chunks)


def test_sentence_windows_respect_budget_and_overlap():
    text = " ".join(f"Sentence number {i} has a few words in it." for i in range(60))
    wins = sentence_windows(text, 60)
    assert len(wins) > 1 and all(approx_tokens(w) <= 80 for w in wins)
    assert wins[0].split(". ")[-1] in wins[1]   # one-sentence overlap


def test_india_code_double_dash_headings():
    doc = "1. Short title and commencement.\u2013\u2013(1) This Act may be called the Test Act.\n(2) It commences.\n2. Definitions.\u2013\u2013In this Act,\u2013\u2013\n(a) \"x\" means y;\n(b) \"z\" means w.\n"
    units = segment_dpdp(to_lines(doc))
    assert [u.title for u in units] == ["Short title and commencement", "Definitions"]
    assert units[0].lines[0].text.startswith("(1) This Act")


def test_glued_and_spaced_section_numbers_are_recognised():
    doc = "1. (1) First.\n2.Second heading.\u2013\u2013Text two.\n3 . Third heading.\u2013\u2013Text three.\n4. Fourth.\nTHE SCHEDULE\n"
    units = segment_dpdp(to_lines(doc))
    assert [u.number for u in units[:4]] == ["1", "2", "3", "4"]
    assert units[1].title == "Second heading"


def test_lone_punctuation_line_is_glued_to_previous_line():
    assert normalize("text before\n.\nnext line\n").splitlines() == ["text before.", "next line"]


def test_hindi_and_gazette_furniture_are_dropped_by_config_noise():
    from statuteradar.ingest.config import GAZETTE_NOISE
    raw = "xxxGIDHxxx\n(1) (2) (3) (4)\n1. \u0938\u0902\u0915\u094d\u0937\u093f\u092a\u094d\u0924.\u2014(1) \u0939\u093f\u0902\u0926\u0940\n(1)\nreal text\nJt. Secy .\n"
    assert normalize(raw, GAZETTE_NOISE).splitlines() == ["(1) real text"]


def test_plain_sentence_first_line_is_body_not_a_title():
    doc = "1. (1) First.\n2. A person may process the personal data of a Data Principal only in accordance\nwith this Act.\n3. Third.\nTHE SCHEDULE\n"
    units = segment_dpdp(to_lines(doc))
    assert units[1].title is None
    assert units[1].lines[0].text.startswith("A person may process")

def test_long_point_windows_each_repeat_lead_in_and_contain_point_text():
    spec = SPEC_BY_KEY["gdpr"]
    lead = "The State shall act where the following applies:"
    sentence = lambda i: f"Sentence {i} " + ("detail " * 70).strip() + "."
    unit = Unit("art5", "5", "Article 5", None, "operative", None,
                L("1. " + lead, "(a) " + " ".join(sentence(i) for i in range(3)), "(b) Short second point."))
    chunks = [c for c in chunk_unit(spec, unit, "sha") if c.citation.startswith("GDPR Art. 5(1)(a)")]
    assert len(chunks) >= 2
    for c in chunks:
        assert c.text.startswith(lead)
        assert "Sentence" in c.text[len(lead):]        # real point text, not only the lead-in


def test_very_long_lead_in_is_not_repeated():
    spec = SPEC_BY_KEY["gdpr"]
    long_lead = ("lead " * 150).strip() + ":"
    unit = Unit("art6", "6", "Article 6", None, "operative", None,
                L("1. " + long_lead, "(a) " + ("point " * 60).strip() + ";", "(b) " + ("other " * 60).strip() + "."))
    chunks = chunk_unit(spec, unit, "sha")
    assert chunks and all(not c.text.startswith("lead") for c in chunks)