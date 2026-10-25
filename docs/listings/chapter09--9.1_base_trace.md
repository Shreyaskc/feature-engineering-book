# Preserve the six base observations

Generated view; the canonical source remains authoritative.

Listing ID: `9.1_base_trace`. Chapter: 9. Language: python.

Canonical source: [chapter09/printed_snippets.json](../../chapter09/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 09`. The root command checks the lesson and its listing expectations in clean copies.

```python
from parity_lab import build_fixture
trace, logs = build_fixture()
policy = [trace.policy_at(r.requested_at).value for r in logs]
source = [trace.source.reference(trace.key, r.requested_at).value
          for r in logs]
print("raw:", [r.raw_value for r in logs])
print("model:", [r.model_input for r in logs])
print("policy:", policy)
print("source:", source)
```

Expected stdout:

```text
raw: [None, 50, 50, 50, 85, 85]
model: [0, 50, 50, 50, 85, 85]
policy: [50, 50, 45, 85, 85, 85]
source: [50, 50, 45, 85, 85, 100]
```
