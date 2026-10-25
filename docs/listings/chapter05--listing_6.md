# measure coverage separately from aggregate difference.

Generated view; the canonical source remains authoritative.

Listing ID: `listing_6`. Chapter: 5. Language: python.

Canonical source: [chapter05/printed_examples.py](../../chapter05/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 05`. The root command checks the lesson and its listing expectations in clean copies.

```python
from chapter5 import BASE, LATE_E, reference, simulate, IMMEDIATE, score
audit = reference(BASE + (LATE_E,))
metrics = [score(o, audit) for o in simulate(IMMEDIATE)['outputs']]
assert [m['identities_seen'] for m in metrics] == [2, 2, 3]
assert [m['matching_latest_versions'] for m in metrics] == [1, 2, 3]
errors = [m['absolute_aggregate_difference'] for m in metrics]
assert errors == [50, 55, 15]

```
