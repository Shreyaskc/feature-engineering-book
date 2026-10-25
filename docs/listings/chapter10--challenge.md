# Run the isolated correction challenge

Generated view; the canonical source remains authoritative.

Listing ID: `challenge`. Chapter: 10. Language: python.

Canonical source: [chapter10/printed_snippets.json](../../chapter10/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 10`. The root command checks the lesson and its listing expectations in clean copies.

```python
from capstone_lab import audit_report, build_dataset, load_case
from capstone_lab import publications
case = load_case("challenge")
print([row["value"] for row in build_dataset(case)[:2]])
print([(row.published_at, row.value) for row in publications(case)])
audit = audit_report(case)
print(audit["closed_policy_value"], audit["audit_source_value"])
```

Expected stdout:

```text
[50, 100]
[(600, 50), (604, 48), (605, 43), (606, 50), (607, 90)]
90 105
```
