# Protect the historical channel

Generated view; the canonical source remains authoritative.

Listing ID: `reject_corrected_promotion`. Chapter: 7. Language: python.

Canonical source: [chapter07/printed_snippets.json](../../chapter07/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 07`. The root command checks the lesson and its listing expectations in clean copies.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from backfill_lab import (ContractError, ReleaseRegistry, ReleaseToken,
                          fixture_specs, stage_build, publish_dataset)

with TemporaryDirectory() as folder:
    store, spec = Path(folder), fixture_specs()["corrected"]
    stage_build(store, "attempt", spec)
    dataset = publish_dataset(store, "attempt", spec)
    registry = ReleaseRegistry(store)
    try:
        registry.promote("historical", dataset.dataset_id,
                         expected_current=ReleaseToken())
    except ContractError:
        print("corrected to historical: rejected")
    print(registry.current("historical").generation)
```

Expected stdout:

```text
corrected to historical: rejected
0
```
