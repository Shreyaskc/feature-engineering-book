# Keep the earlier delayed trace

Generated view; the canonical source remains authoritative.

Listing ID: `continuity`. Chapter: 10. Language: python.

Canonical source: [chapter10/printed_snippets.json](../../chapter10/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 10`. The root command checks the lesson and its listing expectations in clean copies.

```python
from capstone_lab import continuity_report
report = continuity_report()
print(report["raw_values"])
print(report["policy_values"])
print(report["source_values"])
```

Expected stdout:

```text
[None, 50, 50, 50, 85, 85]
[50, 50, 45, 85, 85, 85]
[50, 50, 45, 85, 85, 100]
```
