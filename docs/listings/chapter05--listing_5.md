# apply replacements idempotently.

Generated view; the canonical source remains authoritative.

Listing ID: `listing_5`. Chapter: 5. Language: python.

Canonical source: [chapter05/printed_examples.py](../../chapter05/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 05`. The root command checks the lesson and its listing expectations in clean copies.

```python
from chapter5 import simulate, IMMEDIATE, latest_outputs
outputs = simulate(IMMEDIATE)['outputs']
assert sum(o.total for o in outputs) == 180  # Wrong consumer behavior.
latest = latest_outputs(list(reversed(outputs)) + outputs)
assert list(latest.values())[0].total == 85

```
