# Chapter 2: code-first practice

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 02`. Predict each observation, inspect the implementation, then compare tests and expected outputs. These independently written lab instructions retain the chapter exercise IDs and concepts without reproducing the manuscript prose.

Implementation: [foundations_lab.py](../../chapters01_02/foundations_lab.py). Tests: [test_foundations_lab.py](../../chapters01_02/test_foundations_lab.py).

## Task 1: Replay one delivery

Exercise ID: `ch02-exercise01`.

Resubmit the existing A1 source revision under a new delivery ID.

## Task 2: Reject a contradictory retry

Exercise ID: `ch02-exercise02`.

Change a payload while reusing the same source event and revision.

## Task 3: Reverse transport order

Exercise ID: `ch02-exercise03`.

Ingest the base deliveries in reverse order and compare the resulting ledger.

## Task 4: Check batch atomicity

Exercise ID: `ch02-exercise04`.

Place a valid new delivery and a conflicting delivery in the same candidate batch.

## Task 5: Trace deletion and restoration

Exercise ID: `ch02-exercise05`.

Use the named deletion fixture, then the explicit restoration policy, while retaining the original historical decisions.

## Task 6: Declare identity namespaces

Exercise ID: `ch02-exercise06`.

Inspect the ledger keys and explain what is needed before event IDs can be reused across source systems.

## Task 7: Bound the guarantee

Exercise ID: `ch02-exercise07`.

State what the local replay and candidate-batch tests establish and which deployment claims need other evidence.

[Implementation checks](chapter02-solutions.md).
