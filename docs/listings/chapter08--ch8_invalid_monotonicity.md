# ch8_invalid_monotonicity

Generated view; the canonical source remains authoritative.

Listing ID: `ch8_invalid_monotonicity`. Chapter: 8. Language: python.

Canonical source: [chapter08/printed_snippets.json](../../chapter08/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 08`. The root command checks the lesson and its listing expectations in clean copies.

```python
from foundations_lab import load_fixture, spend_in_window

history = load_fixture().history
for cutoff in (604, 605, 607):
    value = spend_in_window(history, "C1", window_start=540,
                            window_end=600, known_at=cutoff)
    print(cutoff, value)
```

Expected stdout:

```text
604 50
605 45
607 85
```
