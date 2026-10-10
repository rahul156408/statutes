# Phase 1 verification

## Automated checks
- 16 unit tests on synthetic documents and 14 structural checks on the real corpus: all pass (30 total).
- Structural checks cover: unit counts per source, citation order, provenance offsets (each chunk's end matches the end of its cited source span), key-provision wording, no Hindi or Gazette junk, chunk size ceiling.

## Corpus
1,554 chunks: GDPR 838, DPDP Act 208, DPDP Rules 128, CCPA 380.

## Manual spot-check
Status: in progress. Results will be added in a follow-up commit.
Sample: `python scripts/sample_chunks.py 8 42` (32 chunks) plus the key provisions listed in the Phase 1 notes.

## Known limitations
- Token counts are an estimate (words + punctuation); Phase 2 measures them against the real embedding tokenizer. A few chunks (largest about 270 estimated tokens) exceed the 200 budget.
- DPDP Act section titles are not captured (they sit in the PDF margin, which is removed); citations are unaffected.
- DPDP Rules schedules are flat text; tables are not parsed. Schedule chunks carry no heading context.
- Scope: the CCPA statute only (CPPA regulations excluded). GDPR is the original Official Journal text; later corrigenda are not applied.
- DPDP Rules `commencement_phase` comes from secondary sources and should be verified against Rule 1.
- Parsing is sequence-based: a missing marker makes the unit count fall short, which the tests catch.
- When a paragraph is split into points, its lead-in sentence is repeated in each chunk unless the lead-in is very long (over ~120 estimated tokens).
- Closing text that follows a list of points (for example GDPR Art. 6(3)) is attached to the last point's chunk, so the point letter can be imprecise for that sentence; the paragraph number stays correct.
- Footnote markers such as "( 18 )" remain inside some GDPR recital texts.
