# Missing evidence is unverifiable

Generated view; the canonical source remains authoritative.

Listing ID: `listing_6`. Chapter: 6. Language: python.

Canonical source: [chapter06/printed_examples.py](../../chapter06/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 06`. The root command checks the lesson and its listing expectations in clean copies.

```python
from dataclasses import replace
from parity_lab import KEY, SourceHistory, build_fixture, reconcile
trace, logs = build_fixture()
partial = replace(
    logs[4], present_fields=logs[4].present_fields - {"value_revision"})
row = reconcile(trace, [partial])["rows"][0]
assert row["comparisons"]["policy_full_match"] is None
assert "insufficient_evidence" in row["flags"]
assert SourceHistory(known=False).reference(KEY, 610).value is None
assert SourceHistory().reference(KEY, 610).value == 0
result = {"full_match": None, "absent": row["absent_log_fields"]}
```
