# Phase 1 verification: legal-text ingestion and chunking

Project: StatuteRadar, a RAG-based system for cross-jurisdictional regulatory conflict detection.

Status: code complete and merged to `main` (PR #2). Automated checks pass. The manual spot-check is in progress (section 7).

## 1. Summary

| Item                          | Result                                                      |
| ----------------------------- | ----------------------------------------------------------- |
| Sources ingested              | 4 (GDPR, DPDP Act 2023, DPDP Rules 2025, CCPA/CPRA statute) |
| Provision-level chunks        | 1,554 (GDPR 838, DPDP Act 208, DPDP Rules 128, CCPA 380)    |
| Automated tests               | 30 pass (16 unit tests, 14 corpus checks)                   |
| Chunk size (estimated tokens) | median 70, 95th percentile 190, maximum 267, budget 200     |
| Manual spot-check             | In progress, results will be added (section 7)              |

The automated checks prove that the structure of the corpus is right: unit counts, order, provenance and key wording. They do not prove that every word of every chunk is right. That is the purpose of the manual spot-check, and no accuracy percentage is claimed until it is complete.

## 2. Sources

| Instrument | Official document                                                             | Format used              | Notes                                                        |
| ---------- | ----------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------ |
| GDPR       | Regulation (EU) 2016/679, OJ L 119, 4.5.2016                                  | HTML (EUR-Lex)           | Original Official Journal text; later corrigenda not applied |
| DPDP Act   | Digital Personal Data Protection Act, 2023 (Act No. 22 of 2023)               | PDF (MeitY Gazette copy) | Section titles sit in a PDF margin column, which is removed  |
| DPDP Rules | Digital Personal Data Protection Rules, 2025, G.S.R. 846(E), 13 November 2025 | PDF (e-Gazette No. 760)  | Bilingual PDF; only the English text is used                 |
| CCPA       | California Civil Code, Title 1.81.5, sections 1798.100 to 1798.199.100        | HTML (leginfo)           | Statute only; CPPA regulations out of scope                  |

The raw files are not committed to the repository. Each folder under `data/raw/` holds a `SOURCES.md` with the official URL, download date and SHA-256 hash, so anyone can download the same files and check that their copies are identical.

## 3. Method

### 3.1 Text extraction and cleaning

- HTML is read with BeautifulSoup. PDFs are read with pdfplumber, with pypdf as a fallback.
- Text is normalised to Unicode NFKC, whitespace is collapsed, and page furniture is removed with per-source patterns: Gazette headers and footers, printer lines, signature blocks, website navigation, and any line containing Hindi (Devanagari) text.
- A marker that sits alone on a line, such as `(a)`, is merged with the text that follows it. A lone `.` or `;` line is attached to the line before it.
- For the DPDP Act, words that start left of x = 114 pt are dropped, which removes the margin column of section titles.
- The cleaned text of each source is saved under `data/interim/`. Chunk offsets refer to these files.

### 3.2 Segmentation into units

Each source is split into top-level units: GDPR recitals and articles, DPDP sections, Rules and schedules, and CCPA sections. Numbering is sequence-aware, meaning only the next expected number or letter is accepted (1, 2, 3 or a, b, c, with California-style aa, ab and Indian-style za, zb). A stray `(1)` inside running text therefore cannot create a false provision. A missing marker makes the unit count fall short, which the tests catch.

### 3.3 Chunking rules

1. A paragraph that fits the token budget becomes one chunk, which keeps a duty together with its exceptions.
2. A longer paragraph is split at its points, (a), (b) and so on. The lead-in sentence is repeated in front of each point so that every chunk stands alone. A very long lead-in (over about 120 estimated tokens) is not repeated.
3. Definition units (GDPR Art. 4, DPDP s.2, Rules r.2, CCPA s.1798.140) give one chunk per definition.
4. Any text still over budget is split into sentence windows with one sentence of overlap. Only the point text is windowed, so each window contains text from the cited point.
5. Trailing Explanation and Illustration text in the DPDP Act and Rules becomes its own chunk when its paragraph is split.
6. Recitals and schedules are chunked as flat text.

The budget is 200 estimated tokens (words plus punctuation). It was lowered from 400 because the planned embedding model, `all-MiniLM-L6-v2`, truncates input beyond 256 word-pieces. Phase 2 measures this with the real tokenizer.

### 3.4 Chunk record

| Field                          | Meaning                                                             |
| ------------------------------ | ------------------------------------------------------------------- |
| `chunk_id`                     | Unique, for example `gdpr:art17:p1:pta`                             |
| `instrument`, `jurisdiction`   | GDPR, DPDP, DPDP-Rules or CCPA; EU, IN or US-CA                     |
| `kind`                         | operative, definition, recital or schedule                          |
| `unit_id`                      | The Article, Section or Rule the chunk belongs to                   |
| `citation`                     | Canonical citation, for example `GDPR Art. 17(1)(a)`                |
| `hierarchy`, `title`           | Chapter, unit, paragraph and point path; unit title where available |
| `text`, `token_count`          | Chunk text and its estimated token count                            |
| `parent_instrument`            | `DPDP` for chunks from the Rules                                    |
| `commencement_phase`           | Rules only: 1 (on publication), 2 (one year), 3 (eighteen months)   |
| `source_file`, `source_sha256` | Provenance of the raw file                                          |
| `char_start`, `char_end`       | Offsets into `data/interim/<source>.txt`                            |

## 4. Corpus statistics

| Source     | Units                           | Chunks | Chunks by kind                            |
| ---------- | ------------------------------- | ------ | ----------------------------------------- |
| GDPR       | 272 (173 recitals, 99 articles) | 838    | recital 229, operative 583, definition 26 |
| DPDP Act   | 45 (44 sections, 1 schedule)    | 208    | operative 178, definition 28, schedule 2  |
| DPDP Rules | 30 (23 rules, 7 schedules)      | 128    | operative 79, definition 5, schedule 44   |
| CCPA       | 46 sections                     | 380    | operative 307, definition 73              |

The 26 GDPR definition chunks are exactly the 26 points of Article 4. The 7 schedules of the Rules match the official notification.

## 5. Automated verification

### 5.1 Unit tests (16)

These run on small inline documents and need no downloaded files. They cover normalisation, alphabetic sequences in both conventions, marker splitting that ignores out-of-sequence markers, segmentation of each source type, double-dash headings, glued section numbers, contents-list skipping, schedule rows, history-note removal, lead-in repetition, Explanation tails, sentence windows, and Hindi and Gazette noise removal.

### 5.2 Corpus checks (14)

| Check                       | What it proves                                                                                                                                            |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unique IDs and valid schema | No duplicate chunk IDs; every record validates                                                                                                            |
| GDPR counts                 | 99 articles and 173 recitals                                                                                                                              |
| DPDP Act counts             | 44 sections and at least one schedule                                                                                                                     |
| DPDP Rules counts           | 23 rules; every chunk has parent instrument DPDP                                                                                                          |
| CCPA range and order        | Sections in ascending order from 1798.100 to 1798.199.100, including 1798.105 and 1798.140                                                                |
| Anchor wording (5 checks)   | GDPR Art. 17 mentions erasure; Art. 33 mentions 72 hours; DPDP s.8 mentions personal data breach; Rules r.7 mentions hours; CCPA 1798.105 mentions delete |
| Provenance offsets          | The end of every chunk matches the end of the source span it cites                                                                                        |
| No junk text                | No Hindi characters, Gazette watermark or printer footer in any chunk                                                                                     |
| Size ceiling                | No chunk exceeds twice the budget                                                                                                                         |
| Oversize report             | Prints chunks above 500 estimated tokens per instrument                                                                                                   |

## 6. Issues found and fixed during the build

| Issue                                                                                  | Fix                                                                        |
| -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| The pinned `pydantic-core` has no Python 3.14 wheel, so installation failed            | Use a Python 3.12 virtual environment                                      |
| The bilingual Rules PDF was parsed in Hindi instead of English                         | Drop any line containing Devanagari characters                             |
| pypdf glued words together (for example `provisionsof`) and lost section markers       | Read PDFs with pdfplumber                                                  |
| Margin titles of the DPDP Act merged into section lines, so Sections 4 to 44 were lost | Drop words that start in the margin column                                 |
| A title-only heuristic silently removed the first line of plain-sentence sections      | Heuristic removed, regression test added                                   |
| A window of a long point could contain only the lead-in text                           | Window only the point text and repeat the lead-in in each window           |
| The provenance test gave false alarms for short points and same-line titles            | Compare the end of the chunk with the end of its span                      |
| Embedding model truncates input beyond 256 word-pieces                                 | Budget lowered from 400 to 200 estimated tokens, to be measured in Phase 2 |

## 7. Manual spot-check

Status: in progress. Results are added here when it is complete.

### 7.1 Method

1. Generate the reproducible random sample with `python scripts/sample_chunks.py 8 42`, which gives 8 chunks per instrument (32 in total).
2. Check each chunk against the official source: the citation, the text, and where the chunk starts and ends.
3. Check the key provisions in section 7.2 with `python scripts/show.py "<citation prefix>"`.
4. Mark each chunk correct, correct with a noted limitation, or wrong.

Differences that are expected and are not errors: the leading marker is removed, a lead-in sentence is repeated before a point, whitespace is collapsed, and quotation marks and dashes are normalised.

### 7.2 Key provisions

| Provision        | Expected content                                             | Status  |
| ---------------- | ------------------------------------------------------------ | ------- |
| GDPR Art. 4(1)   | Definition of personal data                                  | Pending |
| GDPR Art. 17(1)  | Right to erasure, grounds (a) to (f)                         | Pending |
| GDPR Art. 33(1)  | Breach notification within 72 hours                          | Pending |
| DPDP s.8(6)      | Intimation of a personal data breach                         | Pending |
| DPDP s.9         | Children's data and verifiable parental consent              | Pending |
| DPDP s.16        | Processing outside India                                     | Pending |
| DPDP Rules r.7   | Breach intimation and the detailed report                    | Pending |
| DPDP Rules r.15  | Transfer outside India (title confirmed in the first sample) | Pending |
| CCPA 1798.105(a) | Right to request deletion                                    | Pending |
| CCPA 1798.140(v) | Expected to be the definition of personal information        | Pending |

### 7.3 Sample results

One row per checked chunk. Use: correct, limitation (with a note), or wrong (with a note).

| Chunk ID                   | Citation | Text    | Boundary | Notes   |
| -------------------------- | -------- | ------- | -------- | ------- |
| gdpr:art6:p3:ptb:w2        | Pending  | Pending | Pending  | See 7.4 |
| gdpr:rec173                | Pending  | Pending | Pending  | See 7.4 |
| dpdp_rules:sched-fourth:w6 | Pending  | Pending | Pending  | See 7.4 |

### 7.4 Observations from the first sample review

These were noticed in the printed sample and are to be confirmed against the official texts.

- `gdpr:art6:p3:ptb:w2` is cited as Art. 6(3)(b) but ends with the sentence that closes the whole of paragraph 3. Closing text after a list of points is attached to the last point.
- `gdpr:rec173` contains a footnote marker, `( 18 )`.
- `dpdp_rules:sched-fourth:w6` starts in the middle of a list, because schedules are flat windows without heading context.

### 7.5 Result

To be completed: N of M checked chunks verified correct, K with known-limitation notes, and the number of errors found.

## 8. Known limitations

- Token counts are an estimate (words plus punctuation). Phase 2 measures them against the real embedding tokenizer. A few chunks (the largest about 270 estimated tokens) exceed the 200 budget.
- DPDP Act section titles are not captured, because they sit in the PDF margin that is removed. Citations are unaffected.
- DPDP Rules schedules are flat text and their tables are not parsed. Schedule chunks carry no heading context.
- Scope: the CCPA statute only; the CPPA regulations are excluded. GDPR is the original Official Journal text; later corrigenda are not applied.
- DPDP Rules `commencement_phase` comes from secondary sources and should be verified against Rule 1. A corrigendum to the Rules was published, and whether it changes any rule text is recorded in `data/raw/dpdp/SOURCES.md`.
- Parsing is sequence-based. A missing marker makes the unit count fall short, which the tests catch.
- When a paragraph is split into points, its lead-in sentence is repeated in each chunk unless the lead-in is very long.
- Closing text that follows a list of points (for example GDPR Art. 6(3)) is attached to the last point's chunk, so the point letter can be imprecise for that sentence. The paragraph number stays correct.
- Footnote markers such as `( 18 )` remain inside some GDPR recital texts.

## 9. Reproducing the results

```bash
py -3.12 -m venv venv
source venv/Scripts/activate
pip install pydantic==2.9.2 beautifulsoup4==4.12.3 pypdf==5.0.1 pdfplumber==0.11.10 pytest==8.3.3
# download the four sources as listed in data/raw/*/SOURCES.md
python scripts/run_ingest.py
python -m pytest tests -q
python scripts/sample_chunks.py 8 42
```

## 10. Next steps

1. Complete the manual spot-check and record the result in section 7.
2. Follow-up fixes: attach closing text to its paragraph instead of the last point, and strip footnote markers from recitals.
3. Phase 2: embed the chunks, build the retrieval index, and measure the real token lengths against the embedding model.
