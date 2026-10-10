"""Print a reproducible random sample of chunks for the manual spot-check.

python scripts/sample_chunks.py            # 8 per instrument, seed 42
python scripts/sample_chunks.py 12 7       # 12 per instrument, seed 7
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42

by_inst = defaultdict(list)
for line in (ROOT / "data" / "processed" / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
    c = json.loads(line)
    by_inst[c["instrument"]].append(c)

rng = random.Random(seed)
for inst, items in by_inst.items():
    print(f"\n{'=' * 78}\n{inst}  ({len(items)} chunks)  sample seed={seed}\n{'=' * 78}")
    for c in rng.sample(items, min(n, len(items))):
        print(f"\n[{c['chunk_id']}]  {c['citation']}  |  {c['kind']}  |  {c['token_count']} tok")
        print("  hierarchy:", " > ".join(c["hierarchy"]))
        print("  text:", c["text"][:600] + (" ..." if len(c["text"]) > 600 else ""))