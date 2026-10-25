# Build the rows before fitting a transformation.

Generated view; the canonical source remains authoritative.

Listing ID: `listing_4`. Chapter: 4. Language: python.

Canonical source: [chapter04/printed_examples.py](../../chapter04/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 04`. The root command checks the lesson and its listing expectations in clean copies.

```python
from chapter4 import build_dataset, fit_center, transform
rows, excluded = build_dataset()
train = [r['spend'] for r in rows if r['split'] == 'train']
valid = [r['spend'] for r in rows if r['split'] == 'validation']
center = fit_center(train)
assert center == 55
assert transform(train, center) == [-5, 40, -35]
assert transform(valid, center) == [-45, -15]
assert fit_center(train + valid) == 43  # Wrong fit scope.
assert excluded == [('D4', 'label not mature at cutoff')]

```
