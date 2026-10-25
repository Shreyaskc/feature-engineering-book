# A tombstone changes only eligible later queries

Generated view; the canonical source remains authoritative.

Listing ID: `ch2_delete`. Chapter: 2. Language: python.

Canonical source: [chapters01_02/printed_snippets.json](../../chapters01_02/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 02`. The root command checks the lesson and its listing expectations in clean copies.

```python
from foundations_lab import load_fixture, spend, spend_in_window

history = load_fixture("deletion_extension").history
print(spend(history, "C1", decision_at=600))
print(spend(history, "C1", decision_at=610))
print(spend_in_window(history, "C1", window_start=540,
                      window_end=600, known_at=620))
```

Expected stdout:

```text
50
95
60
```
