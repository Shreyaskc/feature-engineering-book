# Choose the parity denominator explicitly

Generated view; the canonical source remains authoritative.

Listing ID: `9.3_parity`. Chapter: 9. Language: python.

Canonical source: [chapter09/printed_snippets.json](../../chapter09/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 09`. The root command checks the lesson and its listing expectations in clean copies.

```python
from operations_lab import base_report
metrics = base_report()["metrics"]
for name in ("raw_parity", "model_parity", "full_model_parity"):
    m = metrics[name]
    fraction = f'{m["numerator"]}/{m["denominator"]}'
    print(name, fraction, "excluded", m["excluded"],
          "unknown", m["unknown"])
```

Expected stdout:

```text
raw_parity 3/5 excluded 1 unknown 0
model_parity 3/6 excluded 0 unknown 0
full_model_parity 3/6 excluded 0 unknown 0
```
