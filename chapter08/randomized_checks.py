"""Finite, seeded checks against an independent raw-dictionary oracle.

Only the harness imports the implementation being checked. ``raw_oracle``
does not call its parser, normalizer, selector, or query helpers. It scans
each event's raw deliveries comprehensively and takes the greatest eligible
revision. Inputs to this oracle must already satisfy the fixture contract;
this file is not a second implementation of malformed-input validation.

The default 240 generated fixtures are useful, repeatable evidence, not an
exhaustive test or a proof. No timing, network, or external packages occur.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import random


DEFAULT_SEED = 20261005
DEFAULT_CASES = 240


def raw_oracle(raw_fixture: dict, *, customer_id: str, decision_at: int,
               window_minutes: int, history_known: bool = True
               ) -> int | None:
    """Compute the contract directly for valid inputs, without query code.

    Identical source versions may occur many times among the deliveries.
    Choosing once per event makes both forms of duplicate harmless without
    borrowing the implementation's delivery or source deduplication.
    """
    if not history_known:
        return None
    rows = [delivery["record"] for delivery in raw_fixture["deliveries"]]
    total = 0
    for event_id in sorted({row["event_id"] for row in rows}):
        eligible = [row for row in rows
                    if row["event_id"] == event_id
                    and row["available_at"] <= decision_at]
        if not eligible:
            continue
        chosen = max(eligible, key=lambda row: row["revision"])
        if (chosen["customer_id"] == customer_id
                and decision_at - window_minutes <= chosen["event_time"]
                < decision_at and chosen["op"] == "upsert"):
            total += chosen["amount"]
    return total


def _require(condition: bool, context: str) -> None:
    # Remain active under python -O as well as normal execution.
    if not condition:
        raise AssertionError(context)


def _equal(actual: object, expected: object, context: str) -> None:
    _require(type(actual) is type(expected) and actual == expected,
             f"{context}: expected {expected!r}, got {actual!r}")


def _record(event_id: str, revision: int, customer: str, event_time: int,
            available_at: int, amount: int | None) -> dict:
    return {"event_id": event_id, "revision": revision,
            "customer_id": customer, "event_time": event_time,
            "available_at": available_at, "amount": amount,
            "op": "delete" if amount is None else "upsert"}


def _generate_case(rng: random.Random, number: int) -> tuple[dict, dict]:
    window = rng.choice((1, 7, 30, 60, 90))
    decision = window if number % 11 == 0 else rng.randint(window, 900)
    start = decision - window
    query = {"decision_at": decision, "window_minutes": window}
    fixture = {"schema_version": 1, "allow_restore": False,
               "deliveries": []}
    if number % 17 == 0:
        return fixture, query

    rows = []
    prefix = f"case-{number:03d}"
    # Explicit anchors keep the generated distribution from silently losing
    # crucial edges. Higher revision at equal availability wins, even across
    # a revision gap; the later revision remains invisible to this query.
    rows.extend((
        _record(prefix + "-lower", 1, "C1", start, start, 3),
        _record(prefix + "-lower", 3, "C1", start, start, 17),
        _record(prefix + "-lower", 5, "C1", start, decision + 1, 29),
        _record(prefix + "-upper", 1, "C1", decision, decision, 31),
        _record(prefix + "-after", 1, "C1", decision + 1,
                decision + 1, 37),
        _record(prefix + "-cutoff", 1, "C1", decision - 1,
                decision, 41),
        _record(prefix + "-cutoff", 4, "C1", decision - 1,
                decision + 1, 43),
        _record(prefix + "-deleted", 1, "C1", start, start, 47),
        _record(prefix + "-deleted", 2, "C1", start, decision, None),
        _record(prefix + "-c2", 1, "C2", start, start, 53),
        _record(prefix + "-c3", 1, "C3", start, start, 0),
    ))
    if start > 0:
        rows.append(_record(prefix + "-before", 1, "C1", start - 1,
                            start, 59))

    for event in range(rng.randint(1, 6)):
        event_id = f"{prefix}-random-{event}"
        customer = rng.choice(("C1", "C2", "C3"))
        event_time = max(0, decision + rng.randint(-window - 8, 8))
        available_at = event_time + rng.randint(0, 30)
        revision = rng.randint(1, 3)
        deleted = False
        for position in range(rng.randint(1, 5)):
            if position:
                revision += rng.randint(1, 3)
                available_at += rng.choice((0, 0, 1, 5, 20))
                deleted = deleted or rng.randrange(5) == 0
            amount = None if deleted else rng.choice((0, 1, 7, 101,
                                                       rng.randint(0, 999)))
            rows.append(_record(event_id, revision, customer, event_time,
                                available_at, amount))

    for position, row in enumerate(rows):
        delivery = {"delivery_id": f"{prefix}-delivery-{position}",
                    "delivered_at": row["available_at"] + rng.randint(0, 90),
                    "record": row}
        fixture["deliveries"].append(delivery)
        if position == 0 or rng.randrange(4) == 0:
            fixture["deliveries"].append(deepcopy(delivery))
        if position == 0 or rng.randrange(4) == 0:
            retry = deepcopy(delivery)
            retry["delivery_id"] += "-retry"
            retry["delivered_at"] += rng.randint(1, 90)
            fixture["deliveries"].append(retry)
    rng.shuffle(fixture["deliveries"])
    return fixture, query


def _variants(fixture: dict, query: dict, rng: random.Random,
              number: int) -> dict[str, dict]:
    shuffled = deepcopy(fixture)
    rng.shuffle(shuffled["deliveries"])
    replayed = deepcopy(fixture)
    replayed["deliveries"].extend(deepcopy(fixture["deliveries"]))
    retried = deepcopy(fixture)
    for position, item in enumerate(fixture["deliveries"][:6]):
        retry = deepcopy(item)
        retry["delivery_id"] = f"metamorphic-{number}-retry-{position}"
        retry["delivered_at"] += 100
        retried["deliveries"].append(retry)

    later = deepcopy(fixture)
    rows = [item["record"] for item in fixture["deliveries"]]
    for position, event_id in enumerate(sorted({r["event_id"] for r in rows})):
        last = max((r for r in rows if r["event_id"] == event_id),
                   key=lambda r: r["revision"])
        future = deepcopy(last)
        future["revision"] += 1
        future["available_at"] = max(last["available_at"],
                                      query["decision_at"]) + 1
        # Preserve an existing tombstone: this lab never enables restoration.
        if future["op"] == "upsert":
            future["amount"] += 67
        later["deliveries"].append({
            "delivery_id": f"metamorphic-{number}-future-{position}",
            "delivered_at": future["available_at"], "record": future})
    late_new = _record(f"metamorphic-{number}-new", 1, "C1",
                       query["decision_at"] - 1,
                       query["decision_at"] + 1, 71)
    later["deliveries"].append({
        "delivery_id": f"metamorphic-{number}-new-delivery",
        "delivered_at": late_new["available_at"], "record": late_new})
    return {"shuffle": shuffled, "exact_delivery_replay": replayed,
            "distinct_delivery_retry": retried, "later_information": later}


def _coverage(fixture: dict, query: dict) -> dict[str, bool]:
    deliveries = fixture["deliveries"]
    rows = [item["record"] for item in deliveries]
    ids = {item["delivery_id"] for item in deliveries}
    source_keys = {(row["event_id"], row["revision"]) for row in rows}
    distinct = {key: next(row for row in rows
                         if (row["event_id"], row["revision"]) == key)
                for key in source_keys}
    pairs = [(left, right) for left in distinct.values()
             for right in distinct.values()
             if left["event_id"] == right["event_id"]
             and left["revision"] < right["revision"]]
    decision = query["decision_at"]
    start = decision - query["window_minutes"]
    return {
        "empty_histories": not rows,
        "multiple_customers": len({r["customer_id"] for r in rows}) > 1,
        "lower_boundary": any(r["event_time"] == start for r in rows),
        "upper_boundary": any(r["event_time"] == decision for r in rows),
        "availability_at_decision": any(r["available_at"] == decision
                                        for r in rows),
        "availability_after_decision": any(r["available_at"] > decision
                                           for r in rows),
        "equal_availability_revisions": any(
            a["available_at"] == b["available_at"] for a, b in pairs),
        "different_availability_revisions": any(
            a["available_at"] < b["available_at"] for a, b in pairs),
        "revision_gaps": any(b["revision"] - a["revision"] > 1
                             for a, b in pairs),
        "deletions": any(r["op"] == "delete" for r in rows),
        "zero_amount_upserts": any(r["amount"] == 0 for r in rows),
        "exact_delivery_replays": len(deliveries) > len(ids),
        "distinct_delivery_retries": len(ids) > len(source_keys),
        "clock_origin_window": start == 0,
    }


def run_checks(seed: int = DEFAULT_SEED, cases: int = DEFAULT_CASES) -> dict:
    """Compare valid generated inputs and valid metamorphic transformations.

    The tested public API validates every fixture. A transformed case must
    still parse successfully, then match the original independent answer.
    Later-information invariance means an unchanged historical query with
    only strictly post-decision source availability appended. It does not
    apply to changing the decision, coverage assertion, or old payloads.
    """
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(cases) is not int or cases < 1:
        raise ValueError("cases must be a positive integer")
    # This import belongs to the comparison harness, never the oracle.
    from fault_testing_lab import Query, evaluate

    rng = random.Random(seed)
    coverage: Counter[str] = Counter()
    transformations: Counter[str] = Counter()
    query_checks = 0
    digest = hashlib.sha256()
    for number in range(cases):
        fixture, time_query = _generate_case(rng, number)
        original = deepcopy(fixture)
        variants = _variants(fixture, time_query, rng, number)
        for name, present in _coverage(fixture, time_query).items():
            coverage[name] += int(present)
        for customer in ("C1", "C2", "C3", "absent-customer"):
            for known in (True, False):
                arguments = {**time_query, "customer_id": customer,
                             "history_known": known}
                query = Query(**arguments)
                expected = raw_oracle(fixture, **arguments)
                context = f"case {number}, {arguments}"
                _equal(evaluate(fixture, query=query), expected, context)
                query_checks += 1
                coverage["known_history_queries" if known
                         else "unknown_history_queries"] += 1
                digest.update(json.dumps({"fixture": fixture,
                                          "query": arguments,
                                          "expected": expected},
                                         sort_keys=True,
                                         separators=(",", ":")).encode())
                for name, changed in variants.items():
                    _equal(raw_oracle(changed, **arguments), expected,
                           f"oracle {name}, {context}")
                    _equal(evaluate(changed, query=query), expected,
                           f"reference {name}, {context}")
                    transformations[name] += 1
        _require(fixture == original, f"case {number}: input was mutated")

    if cases >= 18:
        _require(all(count > 0 for count in coverage.values()),
                 "generated distribution lost a required coverage category")
    return {
        "seed": seed,
        "generated_cases": cases,
        "original_query_comparisons": query_checks,
        "metamorphic_comparisons": dict(sorted(transformations.items())),
        "reference_oracle_comparisons": query_checks + sum(transformations.values()),
        "coverage": dict(sorted(coverage.items())),
        "corpus_sha256": digest.hexdigest(),
        "status": "passed",
        "scope": "Finite generated evidence; not exhaustive or a proof.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--cases", type=int, default=DEFAULT_CASES)
    arguments = parser.parse_args()
    print(json.dumps(run_checks(arguments.seed, arguments.cases),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
