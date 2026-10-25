# Replay reordered source deliveries

Generated view; the canonical source remains authoritative.

Listing ID: `replay_invariance`. Chapter: 10. Language: python.

Canonical source: [chapter10/printed_snippets.json](../../chapter10/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 10`. The root command checks the lesson and its listing expectations in clean copies.

```python
from dataclasses import replace
from random import Random
from capstone_lab import load_case, run_case
from foundations_lab import Ledger
case = load_case("challenge")
rows = list(case.ledger.deliveries) * 3
Random(1010).shuffle(rows)
replayed = replace(case, ledger=Ledger(tuple(rows)))
print(run_case(case) == run_case(replayed))
```

Expected stdout:

```text
True
```
