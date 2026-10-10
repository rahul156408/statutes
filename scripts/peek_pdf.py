"""Show how a PDF page really lays out its text (x positions), to debug extraction.

python scripts/peek_pdf.py data/raw/dpdp/dpdp_act_2023.pdf "A person may process"
Finds the first page containing the phrase and prints every line with word x-positions.
"""
import sys

import pdfplumber

sys.stdout.reconfigure(encoding="utf-8")
path, phrase = sys.argv[1], sys.argv[2]

with pdfplumber.open(path) as pdf:
    for pno, page in enumerate(pdf.pages, start=1):
        if phrase in (page.extract_text() or ""):
            break
    else:
        sys.exit(f"phrase not found in {path}")
    print(f"page {pno} of {len(pdf.pages)}, page width {page.width:.0f} pt")
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
    rows = {}
    for w in words:
        rows.setdefault(round(w["top"] / 3), []).append(w)
    for key in sorted(rows):
        ws = sorted(rows[key], key=lambda w: w["x0"])
        out, prev_x1 = [], None
        for w in ws:
            if prev_x1 is not None and w["x0"] - prev_x1 > 18:
                out.append(f" <<gap {w['x0'] - prev_x1:.0f}pt>> ")
            out.append(w["text"] + " ")
            prev_x1 = w["x1"]
        print(f"x0={ws[0]['x0']:5.0f} | {''.join(out)[:140]}")
