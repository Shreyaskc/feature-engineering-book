# Chapter 1: implementation checks

Use `.venv/bin/python -B verify_all.py --chapter 01` for isolated verification. The notes below point to actual lab behavior; full manuscript solution text is maintained separately.

## Check 1: Specify the request

Exercise ID: `ch01-exercise01`.

For the base request, C1 uses [540,600), availability at or before 600, and known coverage. The declared answer is 50; a changed rule needs a distinct expectation.

## Check 2: Explain the contributions

Exercise ID: `ch01-exercise02`.

The window contributions are event A revision 1 (20) and event C revision 1 (30). D's event time 602 is outside [540,600); D is available at 603. The C correction still has event time 585 but is unavailable until 605. B is unavailable until 607. Event-window membership and availability cutoff are separate checks.

## Check 3: Move the event edges

Exercise ID: `ch01-exercise03`.

The lower edge is included and produces 55. The upper edge is excluded and leaves 50. These are separate fixture variations.

## Check 4: Distinguish empty and unavailable

Exercise ID: `ch01-exercise04`.

Known empty produces 0; unknown coverage produces None. The fixture report exposes both states.

## Check 5: Identify a definition change

Exercise ID: `ch01-exercise05`.

A new duration or membership rule needs a separately identified definition and reviewed expectations. Agreement on one fixture does not establish equivalent contracts.

## Check 6: Review a passing calculation

Exercise ID: `ch01-exercise06`.

Check membership and timing as well as the value: at the first decision event A revision 1 and event C revision 1 contribute 20+30. A numeric answer without the declared selection evidence is insufficient.

Inspect [foundations_lab.py](../../chapters01_02/foundations_lab.py) and [test_foundations_lab.py](../../chapters01_02/test_foundations_lab.py) for runnable evidence.
