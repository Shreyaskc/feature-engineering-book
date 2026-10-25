# Source and local validation

Run `python3 -B verify_all.py --source-only` for file identities, Python syntax, chapter targets, canonical listings and local links. It does not run lesson code. `--check-env` checks the interpreter, SQLite support and temporary-file access.

Run `python3 -B verify_all.py --prerequisites-only` for the separate readiness module or `--chapter 03` for one lesson. The full verifier executes selected lessons twice in clean copies and compares their synthetic semantic contracts. Run repository guards separately with `python3 -B -m unittest discover -s tests -v`.

Inspect each exit status and generated local report. A successful static check is not a lab execution result or production guarantee. No private historical execution logs are shipped. Expected synthetic results are teaching contracts, not measurements of external systems.
