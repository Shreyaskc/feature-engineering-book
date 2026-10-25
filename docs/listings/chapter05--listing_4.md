# an arrival after closure stays out of published history.

Generated view; the canonical source remains authoritative.

Listing ID: `listing_4`. Chapter: 5. Language: python.

Canonical source: [chapter05/printed_examples.py](../../chapter05/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 05`. The root command checks the lesson and its listing expectations in clean copies.

```python
from chapter5 import BASE, LATE_E, simulate, IMMEDIATE, reference
late_run = simulate(IMMEDIATE, BASE + (LATE_E,))
assert late_run['outputs'][-1].total == 85
assert [d.delivery_id for d in late_run['reconciliation']] == ['e1']
assert sum(e.amount for e in reference(BASE + (LATE_E,)).values()) == 100
old = reference(BASE + (LATE_E,), cutoff=600)
assert sum(e.amount for e in old.values()) == 50

```
