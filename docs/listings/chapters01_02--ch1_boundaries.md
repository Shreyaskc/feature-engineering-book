# The lower and upper boundaries

Generated view; the canonical source remains authoritative.

Listing ID: `ch1_boundaries`. Chapter: 1. Language: python.

Canonical source: [chapters01_02/printed_snippets.json](../../chapters01_02/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 01`. The root command checks the lesson and its listing expectations in clean copies.

```python
from foundations_lab import Revision, load_fixture, spend

base = load_fixture().history
lower = Revision("K", 1, "C1", 540, 541, 5)
upper = Revision("L", 1, "C1", 600, 600, 7)
print(spend(base + (lower,), "C1", decision_at=600))
print(spend(base + (upper,), "C1", decision_at=600))
```

Expected stdout:

```text
55
50
```
