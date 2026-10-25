# Reject the whole candidate batch

Generated view; the canonical source remains authoritative.

Listing ID: `ch2_atomic`. Chapter: 2. Language: python.

Canonical source: [chapters01_02/printed_snippets.json](../../chapters01_02/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 02`. The root command checks the lesson and its listing expectations in clean copies.

```python
from dataclasses import replace
from foundations_lab import ContractError, Delivery, ingest
from foundations_lab import Revision, load_fixture

ledger = load_fixture()
before = ledger
new = Delivery("n1", Revision("N", 1, "C1", 590, 591, 2), 591)
conflict = Delivery("a1-bad", replace(ledger.history[0], amount=21), 610)
try:
    ledger = ingest(ledger, [new, conflict])
except ContractError:
    print("ContractError")
print(ledger is before)
```

Expected stdout:

```text
ContractError
True
```
