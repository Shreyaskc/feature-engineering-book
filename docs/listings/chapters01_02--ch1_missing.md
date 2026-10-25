# Known empty and unknown history

Generated view; the canonical source remains authoritative.

Listing ID: `ch1_missing`. Chapter: 1. Language: python.

Canonical source: [chapters01_02/printed_snippets.json](../../chapters01_02/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 01`. The root command checks the lesson and its listing expectations in clean copies.

```python
from foundations_lab import load_fixture, spend

history = load_fixture().history
print(spend(history, "C9", decision_at=600,
            history_known=True))
print(spend(history, "C1", decision_at=600,
            history_known=False))
```

Expected stdout:

```text
0
None
```
