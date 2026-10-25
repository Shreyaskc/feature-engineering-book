# The join demonstration, from the companion directory.

Generated view; the canonical source remains authoritative.

Listing ID: `listing_1`. Chapter: 4. Language: python.

Canonical source: [chapter04/printed_examples.py](../../chapter04/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 04`. The root command checks the lesson and its listing expectations in clean copies.

```python
from chapter4 import join_demo
bad, good = join_demo()
assert len(bad) == 4
assert good == [('D1', 50), ('D2', 95)]

```
