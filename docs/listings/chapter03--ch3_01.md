# Three questions, three answers

Generated view; the canonical source remains authoritative.

Listing ID: `ch3_01`. Chapter: 3. Language: python.

Canonical source: [chapter03/printed_snippets.json](../../chapter03/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 03`. The root command checks the lesson and its listing expectations in clean copies.

```python
from historical_lab import Query, load_fixture, reference_value
ledger = load_fixture()
print(reference_value(ledger, Query("C1", 540, 600, 600)))
print(reference_value(ledger, Query("C1", 550, 610, 610)))
print(reference_value(ledger, Query("C1", 540, 600, 610)))
```

Expected stdout:

```text
50
95
85
```
