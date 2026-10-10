"""Build data/processed/chunks.jsonl + manifest.json from data/raw/*."""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")   # curly quotes/dashes print safely on Windows
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from statuteradar.ingest.pipeline import run_all  # noqa: E402

chunks, manifest = run_all()
print(f"{'source':<12}{'units':>7}{'chunks':>8}")
for k, m in manifest["sources"].items():
    print(f"{k:<12}{m['n_units']:>7}{m['n_chunks']:>8}   {m['chunks_by_kind']}")
print(f"\nTOTAL chunks: {len(chunks)}")
toks = sorted(c.token_count for c in chunks)
print(f"tokens/chunk  median={toks[len(toks)//2]}  p95={toks[int(len(toks)*0.95)]}  max={toks[-1]}")
print("wrote data/processed/chunks.jsonl and data/processed/manifest.json")