# Reject corrupted retained content

Generated view; the canonical source remains authoritative.

Listing ID: `tamper_rejection`. Chapter: 10. Language: python.

Canonical source: [chapter10/printed_snippets.json](../../chapter10/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 10`. The root command checks the lesson and its listing expectations in clean copies.

```python
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from capstone_lab import CapstoneError, canonical, load_case
from capstone_lab import persist_run, verify_artifacts
with TemporaryDirectory() as directory:
    path = Path(directory) / "run"
    persist_run(load_case(), path)
    file = path / "improved_dataset.json"
    rows = json.loads(file.read_text())
    rows[0]["value"] = 51
    file.write_text(canonical(rows))
    try:
        verify_artifacts(path)
    except CapstoneError as error:
        assert str(error).startswith("artifact content mismatch:")
        print(error)
    else:
        raise AssertionError("corruption went undetected")
```

Expected stdout:

```text
artifact content mismatch: improved_dataset.json
```
