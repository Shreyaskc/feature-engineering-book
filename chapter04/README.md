# chapter04

From the repository root, run:

```sh
.venv/bin/python -B verify_all.py --chapter 04
```

The runner uses fresh temporary copies and retains outputs under root `generated/`. See [chapter map](../docs/CHAPTER_MAP.md) for concepts, source functions, exercises and expected results. See [imported lesson explanation](../provenance/CODE_BASELINE.json) for its detailed contract; its runtime/build commands and recorded checksums describe the upstream release.

Event IDs are global within this synthetic source, following Chapter 2. Canonical versions use `(event, version)`; customer and event time are immutable across versions. Reusing an event ID under another customer rejects the complete input before feature filtering, including when no dataset decisions remain. Different customers may have distinct event IDs. Identical retries still deduplicate. Normal fixture rows and printed listings are unchanged.

The imported `dataset_manifest.json` and original provenance archive retain historical metadata. A newly generated manifest records the corrected global identity and current code hash; the verifier checks the explicit reviewed transition without changing the historical snapshot or other semantic expectations.
