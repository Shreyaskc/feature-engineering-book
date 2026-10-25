# Two wrong reconstruction orders

Generated view; the canonical source remains authoritative.

Listing ID: `ch3_03`. Chapter: 3. Language: python.

Canonical source: [chapter03/printed_snippets.json](../../chapter03/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 03`. The root command checks the lesson and its listing expectations in clean copies.

```python
from historical_lab import Query, load_fixture, reference_value
from historical_lab import wrong_latest_then_availability
from historical_lab import wrong_ignore_availability
ledger, query = load_fixture(), Query("C1", 540, 600, 600)
print(reference_value(ledger, query))
print(wrong_latest_then_availability(ledger, query))
print(wrong_ignore_availability(ledger, query))
```

Expected stdout:

```text
50
20
85
```
