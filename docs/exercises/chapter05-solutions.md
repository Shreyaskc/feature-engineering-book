# Chapter 5: implementation checks

Use `.venv/bin/python -B verify_all.py --chapter 05` for isolated verification. The notes below point to actual lab behavior; full manuscript solution text is maintained separately.

## Check 1: Preserve the fixed key

Exercise ID: `ch05-exercise01`.

The values are 50 and 85. Moving the event window would answer a different question.

## Check 2: Separate retry and revision

Exercise ID: `ch05-exercise02`.

A retry does not create another contribution; a valid new revision can replace an earlier contribution under the declared policy.

## Check 3: Challenge deadline equality

Exercise ID: `ch05-exercise03`.

The deadline is inclusive: an eligible delivery at 610 can participate, while one at 611 is reconciled after closure.

## Check 4: Read each denominator

Exercise ID: `ch05-exercise04`.

Coverage and matching-latest-version counts differ. The displayed aggregate errors are 50,55,15; none alone is a universal correctness score.

## Check 5: Repair the snapshot consumer

Exercise ID: `ch05-exercise05`.

Adding 50+45+85 produces the wrong value 180. The latest complete replacement is 85.

## Check 6: Remove the watermark trace

Exercise ID: `ch05-exercise06`.

The declared fixed deadline still controls publication; removing the trace does not alter the emitted snapshots.

## Check 7: Write a policy decision

Exercise ID: `ch05-exercise07`.

The immediate schedule emits 50,45,85 while the delayed schedule emits one 85 at 610. Document the latency/correction tradeoff and interpret metrics using their declared populations.

Inspect [chapter5.py](../../chapter05/chapter5.py) and [test_chapter5.py](../../chapter05/test_chapter5.py) for runnable evidence.
