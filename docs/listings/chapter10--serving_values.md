# Compare the two online consumers

Generated view; the canonical source remains authoritative.

Listing ID: `serving_values`. Chapter: 10. Language: python.

Canonical source: [chapter10/printed_snippets.json](../../chapter10/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 10`. The root command checks the lesson and its listing expectations in clean copies.

```python
from capstone_lab import load_case, online_lookups
for mode in ("snapshot_baseline", "contract_pipeline"):
    rows = online_lookups(load_case(), mode)
    print(mode, [row["raw_value"] for row in rows])
```

Expected stdout:

```text
snapshot_baseline [None, 50, 95, 95, 180, 180]
contract_pipeline [None, 50, 45, 45, 85, 85]
```
