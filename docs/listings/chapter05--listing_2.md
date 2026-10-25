# execute the two policies.

Generated view; the canonical source remains authoritative.

Listing ID: `listing_2`. Chapter: 5. Language: python.

Canonical source: [chapter05/printed_examples.py](../../chapter05/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 05`. The root command checks the lesson and its listing expectations in clean copies.

```python
from chapter5 import simulate, IMMEDIATE, DELAYED
a = simulate(IMMEDIATE)['outputs']
b = simulate(DELAYED)['outputs']
expected = [(600, 50), (605, 45), (607, 85)]
assert [(o.emitted_at, o.total) for o in a] == expected
assert [(o.emitted_at, o.total) for o in b] == [(610, 85)]

```
