# Inspect the selected evidence

Generated view; the canonical source remains authoritative.

Listing ID: `ch3_02`. Chapter: 3. Language: python.

Canonical source: [chapter03/printed_snippets.json](../../chapter03/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 03`. The root command checks the lesson and its listing expectations in clean copies.

```python
from historical_lab import Query, explain, load_fixture
ledger = load_fixture()
for cutoff in (600, 610):
    trace = explain(ledger, Query("C1", 540, 600, cutoff))
    chosen = [(r["event_id"], r["revision"]) for r in trace["selected"]]
    print(cutoff, chosen)
print(trace["selected"][-1]["reason"])
```

Expected stdout:

```text
600 [('A', 1), ('C', 1)]
610 [('A', 1), ('B', 1), ('C', 2), ('D', 1)]
outside event window
```
