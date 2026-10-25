# Replay order does not choose the revision

Generated view; the canonical source remains authoritative.

Listing ID: `ch2_replay`. Chapter: 2. Language: python.

Canonical source: [chapters01_02/printed_snippets.json](../../chapters01_02/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 02`. The root command checks the lesson and its listing expectations in clean copies.

```python
from foundations_lab import Ledger, ingest, load_fixture, spend

original = load_fixture()
duplicated = ingest(original, original.deliveries)
print(duplicated == original)
replayed = ingest(Ledger(), reversed(original.deliveries))
print(replayed == original)
print(spend(replayed.history, "C1", decision_at=610))
```

Expected stdout:

```text
True
True
95
```
