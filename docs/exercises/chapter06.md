# Chapter 6: code-first practice

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 06`. Predict each observation, inspect the implementation, then compare tests and expected outputs. These independently written lab instructions retain the chapter exercise IDs and concepts without reproducing the manuscript prose.

Implementation: [parity_lab.py](../../chapter06/parity_lab.py). Tests: [test_parity_lab.py](../../chapter06/test_parity_lab.py).

## Task 1: Recheck the feature key

Exercise ID: `ch06-exercise01`.

Compare the fixed-window key with a copied rolling-window key.

## Task 2: Trace two lag boundaries

Exercise ID: `ch06-exercise02`.

Inspect the request whose policy, store and cache views disagree.

## Task 3: Inspect an empty lookup

Exercise ID: `ch06-exercise03`.

Read the first raw value, missing flag and model fallback.

## Task 4: Respect policy closure

Exercise ID: `ch06-exercise04`.

Compare the final policy value with later source evidence.

## Task 5: Keep provenance in parity

Exercise ID: `ch06-exercise05`.

Change a logged publication revision while keeping its numeric value.

## Task 6: Remove one evidence field

Exercise ID: `ch06-exercise06`.

Inspect a log with an absent required field.

## Task 7: Choose numeric comparison rules

Exercise ID: `ch06-exercise07`.

Read numeric_equal and its finite-value tests.

## Task 8: Read the population

Exercise ID: `ch06-exercise08`.

Inspect the base parity metrics with missing values retained.

[Implementation checks](chapter06-solutions.md).
