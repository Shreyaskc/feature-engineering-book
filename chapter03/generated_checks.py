"""Seeded independent SQLite/reference agreement over generated valid histories."""
from dataclasses import replace
import json
import random

from foundations_lab import Delivery, Ledger, Revision, spend_in_window
from historical_lab import Query, reference_selection, reference_value, sqlite_value
from sqlite_lab import contributors, selected


def run_checks(seed: int = 20261005, histories: int = 200, per_history: int = 20) -> dict:
    rng = random.Random(seed)
    query_count = 0
    unknown_count = 0
    tombstones = 0
    equal_availability = 0
    restorations = 0
    for case in range(histories):
        deliveries = []
        for event in range(rng.randint(0, 14)):
            customer, event_time = rng.choice(("C1", "C2")), rng.randint(0, 700)
            available, revision, old_op = event_time, 0, "upsert"
            for version in range(rng.randint(1, 5)):
                old_available = available
                available += rng.randint(0, 35)
                revision += rng.randint(1, 3)
                op = rng.choice(("upsert", "upsert", "upsert", "delete"))
                amount = None if op == "delete" else rng.randint(0, 100)
                row = Revision(f"event-{case}-{event}", revision, customer,
                               event_time, available, amount, op)
                delivery = Delivery(f"d-{event}-{version}", row,
                                    available + rng.randint(0, 50))
                deliveries.append(delivery)
                if rng.random() < 0.5:
                    deliveries.append(delivery)
                if rng.random() < 0.4:
                    deliveries.append(Delivery(f"retry-{event}-{version}", row,
                                               available + rng.randint(50, 100)))
                tombstones += op == "delete"
                equal_availability += version > 0 and available == old_available
                restorations += old_op == "delete" and op == "upsert"
                old_op = op
        rng.shuffle(deliveries)
        canonical = Ledger(tuple(deliveries), allow_restore=True)
        replay = Ledger(tuple(reversed(deliveries)) + canonical.deliveries,
                        allow_restore=True)
        if canonical != replay:
            raise AssertionError("replay changed canonical input")
        for _ in range(per_history):
            end = rng.randint(1, 950)
            start = rng.randint(0, end - 1)
            known_at = rng.randint(end, 1050)
            known = rng.random() > 0.2
            query = Query(rng.choice(("C1", "C2", "C9")), start, end, known_at, known)
            reference = reference_value(canonical, query)
            sql = sqlite_value(replay, query)
            old_reference = spend_in_window(canonical.history, query.customer_id,
                                           window_start=start, window_end=end,
                                           known_at=known_at, history_known=known)
            if reference != sql or reference != old_reference:
                raise AssertionError((case, query, reference, sql, old_reference))
            reference_rows = [(r.event_id, r.revision, r.amount, r.op)
                              for r in reference_selection(canonical, query)]
            if selected(replay, query) != reference_rows:
                raise AssertionError("selected identities differ despite possible equal sums")
            reference_contributors = [(r.event_id, r.revision, r.amount, r.op)
                                      for r in reference_selection(canonical, query)
                                      if r.customer_id == query.customer_id
                                      and start <= r.event_time < end
                                      and r.op == "upsert"]
            if contributors(replay, query) != reference_contributors:
                raise AssertionError("contributing identities differ despite possible equal sums")
            # Adding ineligible future evidence cannot change a past decision.
            truncated = Ledger(tuple(d for d in canonical.deliveries
                                     if d.record.available_at <= known_at),
                               allow_restore=True)
            if reference_value(truncated, query) != reference:
                raise AssertionError("future evidence changed a historical answer")
            query_count += 1
            unknown_count += not known
    return {"seed": seed, "histories": histories, "queries": query_count,
            "reference_sqlite_value_agreements": query_count,
            "selected_identity_agreements": query_count,
            "contributor_identity_agreements": query_count,
            "foundation_reference_agreements": query_count,
            "future_evidence_isolation_checks": query_count,
            "replay_invariance_checks": histories, "unknown_history_queries": unknown_count,
            "generated_tombstones": tombstones, "equal_availability_pairs": equal_availability,
            "generated_restorations": restorations, "status": "passed"}


if __name__ == "__main__":
    print(json.dumps(run_checks(), indent=2, sort_keys=True))
