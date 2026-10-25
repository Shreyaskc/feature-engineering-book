# A delivery retry preserves source availability

Generated view; the canonical source remains authoritative.

Listing ID: `ch2_retry`. Chapter: 2. Language: python.

Canonical source: [chapters01_02/printed_snippets.json](../../chapters01_02/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 02`. The root command checks the lesson and its listing expectations in clean copies.

```python
from foundations_lab import Delivery, ingest, load_fixture, spend

ledger = load_fixture()
a1 = ledger.history[0]
retry = Delivery("a1-retry", a1, delivered_at=609)
replayed = ingest(ledger, [retry])
print(len(replayed.deliveries), len(replayed.history))
print(replayed.history[0].available_at)
print(spend(replayed.history, "C1", decision_at=600))
```

Expected stdout:

```text
6 5
551
50
```
