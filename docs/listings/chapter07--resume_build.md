# Restart from verified chunks

Generated view; the canonical source remains authoritative.

Listing ID: `resume_build`. Chapter: 7. Language: python.

Canonical source: [chapter07/printed_snippets.json](../../chapter07/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 07`. The root command checks the lesson and its listing expectations in clean copies.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from backfill_lab import make_spec, stage_build, publish_dataset

with TemporaryDirectory() as folder:
    store, spec = Path(folder), make_spec()
    first = stage_build(store, "attempt", spec, stop_after_chunks=1)
    resumed = stage_build(store, "attempt", spec)
    replayed = stage_build(store, "attempt", spec)
    dataset = publish_dataset(store, "attempt", spec)
    print(first.next_index, first.complete)
    print(resumed.next_index, resumed.complete)
    print(replayed == resumed, len(dataset.records))
```

Expected stdout:

```text
1 False
3 True
True 3
```
