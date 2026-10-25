# Two lag causes at one request

Generated view; the canonical source remains authoritative.

Listing ID: `listing_4`. Chapter: 6. Language: python.

Canonical source: [chapter06/printed_examples.py](../../chapter06/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 06`. The root command checks the lesson and its listing expectations in clean copies.

```python
from parity_lab import build_fixture, reconcile
trace, logs = build_fixture()
row = reconcile(trace, logs)["rows"][3]
assert row["expected_policy"]["value"] == 85
assert row["expected_store"]["record"]["value"] == 45
assert row["expected_cache"]["record"]["value"] == 50
assert {"materialization_lag", "cache_lag"} <= set(row["flags"])
result = {"request": row["request_id"], "flags": row["flags"]}
```
