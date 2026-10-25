# Contributing

Read [setup](docs/SETUP.md) and the [chapter map](docs/CHAPTER_MAP.md). Make experiments in a copy so the active lesson fixtures remain stable. Review code before executing imported changes. Core commands run offline and require no credentials.

Run `.venv/bin/python -B verify_all.py --source-only` for hashes, source syntax, provenance, chapter paths/functions, the two preserved refresher views and local documentation targets. This executes no lab code and is the hosted CI contract. Run `.venv/bin/python -B verify_all.py` on the Mac mini for the actual nine-suite check.

Every new acceptance packet must separately run `.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v`. These repository-harness methods are not silently included in the chapter-suite or readiness counts. Keep their complete result alongside both clean suite passes.

Review expected-output differences manually. Never rewrite expected results or manifests merely to obtain PASS. A deliberate lesson change must update its rationale, chapter/listing map, source difference record, and active file hash. Keep old provenance and record which manuscript listing IDs need updating.

The integrity boundaries are the nine active chapter directories in `LAB_FILES.json` and the separate beginner readiness directory in `PREREQUISITE_FILES.json`. Git metadata, wrapper documentation, CI and root evidence are outside that boundary; unexpected or altered lesson files fail. The original ZIP is hash checked separately. Checksums are local integrity checks, not signatures or a defense against replacing the checker and trusted hashes together.

Hosted CI has read-only permissions and runs no examples. Keep credentials, environment folders, temporary stores and private machine identifiers out of commits and archives. The lab software is MIT licensed as described in LICENSE_SCOPE.md. Keep manuscript text, covers, book-build sources and private identifiers outside this repository. Repository administration and new external integrations still require owner authorization.
