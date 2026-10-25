# Read the lab code: a short readiness lab

Complete this before Chapter 1, after the [environment check](../docs/SETUP.md). Allow about 15 minutes. You need only the installed Python standard library. The examples write no persistent data and make no network requests.

From the **repository root**:

```sh
.venv/bin/python -B verify_all.py --prerequisites-only
```

Expected: PASS, **12 readiness tests**, two matching clean runs, and zero chapter suites. Inspect `generated/prerequisites/run_1/commands.json` for observed output. The same readiness check runs before the nine chapter suites in the full command. It is a preparatory exercise, not Chapter 11 or a tenth chapter suite.

## 1. Run the two book refresher examples

Read the [Python values example](refresher-python.md) and [SQLite filtering example](refresher-sql.md) based on the reader draft's “Reading the lab code” section. The Python body is unchanged. The SQL lab body now wraps the connection in `closing(...)` while retaining the inner transaction context; the original book paragraph 2032 needs the same ownership correction. The [canonical refresher registry](book_refresher_examples.json) retains original source provenance and code hash alongside the corrected SQL hash. Generated views are checked against the current canonical bodies without executing them during rendering.

The Python example prints:

```text
[False, True, False]
True
```

The SQL example prints `50`. It has one version per event and teaches filtering by event window and availability. It does **not** teach revision ranking; that is a separate preview in step 6 and a full lesson in Chapter 3.

To see all micro-examples directly, still from the repository root:

```sh
.venv/bin/python -B prerequisites/readiness_lab.py
```

Its JSON must match [expected_output.json](expected_output.json). The full Mac observed output (generate locally with the readiness command) is retained separately.

## 2. Keep absence separate from truthiness

Find `absence_example` in [readiness_lab.py](readiness_lab.py). Predict the result for `[0, None, False, 50]`. Only `None` is absent. Zero and `False` are both falsy, and Python even compares `0 == False` as true; their types differ. Use `value is None` to ask whether a value is absent. Each chapter separately defines which value types its contract accepts.

Expected absence flags: `[false, true, false, false]`. Expected type names: `int`, `NoneType`, `bool`, `int`. A blanket `if not value` cannot implement that missingness policy.

## 3. Read an immutable record

`Event` is a frozen dataclass with four scalar fields. Assigning `original.amount = 25` raises `FrozenInstanceError`; `replace(original, amount=25)` creates a new record while the original remains 20. Read `record_example`, then find the two tests protecting these observations. This is local record behavior, not durable or distributed storage.

## 4. Read the clocks and boundaries

`event_time` says when the activity happened. `available_at` says when its information could be used. For `[540,600)` at cutoff 600, time 540 is included and event time 600 is excluded; availability exactly 600 is allowed. Predict `boundary_example` before running it: base 50, lower-boundary addition 55, upper-boundary addition 50, cutoff equality 55, later availability 50.

## 5. Read a fixture and an assertion

A fixture is a small repeatable input whose answer you can calculate independently. Inspect [fixtures/readiness.json](fixtures/readiness.json). At cutoff 600, A contributes 20 and C contributes 30; B is available only at 607. The assertion checks `20 + 30 == 50`. A failing assertion identifies a violated expectation; it is not permission to rewrite the expected answer.

The [tests](test_readiness_lab.py) test each boundary and a few deliberately wrong alternatives. To experiment with changes, use the [copied-chapter workflow](../docs/EXPERIMENTING.md); retain the pristine source and its integrity checks.

## 6. Preview two SQL mistakes

`sql_example` is an additional preview, separate from the SQL filtering refresher. Joining two C1 decisions to two C1 feature rows by customer produces **four rows**. Joining by decision identity produces **two**: D1=50 and D2=95. Chapter 4 explains the full row-grain and label contracts.

The revision preview keeps `[540,600)` fixed. At cutoff 600, filter availability **before** ranking the greatest revision per event: the answer is **50**. Ranking first hides eligible C1 behind unavailable C2 and incorrectly gives **20**. At cutoff 610, the fixed-window answer is **85**. This is not D2's rolling `[550,610)` value of 95. Chapter 3 adds the full corrected-event selection contract.

When these outputs are explainable, continue to the [chapter map](../docs/CHAPTER_MAP.md). All records are synthetic; the source chapter contracts remain authoritative.
