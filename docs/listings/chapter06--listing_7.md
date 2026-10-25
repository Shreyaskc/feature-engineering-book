# Finite floating-point tolerance is an explicit choice

Generated view; the canonical source remains authoritative.

Listing ID: `listing_7`. Chapter: 6. Language: python.

Canonical source: [chapter06/printed_examples.py](../../chapter06/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 06`. The root command checks the lesson and its listing expectations in clean copies.

```python
from parity_lab import numeric_equal
tolerance = {"rel_tol": 1e-9, "abs_tol": 1e-12}
assert numeric_equal(0.0, 5e-13, **tolerance)
assert not numeric_equal(0.0, 2e-12, **tolerance)
assert not numeric_equal(84, 85)
assert not numeric_equal(None, None)
result = {"near_zero_inside": True, "near_zero_outside": False,
          "integer_match": False, "missing_is_numeric_match": False}
```
