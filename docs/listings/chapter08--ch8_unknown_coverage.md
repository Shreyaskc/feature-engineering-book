# ch8_unknown_coverage

Generated view; the canonical source remains authoritative.

Listing ID: `ch8_unknown_coverage`. Chapter: 8. Language: python.

Canonical source: [chapter08/printed_snippets.json](../../chapter08/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 08`. The root command checks the lesson and its listing expectations in clean copies.

```python
from fault_testing_lab import Query, base_fixture, evaluate

empty = base_fixture()
empty["deliveries"] = []
print(evaluate(empty, Query(history_known=True)))
print(evaluate(empty, Query(history_known=False)))
print(evaluate(base_fixture(), Query(history_known=False)))
```

Expected stdout:

```text
0
None
None
```
