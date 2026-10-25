# A known early positive is still immature under our policy.

Generated view; the canonical source remains authoritative.

Listing ID: `listing_3`. Chapter: 4. Language: python.

Canonical source: [chapter04/printed_examples.py](../../chapter04/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 04`. The root command checks the lesson and its listing expectations in clean copies.

```python
from chapter4 import DECISIONS, OUTCOMES, FINALIZED_AT, label_at
assert label_at(DECISIONS[3], OUTCOMES, FINALIZED_AT, 1200) is None
assert label_at(DECISIONS[3], OUTCOMES, FINALIZED_AT, 1320) == 1

```
