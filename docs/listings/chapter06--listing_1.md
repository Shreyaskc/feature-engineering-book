# Fixed means fixed

Generated view; the canonical source remains authoritative.

Listing ID: `listing_1`. Chapter: 6. Language: python.

Canonical source: [chapter06/printed_examples.py](../../chapter06/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 06`. The root command checks the lesson and its listing expectations in clean copies.

```python
from dataclasses import replace
from parity_lab import KEY, build_fixture
trace, _ = build_fixture()
fixed = trace.source.reference(KEY, 610).value
rolling_key = replace(KEY, window_start=550, window_end=610)
rolling = trace.source.reference(rolling_key, 610).value
assert (fixed, rolling) == (85, 95)
result = {"fixed": fixed, "rolling": rolling}
```
