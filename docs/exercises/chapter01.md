# Chapter 1: code-first practice

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 01`. Predict each observation, inspect the implementation, then compare tests and expected outputs. These independently written lab instructions retain the chapter exercise IDs and concepts without reproducing the manuscript prose.

Implementation: [foundations_lab.py](../../chapters01_02/foundations_lab.py). Tests: [test_foundations_lab.py](../../chapters01_02/test_foundations_lab.py).

## Task 1: Specify the request

Exercise ID: `ch01-exercise01`.

Name the entity, units, event interval, availability cutoff and coverage assumption before calling the function.

## Task 2: Explain the contributions

Exercise ID: `ch01-exercise02`.

Identify which source versions supply the base answer and why later or out-of-window records are absent.

## Task 3: Move the event edges

Exercise ID: `ch01-exercise03`.

Add a five-unit event at minute 540, then separately add a seven-unit event at minute 600.

## Task 4: Distinguish empty and unavailable

Exercise ID: `ch01-exercise04`.

Compare complete empty history with a query whose coverage is unknown.

## Task 5: Identify a definition change

Exercise ID: `ch01-exercise05`.

Change the declared duration or membership rule in an experiment and decide whether to retain the original definition identity.

## Task 6: Review a passing calculation

Exercise ID: `ch01-exercise06`.

Explain why a completed run or nonnegative aggregate is insufficient evidence that the intended feature was calculated.

[Implementation checks](chapter01-solutions.md).
