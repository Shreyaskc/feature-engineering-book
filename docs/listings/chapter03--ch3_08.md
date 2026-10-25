# Preserve the coverage distinction

Generated view; the canonical source remains authoritative.

Listing ID: `ch3_08`. Chapter: 3. Language: python.

Canonical source: [chapter03/printed_snippets.json](../../chapter03/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 03`. The root command checks the lesson and its listing expectations in clean copies.

```python
from historical_lab import Query, load_fixture, reference_value, sqlite_value
ledger = load_fixture()
for known in (True, False):
    query = Query("C9", 540, 600, 600, history_known=known)
    print(reference_value(ledger, query), sqlite_value(ledger, query))
```

Expected stdout:

```text
0 0
None None
```
