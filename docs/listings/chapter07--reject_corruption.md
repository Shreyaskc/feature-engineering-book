# Validate before moving a release pointer

Generated view; the canonical source remains authoritative.

Listing ID: `reject_corruption`. Chapter: 7. Language: python.

Canonical source: [chapter07/printed_snippets.json](../../chapter07/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 07`. The root command checks the lesson and its listing expectations in clean copies.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from backfill_lab import (ContractError, ReleaseRegistry, ReleaseToken,
                          dataset_path, fixture_specs, load_dataset,
                          stage_build, publish_dataset)

with TemporaryDirectory() as folder:
    store, specs, ids = Path(folder), fixture_specs(), []
    for name in ("baseline", "extended_historical"):
        stage_build(store, name, specs[name])
        ids.append(publish_dataset(store, name, specs[name]).dataset_id)
    registry = ReleaseRegistry(store)
    before = registry.promote("historical", ids[0],
                              expected_current=ReleaseToken())
    dataset_path(store, ids[1]).write_bytes(b"broken\n")
    try:
        registry.promote("historical", ids[1], expected_current=before)
    except ContractError:
        print("corruption: rejected")
    print(registry.current("historical") == before)
    original = load_dataset(store, ids[0])
    print([row.value for row in original.records])
```

Expected stdout:

```text
corruption: rejected
True
[50, 95, 0]
```
