# Chapter 8: implementation checks

Use `.venv/bin/python -B verify_all.py --chapter 08` for isolated verification. The notes below point to actual lab behavior; full manuscript solution text is maintained separately.

## Check 1: Compare fault populations

Exercise ID: `ch08-exercise01`.

The weak suite detects 1/5 selected faults and the diagnostic suite 5/5. These are five declared variants, not every possible defect.

## Check 2: Reject a false monotonicity rule

Exercise ID: `ch08-exercise02`.

The valid sequence 50,45,85 disproves the claim that later knowledge must always increase the sum.

## Check 3: Target an event boundary

Exercise ID: `ch08-exercise03`.

The correct half-open contract excludes it; the inclusive-upper teaching fault becomes observable.

## Check 4: Check schema before arithmetic

Exercise ID: `ch08-exercise04`.

The reference adapter rejects invalid evidence. Supplying a default time would invent information.

## Check 5: Challenge relation-only tests

Exercise ID: `ch08-exercise05`.

Some replay/shuffle relations still pass, while hand-calculated and coverage checks expose the constant implementation.

## Check 6: Classify failed runs

Exercise ID: `ch08-exercise06`.

Only an expected assertion mismatch is a detected selected fault; an unexpected harness error is not counted as success.

## Check 7: Keep a small witness

Exercise ID: `ch08-exercise07`.

The witness records both the reference observation and the faulty observation, making the counterexample explainable.

## Check 8: State what passed

Exercise ID: `ch08-exercise08`.

Finite generated cases and five chosen faults provide bounded evidence, not a proof of production correctness.

Inspect [fault_testing_lab.py](../../chapter08/fault_testing_lab.py) and [test_fault_testing_lab.py](../../chapter08/test_fault_testing_lab.py) for runnable evidence.

Additional executable witnesses: [exercise_answers.py](../../chapter08/exercise_answers.py).
