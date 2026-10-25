# Features remain fixed at each original decision.

Generated view; the canonical source remains authoritative.

Listing ID: `listing_2`. Chapter: 4. Language: python.

Canonical source: [chapter04/printed_examples.py](../../chapter04/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 04`. The root command checks the lesson and its listing expectations in clean copies.

```python
from chapter4 import EVENTS, historical_sum
assert historical_sum(EVENTS, 'C1', 600) == 50
assert historical_sum(EVENTS, 'C1', 610) == 95

```
