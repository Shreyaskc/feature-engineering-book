# Later knowledge can lower a total

Generated view; the canonical source remains authoritative.

Listing ID: `ch3_04`. Chapter: 3. Language: python.

Canonical source: [chapter03/printed_snippets.json](../../chapter03/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 03`. The root command checks the lesson and its listing expectations in clean copies.

```python
from historical_lab import Query, load_fixture, reference_value
ledger = load_fixture()
for cutoff in (604, 605, 607):
    query = Query("C1", 540, 600, cutoff)
    print(cutoff, reference_value(ledger, query))
```

Expected stdout:

```text
604 50
605 45
607 85
```
