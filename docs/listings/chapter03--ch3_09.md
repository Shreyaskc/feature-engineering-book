# Replaying delivery evidence preserves history

Generated view; the canonical source remains authoritative.

Listing ID: `ch3_09`. Chapter: 3. Language: python.

Canonical source: [chapter03/printed_snippets.json](../../chapter03/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 03`. The root command checks the lesson and its listing expectations in clean copies.

```python
from foundations_lab import Delivery, Ledger, ingest
from historical_lab import Query, load_fixture, sqlite_value
ledger = load_fixture()
retry = Delivery("a1-later", ledger.history[0], delivered_at=609)
replayed = ingest(ledger, [retry, retry])
reversed_log = Ledger(tuple(reversed(replayed.deliveries)))
print(replayed.history == ledger.history)
print(reversed_log == replayed)
print(sqlite_value(reversed_log, Query("C1", 540, 600, 600)))
```

Expected stdout:

```text
True
True
50
```
