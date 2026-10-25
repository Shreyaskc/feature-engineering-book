# Experiment in a copied chapter

Keep the verified repository intact while trying a change. The commands below were tested on the Mac mini using Chapter 3, outside the release tree. Start in the **repository root**, the directory containing `verify_all.py` and `.venv`:

```sh
project_root="$PWD"
lab_python="$project_root/.venv/bin/python"
experiment_dir="$(mktemp -d /tmp/feature-chapter03.XXXXXX)"
cp -R "$project_root/chapter03" "$experiment_dir/chapter03"
cd "$experiment_dir/chapter03"
"$lab_python" -B -m unittest discover -s . -p 'test_*.py' -v
"$lab_python" -B printed_examples.py
```

The working directory for both behavioral commands is the copied **`$experiment_dir/chapter03`**. `lab_python` retains the absolute interpreter path from the original venv, so copying the lesson does not copy, move or recreate the environment. Expected: **29 tests pass**, then the **nine printed listings** match their recorded output. The experiment evidence (local output not distributed) records both clean commands and the deliberate-failure checks below.

Run these direct commands in a copied chapter. Its `verify_lab.py` and `clean_verify.py` dispatch to the parent repository verifier and require the repository layout; they are not standalone experiment entry points. The behavioral commands above read the local copied code and fixture directly.

## Make one deliberate change

In the copied `fixtures/base.json`, change A1's amount from 20 to 21. Predict which historical answers will change. Rerun the same two behavioral commands from the copied chapter directory. Tests and printed-example checks should now fail because the fixture no longer satisfies the stated expected values; the observed run confirmed both nonzero exits. A failure is useful feedback about the change, not a reason to rewrite expected answers indiscriminately.

You may continue experimenting in the copy, or create another fresh copy to start over. The original chapter and its 72-listing book population remain unchanged. No root manifest is edited or disabled for an experiment.

## Verify the pristine release separately

Return to the original repository and run its integrity check:

```sh
cd "$project_root"
"$lab_python" -B verify_all.py --source-only
```

Expected: PASS and zero lab suites, even after the separate experiment has changed. For full original-release behavioral evidence, run `"$lab_python" -B verify_all.py` from that original root. If you intentionally edit an active repository lesson instead, a subsequent root hash failure is expected: review and restore the edit, or make a deliberate reviewed source/provenance update. Do not bypass the integrity check to hide it.
