# Chapter 4: implementation checks

Use `.venv/bin/python -B verify_all.py --chapter 04` for isolated verification. The notes below point to actual lab behavior; full manuscript solution text is maintained separately.

## Check 1: Inspect join row counts

Exercise ID: `ch04-exercise01`.

The customer join yields four rows; the decision join yields two correctly paired rows.

## Check 2: Check label eligibility

Exercise ID: `ch04-exercise02`.

Its label is not mature at that cutoff. The row is excluded instead of receiving a prematurely final label.

## Check 3: Probe the target interval

Exercise ID: `ch04-exercise03`.

The target interval is (decision_time, decision_time+120]; use label_at boundary tests to check the open and closed edges.

## Check 4: Freeze preprocessing state

Exercise ID: `ch04-exercise04`.

The training mean is 55; fitting on training plus validation would give 43 and leak evaluation information.

## Check 5: State the entity question

Exercise ID: `ch04-exercise05`.

The fixture evaluates a future mixture of returning and new entities. It is not an unseen-entity-only experiment.

## Check 6: Handle missing values deliberately

Exercise ID: `ch04-exercise06`.

The preserved listing uses a training mean of 35 and transforms [None,100] to [0,65]; it does not equate unknown history with a measured zero.

Inspect [chapter4.py](../../chapter04/chapter4.py) and [test_chapter4.py](../../chapter04/test_chapter4.py) for runnable evidence.
