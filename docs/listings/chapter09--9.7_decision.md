# Require evidence before recommending rollback

Generated view; the canonical source remains authoritative.

Listing ID: `9.7_decision`. Chapter: 9. Language: python.

Canonical source: [chapter09/printed_snippets.json](../../chapter09/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 09`. The root command checks the lesson and its listing expectations in clean copies.

```python
from operations_lab import build_change_packet, decide
report = decide(build_change_packet())
print("contract:", report["contract"])
print("action:", report["action"])
print("blockers:", report["blockers"])
print("external action: False")
```

Expected stdout:

```text
contract: FAIL
action: ROLLBACK
blockers: []
external action: False
```
