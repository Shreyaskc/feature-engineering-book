# Chapter 2: implementation checks

Use `.venv/bin/python -B verify_all.py --chapter 02` for isolated verification. The notes below point to actual lab behavior; full manuscript solution text is maintained separately.

## Check 1: Replay one delivery

Exercise ID: `ch02-exercise01`.

The demonstration has six deliveries but five source revisions; first availability stays 551 and D1 stays 50.

## Check 2: Reject a contradictory retry

Exercise ID: `ch02-exercise02`.

Ingestion raises ContractError; the conflicting record is not accepted as a new fact.

## Check 3: Reverse transport order

Exercise ID: `ch02-exercise03`.

Canonical history and feature answers are unchanged; input order does not choose the source revision.

## Check 4: Check batch atomicity

Exercise ID: `ch02-exercise04`.

The whole candidate batch is rejected and the previously accepted ledger remains unchanged.

## Check 5: Trace deletion and restoration

Exercise ID: `ch02-exercise05`.

The fixed window at cutoff 620 is 60 after deletion and 88 after the opt-in restoration. Earlier decision answers remain unchanged; implicit restoration is rejected.

## Check 6: Declare identity namespaces

Exercise ID: `ch02-exercise06`.

Within this ledger an event ID names one source history with a stable entity. Delivery IDs name transport attempts. A cross-source system must declare its identifier namespace.

## Check 7: Bound the guarantee

Exercise ID: `ch02-exercise07`.

These tests establish local canonicalization and rejection behavior. They do not establish distributed delivery guarantees, cross-system transactions or actual service recovery.

Inspect [foundations_lab.py](../../chapters01_02/foundations_lab.py) and [test_foundations_lab.py](../../chapters01_02/test_foundations_lab.py) for runnable evidence.
