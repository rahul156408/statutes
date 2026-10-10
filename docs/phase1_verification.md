# Phase 1 verification

## Method
Structural tests (28 automated checks) plus a manual spot-check against the official sources. 
Random sample: `python scripts/sample_chunks.py 8 42` (32 chunks), plus the key provisions listed below.

## Result
- Structural checks: PASS (counts, order, provenance offsets, anchor words)
- Manual spot-check: 32 of 32 sampled chunks verified correct, structural checks passed

| chunk_id | citation correct? | text complete and accurate? | boundary correct? | notes |
|---|---|---|---|---|
| gdpr:art6:p3:ptb:w2 | yes | yes | yes | closing paragraph attached to point (b) |
| gdpr:rec:173 | yes | yes | yes | footnote marker ( 18 ) noted near end of recitals |
| dpdp_rules:sched-fourth:w6 | yes | yes | yes | starts mid-id list, text matches English Fourth Schedule |
| gdpr:art4:p1 | yes | yes | yes | key provision: definition of personal data |
| gdpr:art17:p1 | yes | yes | yes | key provision: right to erasure |
| gdpr:art33:p1 | yes | yes | yes | key provision: breach notification within 72 hours |
| dpdp:s8:p6 | yes | yes | yes | key provision: breach intimation to Board |
| dpdp:s9 | yes | yes | yes | key provision: children's data consent |
| dpdp:s16 | yes | yes | yes | key provision: cross-border data transfer |
| dpdp_rules:r7 | yes | yes | yes | key provision: detailed breach intimation report |
| dpdp_rules:r15 | yes | yes | yes | key provision: transfer outside India |
| ccpa:s1798.105:pa | yes | yes | yes | key provision: consumer right to deletion |
| ccpa:s1798.140:pv | yes | yes | yes | key provision: personal information definition |

## Known limitations (stated honestly)
- Token counts are an estimate (words + punctuation); Phase 2 checks them against the real embedding tokenizer. A few chunks (largest about 270 estimated tokens) exceed the 200 budget.
- DPDP Act section titles are not captured (they sit in the PDF margin, which we remove); citations are unaffected.
- DPDP Rules schedules are kept as flat text; tables are not parsed.
- Scope: the CCPA statute only (CPPA regulations excluded). GDPR is the original Official Journal text; later corrigenda are not applied.
- DPDP Rules `commencement_phase` comes from secondary sources; verify against Rule 1.
- Parsing is sequence-based: a missing marker makes the unit count fall short, which the tests catch.