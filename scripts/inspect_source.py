"""Diagnose one source (or all): python scripts/inspect_source.py gdpr|dpdp|dpdp_rules|ccpa|all"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")   # curly quotes/dashes print safely on Windows
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from statuteradar.ingest.config import SPEC_BY_KEY, SPECS  # noqa: E402
from statuteradar.ingest.pipeline import diagnose  # noqa: E402

keys = [s.key for s in SPECS] if len(sys.argv) < 2 or sys.argv[1] == "all" else sys.argv[1:]
for k in keys:
    try:
        print(diagnose(SPEC_BY_KEY[k]))
    except FileNotFoundError as e:
        print(f"=== {k} ===\n  SKIPPED: {e}")
    print()