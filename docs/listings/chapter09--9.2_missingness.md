# Distinguish a missing feature from missing evidence

Generated view; the canonical source remains authoritative.

Listing ID: `9.2_missingness`. Chapter: 9. Language: python.

Canonical source: [chapter09/printed_snippets.json](../../chapter09/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 09`. The root command checks the lesson and its listing expectations in clean copies.

```python
from operations_lab import base_report
metrics = base_report()["metrics"]
for name in ("missing", "fallback"):
    m = metrics[name]
    fraction = f'{m["numerator"]}/{m["denominator"]}'
    print(name, fraction, "unknown", m["unknown"])
```

Expected stdout:

```text
missing 1/6 unknown 0
fallback 1/6 unknown 0
```
