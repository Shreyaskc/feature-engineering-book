# ch8_later_info_invariance

Generated view; the canonical source remains authoritative.

Listing ID: `ch8_later_info_invariance`. Chapter: 8. Language: python.

Canonical source: [chapter08/printed_snippets.json](../../chapter08/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 08`. The root command checks the lesson and its listing expectations in clean copies.

```python
from fault_testing_lab import run_check

for name in ("reference", "M1_latest_before_cutoff"):
    result = run_check("later_info_invariance", name)
    witness = result["observations"][0]
    print(name, witness["expected"], witness["observed"])
```

Expected stdout:

```text
reference 30 30
M1_latest_before_cutoff 30 0
```
