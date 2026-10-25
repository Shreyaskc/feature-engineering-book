# ch8_shuffled_input

Generated view; the canonical source remains authoritative.

Listing ID: `ch8_shuffled_input`. Chapter: 8. Language: python.

Canonical source: [chapter08/printed_snippets.json](../../chapter08/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 08`. The root command checks the lesson and its listing expectations in clean copies.

```python
from fault_testing_lab import Query, base_fixture, evaluate

rows = base_fixture()
rows["deliveries"].reverse()
query = Query(decision_at=610)
print(evaluate(rows, query))
print(evaluate(rows, query, implementation="M4_input_order_latest"))
```

Expected stdout:

```text
95
100
```
