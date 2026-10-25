# The same number with the wrong revision

Generated view; the canonical source remains authoritative.

Listing ID: `listing_5`. Chapter: 6. Language: python.

Canonical source: [chapter06/printed_examples.py](../../chapter06/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 06`. The root command checks the lesson and its listing expectations in clean copies.

```python
from dataclasses import replace
from parity_lab import build_fixture, reconcile
trace, logs = build_fixture()
wrong_revision = replace(logs[4], value_revision=1)
row = reconcile(trace, [wrong_revision])["rows"][0]
assert row["comparisons"]["policy_numeric_match"] is True
assert row["comparisons"]["trace_provenance_match"] is False
result = {"numeric_match": True, "flags": row["flags"]}
```
