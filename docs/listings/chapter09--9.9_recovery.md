# Verify a fresh local recovery replay

Generated view; the canonical source remains authoritative.

Listing ID: `9.9_recovery`. Chapter: 9. Language: python.

Canonical source: [chapter09/printed_snippets.json](../../chapter09/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 09`. The root command checks the lesson and its listing expectations in clean copies.

```python
from operations_lab import build_change_packet, simulate_recovery
report = simulate_recovery(build_change_packet())
print("outcome:", report["outcome"])
print("phase:", report["phase"])
print("raw:", report["raw_values"])
for name in ("missing", "fallback", "full_model_parity", "lineage"):
    m = report["checks"]["metrics"][name]
    print(name, f'{m["numerator"]}/{m["denominator"]}')
```

Expected stdout:

```text
outcome: RECOVERED
phase: fresh_post_restore_replay
raw: [85, 85, 85, 85]
missing 0/4
fallback 0/4
full_model_parity 4/4
lineage 4/4
```
