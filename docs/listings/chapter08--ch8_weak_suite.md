# ch8_weak_suite

Generated view; the canonical source remains authoritative.

Listing ID: `ch8_weak_suite`. Chapter: 8. Language: python.

Canonical source: [chapter08/printed_snippets.json](../../chapter08/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 08`. The root command checks the lesson and its listing expectations in clean copies.

```python
from fault_testing_lab import Query, base_fixture, evaluate, run_suite

mutant = "M2_count_deliveries"
print(run_suite(mutant, suite="weak")["passed"])
for cutoff in (600, 610):
    value = evaluate(base_fixture(), Query(decision_at=cutoff),
                     implementation=mutant)
    print(cutoff, value)
```

Expected stdout:

```text
True
600 50
610 125
```
