# Four builds, three meanings

Generated view; the canonical source remains authoritative.

Listing ID: `compare_builds`. Chapter: 7. Language: python.

Canonical source: [chapter07/printed_snippets.json](../../chapter07/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 07`. The root command checks the lesson and its listing expectations in clean copies.

```python
from backfill_lab import fixture_specs, values

for name, spec in fixture_specs().items():
    print(name, values(spec))
```

Expected stdout:

```text
baseline [50, 95, 0]
extended_historical [50, 95, 0]
corrected [102, 112, 0]
new_definition [30, 35, 0]
```
