# Chapter 3: implementation checks

Use `.venv/bin/python -B verify_all.py --chapter 03` for isolated verification. The notes below point to actual lab behavior; full manuscript solution text is maintained separately.

## Check 1: Compare three queries

Exercise ID: `ch03-exercise01`.

The relevant values are D1=50, D2=95 and fixed-known-at-610=85, in both Python and SQLite.

## Check 2: Expose ranking order

Exercise ID: `ch03-exercise02`.

Availability must be filtered before selecting a winning revision; otherwise an unavailable revision hides an eligible older one.

## Check 3: Exercise all edges

Exercise ID: `ch03-exercise03`.

The lower event edge and availability equality are included; the upper event edge is excluded.

## Check 4: Follow the correction

Exercise ID: `ch03-exercise04`.

The values are 50, 45 and 85. Later knowledge can decrease a corrected aggregate.

## Check 5: Resolve a revision tie

Exercise ID: `ch03-exercise05`.

The greatest eligible source revision wins independently of transport order; inspect exercise_answers.py for the explicit fixture.

## Check 6: Keep the selected tombstone

Exercise ID: `ch03-exercise06`.

Rank eligible source versions including deletes, then decide whether the winning record contributes. Prefiltering deletes resurrects an older upsert.

## Check 7: Keep absence explicit

Exercise ID: `ch03-exercise07`.

The implementations agree on 0 for known empty and None/null for unknown coverage.

## Check 8: Reconstruct after replay

Exercise ID: `ch03-exercise08`.

Canonical source history and the original decision answer remain unchanged; the executable answer report verifies the result.

Inspect [historical_lab.py](../../chapter03/historical_lab.py) and [test_historical_lab.py](../../chapter03/test_historical_lab.py) for runnable evidence.

Additional executable witnesses: [exercise_answers.py](../../chapter03/exercise_answers.py).
