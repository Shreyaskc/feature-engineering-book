# a diagnostic watermark does not control this fixed deadline.

Generated view; the canonical source remains authoritative.

Listing ID: `listing_3`. Chapter: 5. Language: python.

Canonical source: [chapter05/printed_examples.py](../../chapter05/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 05`. The root command checks the lesson and its listing expectations in clean copies.

```python
from chapter5 import simulate, IMMEDIATE
with_trace = simulate(IMMEDIATE)
without_trace = simulate(IMMEDIATE, watermarks=())
assert with_trace['outputs'] == without_trace['outputs']
assert any(d['behind_watermark'] for d in with_trace['diagnostics'])
assert not any(d['behind_watermark'] for d in without_trace['diagnostics'])

```
