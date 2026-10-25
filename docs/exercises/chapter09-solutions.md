# Chapter 9: implementation checks

Use `.venv/bin/python -B verify_all.py --chapter 09` for isolated verification. The notes below point to actual lab behavior; full manuscript solution text is maintained separately.

## Check 1: Account for every request

Exercise ID: `ch09-exercise01`.

The missing and fallback rates are each 1/6 in the base trace; populations stay explicit.

## Check 2: Distinguish age from lag

Exercise ID: `ch09-exercise02`.

An old publication can still have zero policy lag. The recorded R5 publication age is 13 with policy lag 0.

## Check 3: Retain uncertainty

Exercise ID: `ch09-exercise03`.

Unknown evidence must remain unknown and cannot make an incompatible or incomplete cohort healthy.

## Check 4: Test a consumer hypothesis

Exercise ID: `ch09-exercise04`.

Replacement gives 85; addition gives 180. Controlled baseline/candidate replay scores are 4/4 and 0/4.

## Check 5: Reject agreement on a wrong contract

Exercise ID: `ch09-exercise05`.

Numeric agreement cannot establish the correct semantic contract; identity and lineage checks remain required.

## Check 6: Separate finding from action

Exercise ID: `ch09-exercise06`.

A contract failure and a local rollback recommendation are distinct. No real external rollback is executed.

## Check 7: Expire recovery evidence

Exercise ID: `ch09-exercise07`.

The local decision holds when required recovery evidence is unavailable or expired.

## Check 8: Require a fresh recovery replay

Exercise ID: `ch09-exercise08`.

The preserved local simulation reports RECOVERED and 4/4 full-model parity; it is not proof of service recovery.

Inspect [operations_lab.py](../../chapter09/operations_lab.py) and [test_operations_lab.py](../../chapter09/test_operations_lab.py) for runnable evidence.

Additional executable witnesses: [exercise_answers.py](../../chapter09/exercise_answers.py).
