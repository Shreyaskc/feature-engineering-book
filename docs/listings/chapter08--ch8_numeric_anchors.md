# ch8_numeric_anchors

Generated view; the canonical source remains authoritative.

Listing ID: `ch8_numeric_anchors`. Chapter: 8. Language: python.

Canonical source: [chapter08/printed_snippets.json](../../chapter08/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 08`. The root command checks the lesson and its listing expectations in clean copies.

```python
from fault_testing_lab import Query, base_fixture, evaluate

print(evaluate(base_fixture(), Query(decision_at=600)))
print(evaluate(base_fixture(), Query(decision_at=610)))
```

Expected stdout:

```text
50
95
```
