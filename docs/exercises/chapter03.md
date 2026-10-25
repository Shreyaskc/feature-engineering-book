# Chapter 3: code-first practice

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 03`. Predict each observation, inspect the implementation, then compare tests and expected outputs. These independently written lab instructions retain the chapter exercise IDs and concepts without reproducing the manuscript prose.

Implementation: [historical_lab.py](../../chapter03/historical_lab.py). Tests: [test_historical_lab.py](../../chapter03/test_historical_lab.py).

## Task 1: Compare three queries

Exercise ID: `ch03-exercise01`.

Run historical, rolling-later and fixed-window-later queries on the same base history.

## Task 2: Expose ranking order

Exercise ID: `ch03-exercise02`.

Compare the reference selector with wrong_latest_then_availability.

## Task 3: Exercise all edges

Exercise ID: `ch03-exercise03`.

Use records on the lower event edge, upper event edge and availability cutoff.

## Task 4: Follow the correction

Exercise ID: `ch03-exercise04`.

Inspect fixed-window results at cutoffs 604, 605 and 607.

## Task 5: Resolve a revision tie

Exercise ID: `ch03-exercise05`.

Give two revisions equal availability and reverse their input order.

## Task 6: Keep the selected tombstone

Exercise ID: `ch03-exercise06`.

Compare normal selection with a query that removes deletes before ranking.

## Task 7: Keep absence explicit

Exercise ID: `ch03-exercise07`.

Run known-empty and unknown-coverage SQL/Python queries.

## Task 8: Reconstruct after replay

Exercise ID: `ch03-exercise08`.

Replay duplicate and reversed deliveries before running the historical query.

[Implementation checks](chapter03-solutions.md).
