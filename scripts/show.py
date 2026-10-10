"""python scripts/show.py "GDPR Art. 17(1)"   -> prints every chunk whose citation starts with that."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
prefix = sys.argv[1]
path = Path(__file__).resolve().parents[1] / "data" / "processed" / "chunks.jsonl"
found = 0
for line in path.read_text(encoding="utf-8").splitlines():
    c = json.loads(line)

    if c["citation"].startswith(prefix) or c["chunk_id"].startswith(prefix):
        found += 1
        print(f"\n[{c['chunk_id']}] {c['citation']} | {c['kind']} | {c['token_count']} tok\n  {c['text']}")
print(f"\n{found} chunk(s) matched")