# keep the fixed event window separate from the knowledge cutoff.

Generated view; the canonical source remains authoritative.

Listing ID: `listing_1`. Chapter: 5. Language: python.

Canonical source: [chapter05/printed_examples.py](../../chapter05/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 05`. The root command checks the lesson and its listing expectations in clean copies.

```python
from chapter5 import reference
assert sum(e.amount for e in reference(cutoff=600).values()) == 50
assert sum(e.amount for e in reference(cutoff=610).values()) == 85
moving = reference(start=550, end=610, cutoff=610)
assert sum(e.amount for e in moving.values()) == 95

```
