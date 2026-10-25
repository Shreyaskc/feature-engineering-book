# Refuse to resume a different run

Generated view; the canonical source remains authoritative.

Listing ID: `reject_changed_resume`. Chapter: 7. Language: python.

Canonical source: [chapter07/printed_snippets.json](../../chapter07/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 07`. The root command checks the lesson and its listing expectations in clean copies.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from backfill_lab import ContractError, fixture_specs, stage_build

with TemporaryDirectory() as folder:
    store, specs = Path(folder), fixture_specs()
    stage_build(store, "attempt", specs["baseline"],
                stop_after_chunks=1)
    try:
        stage_build(store, "attempt", specs["extended_historical"])
    except ContractError:
        print("changed source: rejected")
    print(stage_build(store, "attempt", specs["baseline"]).complete)
```

Expected stdout:

```text
changed source: rejected
True
```
