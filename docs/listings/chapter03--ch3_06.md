# Select tombstones before filtering operations

Generated view; the canonical source remains authoritative.

Listing ID: `ch3_06`. Chapter: 3. Language: python.

Canonical source: [chapter03/printed_snippets.json](../../chapter03/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 03`. The root command checks the lesson and its listing expectations in clean copies.

```python
from historical_lab import Query, explain, load_fixture, sqlite_value
ledger = load_fixture("deletion_extension")
query = Query("C1", 540, 600, 620)
trace = explain(ledger, query)
print([(r["event_id"], r["revision"], r["op"])
       for r in trace["selected"] if r["event_id"] == "C"])
print(trace["value"], sqlite_value(ledger, query))
print(sqlite_value(ledger, Query("C1", 540, 600, 600)))
```

Expected stdout:

```text
[('C', 3, 'delete')]
60 60
50
```
