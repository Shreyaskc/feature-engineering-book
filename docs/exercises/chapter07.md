# Chapter 7: code-first practice

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 07`. Predict each observation, inspect the implementation, then compare tests and expected outputs. These independently written lab instructions retain the chapter exercise IDs and concepts without reproducing the manuscript prose.

Implementation: [backfill_lab.py](../../chapter07/backfill_lab.py). Tests: [test_backfill_lab.py](../../chapter07/test_backfill_lab.py).

## Task 1: Predict build vectors

Exercise ID: `ch07-exercise01`.

Compare baseline, extended historical, corrected and changed-definition runs.

## Task 2: Compare identities with equal rows

Exercise ID: `ch07-exercise02`.

Build from the two historical source snapshots and compare output values and dataset IDs.

## Task 3: Resume the same build

Exercise ID: `ch07-exercise03`.

Stop after one chunk, resume, then replay the completed attempt.

## Task 4: Mark coverage unknown

Exercise ID: `ch07-exercise04`.

Change only one declared coverage flag.

## Task 5: Inspect the manifest

Exercise ID: `ch07-exercise05`.

Compare an output row count with the full immutable specification.

## Task 6: Reject a stale release token

Exercise ID: `ch07-exercise06`.

Promote another dataset, then reuse an older expected-current token.

## Task 7: Use a compatible channel

Exercise ID: `ch07-exercise07`.

Try promoting a corrected or changed-window dataset to the historical channel.

## Task 8: Test retained evidence loss

Exercise ID: `ch07-exercise08`.

Remove or corrupt a retained dataset/checkpoint only in an experimental store.

[Implementation checks](chapter07-solutions.md).
