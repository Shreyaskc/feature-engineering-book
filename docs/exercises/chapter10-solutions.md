# Chapter 10: implementation checks

Use `.venv/bin/python -B verify_all.py --chapter 10` for isolated verification. The notes below point to actual lab behavior; full manuscript solution text is maintained separately.

## Check 1: Preserve original decisions

Exercise ID: `ch10-exercise01`.

Base D1/D2 are 50/95; challenge D1/D2 are 50/100. Later extraction does not rewrite their cutoffs.

## Check 2: Probe the closing boundary

Exercise ID: `ch10-exercise02`.

Equality is eligible under the inclusive deadline; later evidence does not reopen a closed publication.

## Check 3: Treat publications as replacements

Exercise ID: `ch10-exercise03`.

A publication is a full value. The replacement consumer retains the latest compatible revision instead of adding the history.

## Check 4: Reject contradictory source reuse

Exercise ID: `ch10-exercise04`.

The adapter rejects a conflicting source revision or reused delivery identity; it is not accepted as a retry.

## Check 5: Verify retained artifacts

Exercise ID: `ch10-exercise05`.

verify_artifacts rejects both direct content corruption and digests that disagree with recomputation.

## Check 6: Keep zero and unknown distinct

Exercise ID: `ch10-exercise06`.

The values are 0 and None with distinct flags and source evidence; the states are not interchangeable.

## Check 7: Explain denominators

Exercise ID: `ch10-exercise07`.

Each metric declares its evaluable/excluded population; do not combine unlike denominators into one success claim.

## Check 8: Hand off the challenge

Exercise ID: `ch10-exercise08`.

The closed fixed-window value is 90 and later audit value is 105. Late E accounts for the 15-unit difference; the policy stays closed.

Inspect [capstone_lab.py](../../chapter10/capstone_lab.py) and [test_capstone_lab.py](../../chapter10/test_capstone_lab.py) for runnable evidence.

Additional executable witnesses: [exercise_answers.py](../../chapter10/exercise_answers.py).
