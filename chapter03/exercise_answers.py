"""Executable answers to the eight manuscript exercises, in chapter order."""
from dataclasses import replace
import json

from foundations_lab import ContractError, Delivery, Ledger, Revision, ingest
from historical_lab import (Query, load_fixture, reference_value, sqlite_value,
                            wrong_latest_then_availability)
from sqlite_lab import connect


def both(ledger: Ledger, query: Query) -> int | None:
    reference, sql = reference_value(ledger, query), sqlite_value(ledger, query)
    if reference != sql:
        raise AssertionError("reference/SQLite disagreement")
    return reference


def add(ledger: Ledger, *rows: Revision) -> Ledger:
    return ingest(ledger, [Delivery(f"exercise-{r.event_id}-{r.revision}", r,
                                   r.available_at) for r in rows])


def answers() -> dict:
    base = load_fixture()
    d1 = Query("C1", 540, 600, 600)
    fixed = lambda cutoff: Query("C1", 540, 600, cutoff)
    answer = {}
    answer["exercise_1"] = {
        "D1": {"value": both(base, d1), "terms": [20, 30]},
        "D2": {"value": both(base, Query("C1", 550, 610, 610)),
               "terms": [20, 40, 25, 10]},
        "fixed_known_610": {"value": both(base, fixed(610)),
                            "terms": [20, 40, 25]},
        "why": "D2 changes both the window and knowledge cutoff; fixed_known_610 changes only knowledge."}
    answer["exercise_2"] = {
        "correct": both(base, d1),
        "wrong_latest_first": wrong_latest_then_availability(base, d1),
        "why": "Selecting C2 first and then rejecting it at 600 loses eligible C1; filter availability before choosing a revision."}
    boundary = add(base, Revision("K", 1, "C1", 540, 541, 5),
                   Revision("L", 1, "C1", 600, 600, 7),
                   Revision("M", 1, "C1", 599, 600, 3))
    delayed = Ledger(tuple(
        replace(d, record=replace(d.record, available_at=601), delivered_at=601)
        if d.record.event_id == "M" else d for d in boundary.deliveries))
    answer["exercise_3"] = {
        "K_L_M_together": both(boundary, d1),
        "M_availability_601": both(delayed, d1),
        "why": "540 is included, 600 event time is excluded, and availability exactly 600 is eligible."}
    answer["exercise_4"] = {
        "by_cutoff": {str(t): both(base, fixed(t)) for t in (604, 605, 606, 607)},
        "original_600": both(base, d1),
        "why": "C changes from 30 to 25 at 605; B adds 40 at 607. Later knowledge is not a monotone sum."}
    tied = add(base, Revision("C", 3, "C1", 585, 605, 22))
    answer["exercise_5"] = {
        "by_cutoff": {str(t): both(tied, fixed(t)) for t in (604, 605, 607)},
        "why": "C2 and C3 become eligible together; the greatest eligible revision, C3, wins."}
    deletion, restoration = load_fixture("deletion_extension"), load_fixture("restoration_extension")
    connection = connect(deletion, fixed(620))
    try:
        wrong_deleted_first = connection.execute("""
            WITH ranked AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY event_id ORDER BY revision DESC
                ) AS position
                FROM revisions WHERE available_at <= :known_at AND op = 'upsert'
            )
            SELECT COALESCE(SUM(amount), 0) FROM ranked
            WHERE position = 1 AND customer_id = :customer_id
              AND event_time >= :window_start AND event_time < :window_end
        """, fixed(620).parameters()).fetchone()[0]
    finally:
        connection.close()
    try:
        Ledger(restoration.deliveries)
    except ContractError:
        default_restoration_rejected = True
    else:
        raise AssertionError("restoration must require opt-in")
    answer["exercise_6"] = {
        "deleted_at_620": both(deletion, fixed(620)),
        "restoration_at_619": both(restoration, fixed(619)),
        "restoration_at_620": both(restoration, fixed(620)),
        "wrong_delete_prefilter": wrong_deleted_first,
        "default_restoration_rejected": default_restoration_rejected,
        "why": "C3 must win before its delete operation excludes it; removing tombstones first resurrects C2."}
    answer["exercise_7"] = {
        "known_empty_C9": both(base, Query("C9", 540, 600, 600)),
        "unknown_C9": both(base, Query("C9", 540, 600, 600, False)),
        "unknown_C1": both(base, Query("C1", 540, 600, 600, False)),
        "why": "Coverage is external evidence; neither an empty result nor supplied partial rows establish it."}
    retry = Delivery("a1-retry", base.history[0], 609)
    replayed = Ledger(tuple(reversed(ingest(base, [retry]).deliveries)))
    # This is deliberately falsified source evidence, built from scratch.
    # Ingesting such a changed A1 into the authentic ledger would reject.
    falsified = Ledger(tuple(
        replace(d, record=replace(d.record, available_at=609), delivered_at=609)
        if d.record.event_id == "A" else d for d in base.deliveries))
    answer["exercise_8"] = {
        "deliveries": len(replayed.deliveries), "versions": len(replayed.history),
        "A_available_at": replayed.history[0].available_at,
        "original_value": both(replayed, d1),
        "wrong_rewritten_availability": both(falsified, d1),
        "why": "A retry at 609 preserves first availability 551. Replacing that evidence with 609 incorrectly hides A at 600."}
    expected = {
        "e1": (50, 95, 85), "e2": (50, 20), "e3": (58, 55),
        "e4": (50, 45, 45, 85, 50), "e5": (50, 42, 82),
        "e6": (60, 60, 88, 85, True), "e7": (0, None, None),
        "e8": (6, 5, 551, 50, 30)}
    actual = {
        "e1": tuple(answer["exercise_1"][k]["value"] for k in ("D1", "D2", "fixed_known_610")),
        "e2": tuple(answer["exercise_2"][k] for k in ("correct", "wrong_latest_first")),
        "e3": tuple(answer["exercise_3"][k] for k in ("K_L_M_together", "M_availability_601")),
        "e4": (*answer["exercise_4"]["by_cutoff"].values(), answer["exercise_4"]["original_600"]),
        "e5": tuple(answer["exercise_5"]["by_cutoff"].values()),
        "e6": tuple(answer["exercise_6"][k] for k in ("deleted_at_620", "restoration_at_619", "restoration_at_620", "wrong_delete_prefilter", "default_restoration_rejected")),
        "e7": tuple(answer["exercise_7"][k] for k in ("known_empty_C9", "unknown_C9", "unknown_C1")),
        "e8": tuple(answer["exercise_8"][k] for k in ("deliveries", "versions", "A_available_at", "original_value", "wrong_rewritten_availability"))}
    if actual != expected:
        raise AssertionError((actual, expected))
    return answer


if __name__ == "__main__":
    print(json.dumps(answers(), indent=2, sort_keys=True))
