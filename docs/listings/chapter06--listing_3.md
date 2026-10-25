# A missing cell and its fallback

Generated view; the canonical source remains authoritative.

Listing ID: `listing_3`. Chapter: 6. Language: python.

Canonical source: [chapter06/printed_examples.py](../../chapter06/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 06`. The root command checks the lesson and its listing expectations in clean copies.

```python
from parity_lab import build_fixture
trace, logs = build_fixture()
miss = logs[0]
assert miss.raw_value is None and miss.feature_missing is True
assert miss.model_input == 0 and miss.fallback_value == 0
assert miss.fallback_used and miss.fallback_reason == "cache_miss"
result = {"raw": miss.raw_value, "model": miss.model_input,
          "missing": miss.feature_missing, "reason": miss.fallback_reason}
```
