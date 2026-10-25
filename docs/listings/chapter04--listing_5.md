# Missing values use the training mean.

Generated view; the canonical source remains authoritative.

Listing ID: `listing_5`. Chapter: 4. Language: python.

Canonical source: [chapter04/printed_examples.py](../../chapter04/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 04`. The root command checks the lesson and its listing expectations in clean copies.

```python
from chapter4 import fit_center, transform
center = fit_center([50, None, 20])
assert center == 35
assert transform([None, 100], center) == [0, 65]

```
