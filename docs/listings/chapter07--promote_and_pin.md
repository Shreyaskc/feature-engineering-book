# Release a dataset and pin an experiment

Generated view; the canonical source remains authoritative.

Listing ID: `promote_and_pin`. Chapter: 7. Language: python.

Canonical source: [chapter07/printed_snippets.json](../../chapter07/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 07`. The root command checks the lesson and its listing expectations in clean copies.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from backfill_lab import (Experiment, ReleaseRegistry, ReleaseToken,
                          fixture_specs, stage_build, publish_dataset)

with TemporaryDirectory() as folder:
    store, specs, ids = Path(folder), fixture_specs(), []
    for name in ("baseline", "extended_historical"):
        stage_build(store, name, specs[name])
        ids.append(publish_dataset(store, name, specs[name]).dataset_id)
    experiment = Experiment("baseline_trial", ids[0])
    registry = ReleaseRegistry(store)
    first = registry.promote("historical", ids[0],
                             expected_current=ReleaseToken())
    current = registry.promote("historical", ids[1],
                               expected_current=first)
    print(current.generation)
    print([row.value for row in experiment.read(store).records])
    print(experiment.dataset_id == current.dataset_id)
```

Expected stdout:

```text
2
[50, 95, 0]
False
```
