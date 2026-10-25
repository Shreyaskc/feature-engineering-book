# Chapter 6: implementation checks

Use `.venv/bin/python -B verify_all.py --chapter 06` for isolated verification. The notes below point to actual lab behavior; full manuscript solution text is maintained separately.

## Check 1: Recheck the feature key

Exercise ID: `ch06-exercise01`.

At cutoff 610 the fixed key gives 85 and the rolling key gives 95.

## Check 2: Trace two lag boundaries

Exercise ID: `ch06-exercise02`.

At the documented delayed request the expected policy is 85, store is 45 and cache is 50, exposing separate lag causes.

## Check 3: Inspect an empty lookup

Exercise ID: `ch06-exercise03`.

The raw value is None, while the explicit fallback model input is 0. A fallback is not a measured source zero.

## Check 4: Respect policy closure

Exercise ID: `ch06-exercise04`.

The policy remains 85 after closure while the late-E source reference becomes 100; that alone is not a policy defect.

## Check 5: Keep provenance in parity

Exercise ID: `ch06-exercise05`.

A numeric match can coexist with a provenance mismatch; reconcile keeps those findings separate.

## Check 6: Remove one evidence field

Exercise ID: `ch06-exercise06`.

Missing evidence makes the corresponding comparison unverifiable; it must not silently pass as agreement.

## Check 7: Choose numeric comparison rules

Exercise ID: `ch06-exercise07`.

Use declared tolerances for finite floating-point values. Do not infer a tolerance only after inspecting a failed score.

## Check 8: Read the population

Exercise ID: `ch06-exercise08`.

Raw policy numeric agreement is 3/5, while the full-policy population is 3/6; the exclusions and evaluable counts are explicit.

Inspect [parity_lab.py](../../chapter06/parity_lab.py) and [test_parity_lab.py](../../chapter06/test_parity_lab.py) for runnable evidence.
