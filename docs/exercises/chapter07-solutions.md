# Chapter 7: implementation checks

Use `.venv/bin/python -B verify_all.py --chapter 07` for isolated verification. The notes below point to actual lab behavior; full manuscript solution text is maintained separately.

## Check 1: Predict build vectors

Exercise ID: `ch07-exercise01`.

Historical rows stay [50,95,0]; the corrected branch is [102,112,0], and the changed definition is [30,35,0].

## Check 2: Compare identities with equal rows

Exercise ID: `ch07-exercise02`.

Equal rows do not erase different source provenance; the dataset identities differ.

## Check 3: Resume the same build

Exercise ID: `ch07-exercise03`.

The retained example advances from one row to three, completes, and replays without changing the result.

## Check 4: Mark coverage unknown

Exercise ID: `ch07-exercise04`.

The corresponding output becomes None and the build identity changes; missingness is part of the run contract.

## Check 5: Inspect the manifest

Exercise ID: `ch07-exercise05`.

A matching count cannot establish matching source, definition, runtime or code provenance.

## Check 6: Reject a stale release token

Exercise ID: `ch07-exercise06`.

The stale token is rejected, including after a rollback has advanced the release generation.

## Check 7: Use a compatible channel

Exercise ID: `ch07-exercise07`.

Incompatible definitions are rejected; separate declared channels retain their own contracts.

## Check 8: Test retained evidence loss

Exercise ID: `ch07-exercise08`.

Readback and resume reject missing or invalid evidence rather than reconstructing a fabricated successful release.

Inspect [backfill_lab.py](../../chapter07/backfill_lab.py) and [test_backfill_lab.py](../../chapter07/test_backfill_lab.py) for runnable evidence.
