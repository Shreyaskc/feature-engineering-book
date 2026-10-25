# Persist and verify retained artifacts

Generated view; the canonical source remains authoritative.

Listing ID: `manifest_readback`. Chapter: 10. Language: python.

Canonical source: [chapter10/printed_snippets.json](../../chapter10/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 10`. The root command checks the lesson and its listing expectations in clean copies.

```python
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from capstone_lab import load_case, persist_run, verify_artifacts
with TemporaryDirectory() as directory:
    path = Path(directory) / "run"
    written = persist_run(load_case(), path)
    checked = verify_artifacts(path)
    manifest = json.loads((path / "manifest.json").read_text())
    print(written == checked, checked["artifacts_verified"])
    print(manifest["training_boundary"]["artifact_kind"])
```

Expected stdout:

```text
True 9
feature_dataset_only
```
