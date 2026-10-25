# Chapter 4: code-first practice

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 04`. Predict each observation, inspect the implementation, then compare tests and expected outputs. These independently written lab instructions retain the chapter exercise IDs and concepts without reproducing the manuscript prose.

Implementation: [chapter4.py](../../chapter04/chapter4.py). Tests: [test_chapter4.py](../../chapter04/test_chapter4.py).

## Task 1: Inspect join row counts

Exercise ID: `ch04-exercise01`.

Join two feature rows to two decisions by customer, then by decision identity.

## Task 2: Check label eligibility

Exercise ID: `ch04-exercise02`.

Inspect why D4 is excluded at the fit cutoff despite an observed outcome.

## Task 3: Probe the target interval

Exercise ID: `ch04-exercise03`.

Place outcomes on each edge of the declared label horizon.

## Task 4: Freeze preprocessing state

Exercise ID: `ch04-exercise04`.

Fit centering on the training rows and compare with an all-row fit.

## Task 5: State the entity question

Exercise ID: `ch04-exercise05`.

Read the manifest before interpreting validation results.

## Task 6: Handle missing values deliberately

Exercise ID: `ch04-exercise06`.

Run fit_center and transform with a missing training input.

[Implementation checks](chapter04-solutions.md).
