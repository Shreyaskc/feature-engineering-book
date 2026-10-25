# Inspect the immutable build contract

Generated view; the canonical source remains authoritative.

Listing ID: `inspect_manifest`. Chapter: 7. Language: python.

Canonical source: [chapter07/printed_snippets.json](../../chapter07/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 07`. The root command checks the lesson and its listing expectations in clean copies.

```python
from backfill_lab import Dataset, make_spec, materialize

spec = make_spec()
manifest = Dataset(spec, materialize(spec)).manifest
bound = manifest["spec"]
print(bound["definition"]["feature_name"])
print(bound["definition"]["window_minutes"],
      bound["definition"]["mode"])
print(len(bound["source"]), len(bound["decisions"]))
print(sorted(bound["code"]))
print(bool(bound["runtime"]), manifest["record_count"])
```

Expected stdout:

```text
spend_before_decision
60 historical
5 3
['backfill_lab.py', 'foundations_lab.py']
True 3
```
