# Restoration requires an explicit ledger contract

Generated view; the canonical source remains authoritative.

Listing ID: `ch2_restore`. Chapter: 2. Language: python.

Canonical source: [chapters01_02/printed_snippets.json](../../chapters01_02/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 02`. The root command checks the lesson and its listing expectations in clean copies.

```python
from foundations_lab import Delivery, Ledger, Revision, ingest
from foundations_lab import load_fixture, spend_in_window

ledger = Ledger(allow_restore=True)
ledger = ingest(ledger, load_fixture("deletion_extension").deliveries)
restore = Revision("C", 4, "C1", 585, 620, 28)
ledger = ingest(ledger, [Delivery("c4", restore, 620)])
print(spend_in_window(ledger.history, "C1", window_start=540,
                      window_end=600, known_at=620))
```

Expected stdout:

```text
88
```
