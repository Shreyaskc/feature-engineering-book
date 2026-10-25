# Build historical rows with lineage

Generated view; the canonical source remains authoritative.

Listing ID: `historical_rows`. Chapter: 10. Language: python.

Canonical source: [chapter10/printed_snippets.json](../../chapter10/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 10`. The root command checks the lesson and its listing expectations in clean copies.

```python
from capstone_lab import build_dataset, load_case
rows = build_dataset(load_case())
for row in rows:
    print(row["row_id"], row["source_cutoff"], row["value"],
          row["source_versions"])
```

Expected stdout:

```text
D1 600 50 [['A', 1], ['C', 1]]
D2 610 95 [['A', 1], ['B', 1], ['C', 2], ['D', 1]]
Z1 600 0 []
U1 600 None []
```
