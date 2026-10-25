# ch8_half_open_boundary

Generated view; the canonical source remains authoritative.

Listing ID: `ch8_half_open_boundary`. Chapter: 8. Language: python.

Canonical source: [chapter08/printed_snippets.json](../../chapter08/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 08`. The root command checks the lesson and its listing expectations in clean copies.

```python
from fault_testing_lab import boundary_fixture, evaluate

# Amounts 5 at 540, 7 at 599, 11 at 600; all usable by 600.
print(evaluate(boundary_fixture()))
print(evaluate(boundary_fixture(), implementation="M3_inclusive_upper"))
```

Expected stdout:

```text
12
23
```
