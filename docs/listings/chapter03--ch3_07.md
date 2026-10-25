# Read an explicitly authorized restoration

Generated view; the canonical source remains authoritative.

Listing ID: `ch3_07`. Chapter: 3. Language: python.

Canonical source: [chapter03/printed_snippets.json](../../chapter03/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 03`. The root command checks the lesson and its listing expectations in clean copies.

```python
from historical_lab import Query, load_fixture, reference_value, sqlite_value
ledger = load_fixture("restoration_extension")
print(ledger.allow_restore)
for cutoff in (619, 620):
    query = Query("C1", 540, 600, cutoff)
    print(cutoff, reference_value(ledger, query), sqlite_value(ledger, query))
```

Expected stdout:

```text
True
619 60 60
620 88 88
```
