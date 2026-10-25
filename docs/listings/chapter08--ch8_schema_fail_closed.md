# ch8_schema_fail_closed

Generated view; the canonical source remains authoritative.

Listing ID: `ch8_schema_fail_closed`. Chapter: 8. Language: python.

Canonical source: [chapter08/printed_snippets.json](../../chapter08/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 08`. The root command checks the lesson and its listing expectations in clean copies.

```python
from foundations_lab import ContractError
from fault_testing_lab import evaluate, malformed_cases

cases = malformed_cases()
for name in ("missing", "null", "bool"):
    try:
        evaluate(cases[name + "_available_at"])
    except ContractError:
        print(name, "rejected")
print(evaluate(cases["missing_available_at"],
               implementation="M5_infer_availability"))
```

Expected stdout:

```text
missing rejected
null rejected
bool rejected
90
```
