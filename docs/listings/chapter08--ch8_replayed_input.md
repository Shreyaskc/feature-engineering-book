# ch8_replayed_input

Generated view; the canonical source remains authoritative.

Listing ID: `ch8_replayed_input`. Chapter: 8. Language: python.

Canonical source: [chapter08/printed_snippets.json](../../chapter08/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 08`. The root command checks the lesson and its listing expectations in clean copies.

```python
from copy import deepcopy
from fault_testing_lab import base_fixture, evaluate

data = base_fixture()
replayed = deepcopy(data)
replayed["deliveries"] *= 2
for name in ("reference", "M2_count_deliveries"):
    before = evaluate(data, implementation=name)
    after = evaluate(replayed, implementation=name)
    print(name, before, after)
```

Expected stdout:

```text
reference 50 50
M2_count_deliveries 50 100
```
