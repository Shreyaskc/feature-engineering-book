# Rollback preserves data and advances generation

Generated view; the canonical source remains authoritative.

Listing ID: `rollback_and_stale_token`. Chapter: 7. Language: python.

Canonical source: [chapter07/printed_snippets.json](../../chapter07/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 07`. The root command checks the lesson and its listing expectations in clean copies.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from backfill_lab import (ContractError, ReleaseRegistry, ReleaseToken,
                          fixture_specs, stage_build, publish_dataset)

with TemporaryDirectory() as folder:
    store, specs = Path(folder), fixture_specs()
    ids = []
    for name in ("baseline", "extended_historical"):
        stage_build(store, name, specs[name])
        ids.append(publish_dataset(store, name, specs[name]).dataset_id)
    registry = ReleaseRegistry(store)
    one = registry.promote("historical", ids[0],
                           expected_current=ReleaseToken())
    two = registry.promote("historical", ids[1], expected_current=one)
    three = registry.rollback("historical", ids[0], expected_current=two)
    print(one.generation, two.generation, three.generation)
    print(one.dataset_id == three.dataset_id)
    try:
        registry.promote("historical", ids[1], expected_current=one)
    except ContractError:
        print("stale generation: rejected")
```

Expected stdout:

```text
1 2 3
True
stale generation: rejected
```
