# Equal outputs do not erase provenance

Generated view; the canonical source remains authoritative.

Listing ID: `preserve_identity`. Chapter: 7. Language: python.

Canonical source: [chapter07/printed_snippets.json](../../chapter07/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 07`. The root command checks the lesson and its listing expectations in clean copies.

```python
from backfill_lab import fixture_specs, make_spec, values

specs = fixture_specs()
old = specs["baseline"]
new = specs["extended_historical"]
print(values(old) == values(new))
print(old.dataset_id == new.dataset_id)
reordered = make_spec(
    old.source, decisions=tuple(reversed(old.decisions)),
    coverage=tuple(reversed(old.coverage)))
print(old.dataset_id == reordered.dataset_id)
```

Expected stdout:

```text
True
False
True
```
