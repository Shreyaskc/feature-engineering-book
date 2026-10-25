"""Seeded, independent property checks for the synthetic foundations lab.

This is a finite set of generated examples, not a proof or a production
deployment test. It uses only Python's standard library and local memory.
The reference normalizer detects conflicts pairwise before grouping rows;
the query oracle groups events and takes an explicit maximum revision.
Neither oracle calls the implementation's normalization or query helpers.

Run ``python randomized_checks.py`` for a deterministic JSON report, or
import ``run_checks(seed=..., cases=...)`` from the verification script.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
from itertools import combinations, groupby
import json
import random

from foundations_lab import (
    ContractError, Delivery, Ledger, Revision, ingest, selected_revisions,
    spend, spend_in_window,
)


DEFAULT_SEED = 20261003
DEFAULT_CASES = 160


class ReferenceConflict(ValueError):
    """A reference-contract violation, independent of ContractError."""

    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


def _require(condition: bool, context: str) -> None:
    # Keep verification active even when Python runs with -O.
    if not condition:
        raise AssertionError(context)


def _source_key(row: Revision) -> tuple[str, int]:
    return row.event_id, row.revision


def _reference_normalize(
    deliveries: tuple[Delivery, ...], *, allow_restore: bool,
) -> tuple[tuple[Delivery, ...], tuple[Revision, ...]]:
    """Slow pairwise oracle for already well-typed generated records."""
    for left, right in combinations(deliveries, 2):
        if left.delivery_id == right.delivery_id and left != right:
            raise ReferenceConflict("delivery_id_conflict")
        if (_source_key(left.record) == _source_key(right.record)
                and left.record != right.record):
            raise ReferenceConflict("source_version_conflict")

    # Equal items in a group are established by the pairwise pass above.
    retained = tuple(next(group) for _, group in groupby(
        sorted(deliveries, key=lambda item: item.delivery_id),
        key=lambda item: item.delivery_id))
    history = tuple(next(group) for _, group in groupby(
        sorted((item.record for item in deliveries), key=_source_key),
        key=_source_key))
    for earlier, later in combinations(history, 2):
        if earlier.event_id != later.event_id:
            continue
        if earlier.customer_id != later.customer_id:
            raise ReferenceConflict("entity_change")
        if earlier.event_time != later.event_time:
            raise ReferenceConflict("event_time_change")
        if earlier.available_at > later.available_at:
            raise ReferenceConflict("availability_regression")
        if (not allow_restore and earlier.op == "delete"
                and later.op == "upsert"):
            raise ReferenceConflict("restore_without_permission")
    return retained, history


def _event_groups(history: tuple[Revision, ...]):
    return groupby(sorted(history, key=lambda row: row.event_id),
                   key=lambda row: row.event_id)


def _reference_selection(history: tuple[Revision, ...],
                         known_at: int) -> tuple[Revision, ...]:
    answer = []
    for _, group in _event_groups(history):
        eligible = [row for row in group if row.available_at <= known_at]
        if eligible:
            answer.append(max(eligible, key=lambda row: row.revision))
    return tuple(answer)


def _reference_spend(history: tuple[Revision, ...], customer_id: str, *,
                     window_start: int, window_end: int, known_at: int,
                     history_known: bool) -> int | None:
    # Empty and unknown are different states, including for partial history.
    if not history_known:
        return None
    amounts = []
    for _, group in _event_groups(history):
        eligible = [row for row in group if row.available_at <= known_at]
        if not eligible:
            continue
        chosen = max(eligible, key=lambda row: row.revision)
        if (chosen.op == "upsert" and chosen.customer_id == customer_id
                and window_start <= chosen.event_time < window_end):
            amounts.append(chosen.amount)
    return sum(amounts)


def _generate_case(rng: random.Random, number: int
                   ) -> tuple[tuple[Delivery, ...], bool]:
    allow_restore = number % 3 == 0
    if number % 13 == 0:
        return (), allow_restore
    deliveries = []
    for event in range(rng.randint(1, 6)):
        event_id = f"case-{number:03d}-event-{event}"
        customer = f"customer-{rng.randrange(3)}"
        event_time = rng.randrange(181)
        available = event_time + rng.randint(1, 25)
        revision = rng.randint(1, 3)
        versions = rng.randint(1, 6)
        if event == 0:
            versions = max(versions, 3)
        deleted = False
        for position in range(versions):
            if position:
                revision += (2 if position == 1 and event == 0
                             else rng.randint(1, 3))
                available += (0 if position == 1 and event == 0
                              else rng.choice((0, 0, 1, 3, 8, 19)))
            if event == 0 and allow_restore:
                # Every nonempty restore-enabled case includes a tombstone
                # followed by a higher upsert; some share availability time.
                op = "delete" if position % 3 == 1 else "upsert"
            elif deleted:
                op = "delete"
            elif position and (rng.randrange(4) == 0
                               or (event == 0 and position == versions - 1)):
                op = "delete"
            else:
                op = "upsert"
            deleted = op == "delete"
            amount = None if deleted else rng.choice((0, 1, 7, 35, rng.randrange(501)))
            row = Revision(event_id, revision, customer, event_time,
                           available, amount, op)
            attempts = 2 if event == 0 and position == 0 else rng.randint(1, 3)
            for attempt in range(attempts):
                item = Delivery(f"{event_id}-r{revision}-d{attempt}", row,
                                available + rng.randrange(61))
                deliveries.append(item)
                if attempt == 0 and (position == 0 or rng.randrange(3) == 0):
                    deliveries.append(item)  # Exact transport replay.
    rng.shuffle(deliveries)
    return tuple(deliveries), allow_restore


def _cutoffs(history: tuple[Revision, ...]) -> tuple[int, ...]:
    availability = sorted({row.available_at for row in history})
    if not availability:
        return 0, 1, 60, 120
    anchors = {availability[0], availability[len(availability) // 2],
               availability[-1]}
    # Include equal-time revision ties and a known delete/restore boundary.
    for _, group in _event_groups(history):
        rows = list(group)
        for earlier, later in zip(rows, rows[1:]):
            if (earlier.available_at == later.available_at
                    or earlier.op != later.op):
                anchors.add(later.available_at)
                break
    return tuple(sorted({0, 1, availability[-1] + 60} | {
        value + delta for value in anchors for delta in (-1, 0, 1)
        if value + delta >= 0}))


def _windows(history: tuple[Revision, ...], known_at: int
              ) -> tuple[tuple[int, int], ...]:
    if known_at == 0:
        return ()
    candidates = {(max(0, known_at - 60), known_at), (0, known_at),
                  (0, max(1, known_at // 2))}
    for event_time in sorted({row.event_time for row in history})[:3]:
        if event_time < known_at:
            candidates.add((event_time, event_time + 1))
        if 0 < event_time <= known_at:
            candidates.add((event_time - 1, event_time))
    return tuple(sorted(candidates))


def _case_coverage(deliveries: tuple[Delivery, ...],
                   retained: tuple[Delivery, ...],
                   history: tuple[Revision, ...]) -> dict[str, bool]:
    pairs = [(left, right) for left, right in combinations(history, 2)
             if left.event_id == right.event_id]
    adjacent_pairs = []
    for _, group in _event_groups(history):
        rows = list(group)
        adjacent_pairs.extend(zip(rows, rows[1:]))
    return {
        "empty_histories": not history,
        "revision_gaps": any(right.revision - left.revision > 1
                             for left, right in adjacent_pairs),
        "equal_availability_revisions": any(
            left.available_at == right.available_at for left, right in pairs),
        "exact_delivery_replays": len(deliveries) > len(retained),
        "distinct_delivery_retries": len(retained) > len(history),
        "out_of_order_input": any(
            left.delivered_at > right.delivered_at
            for left, right in zip(deliveries, deliveries[1:])),
        "arrival_order_differs_from_revision_order": any(
            left.record.event_id == right.record.event_id
            and left.record.revision < right.record.revision
            and left.delivered_at > right.delivered_at
            for left, right in combinations(sorted(
                retained, key=lambda item: _source_key(item.record)), 2)),
        "deletions": any(row.op == "delete" for row in history),
        "restorations": any(left.op == "delete" and right.op == "upsert"
                            for left, right in pairs),
        "zero_amount_upserts": any(row.op == "upsert" and row.amount == 0
                                   for row in history),
    }


def _corruptions(ledger: Ledger, number: int):
    if not ledger.history:
        return
    prefix = f"corrupt-{number}"
    item = ledger.deliveries[0]
    yield "delivery_id_conflict", (replace(item, delivered_at=item.delivered_at + 1),)
    source = next(row for row in ledger.history if row.op == "upsert")
    yield "source_version_conflict", (Delivery(
        prefix + "-source", replace(source, amount=source.amount + 1),
        source.available_at),)
    event_rows = [row for row in ledger.history if row.event_id == source.event_id]
    last = max(event_rows, key=lambda row: row.revision)
    new = replace(last, revision=last.revision + 2)
    customer = replace(new, customer_id=last.customer_id + "-changed")
    yield "entity_change", (Delivery(prefix + "-entity", customer, customer.available_at),)
    event_time = replace(new, event_time=last.event_time + 1,
                         available_at=max(last.available_at, last.event_time + 1))
    yield "event_time_change", (Delivery(prefix + "-time", event_time,
                                         event_time.available_at),)
    earlier = replace(new, available_at=last.available_at - 1)
    yield "availability_regression", (Delivery(prefix + "-availability", earlier,
                                                last.available_at),)
    if not ledger.allow_restore:
        tombstone = Revision(prefix + "-restore", 2, "customer-0", 10,
                             11, None, "delete")
        restored = replace(tombstone, revision=5, available_at=12,
                           op="upsert", amount=3)
        yield "restore_without_permission", (
            Delivery(prefix + "-delete", tombstone, 20),
            Delivery(prefix + "-restore", restored, 20))


def run_checks(seed: int = DEFAULT_SEED, cases: int = DEFAULT_CASES) -> dict:
    """Run generated checks and return reproducible, JSON-compatible counts.

    Counts are recomputed from successful comparison audit entries and
    independent reference histories, never from production summary fields.
    Invalid CLI configuration or the first mismatch raises immediately.
    """
    if type(seed) is not int or type(cases) is not int or cases < 1:
        raise ValueError("seed must be an integer and cases must be a positive integer")
    rng = random.Random(seed)
    audit: list[str] = []
    rejected: list[str] = []
    case_records = []
    input_digest = hashlib.sha256()

    def compare(actual, expected, category: str, context: str) -> None:
        _require(actual == expected, f"{context}: {category}: {actual!r} != {expected!r}")
        audit.append(category)

    for number in range(cases):
        raw, allow_restore = _generate_case(rng, number)
        expected_deliveries, expected_history = _reference_normalize(
            raw, allow_restore=allow_restore)
        context = f"seed={seed}, case={number}"
        input_digest.update(json.dumps({
            "allow_restore": allow_restore,
            "deliveries": [asdict(item) for item in raw],
        }, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        ledger = Ledger(raw, allow_restore=allow_restore)

        def check_ledger(candidate: Ledger, candidate_raw: tuple[Delivery, ...],
                         label: str) -> None:
            expected = _reference_normalize(candidate_raw, allow_restore=allow_restore)
            compare(candidate.deliveries, expected[0], "delivery_ledger_comparisons",
                    context + "/" + label)
            compare(candidate.history, expected[1], "canonical_history_comparisons",
                    context + "/" + label)

        check_ledger(ledger, raw, "base")
        shuffled = list(raw)
        rng.shuffle(shuffled)
        variants = (tuple(reversed(raw)), tuple(shuffled),
                    tuple(sorted(raw, key=lambda item: item.delivered_at)))
        for position, variant in enumerate(variants):
            other = Ledger(variant, allow_restore=allow_restore)
            check_ledger(other, variant, f"permutation-{position}")
            compare(other, ledger, "input_order_invariance", context)

        replayed_raw = raw + raw[::2] + raw
        replayed = Ledger(replayed_raw, allow_restore=allow_restore)
        check_ledger(replayed, replayed_raw, "exact-replay")
        compare(replayed, ledger, "exact_retry_invariance", context)
        new_retries = tuple(Delivery(
            f"case-{number}-extra-retry-{index}", row, row.available_at + 1000)
            for index, row in enumerate(expected_history[::2]))
        retried_raw = raw + new_retries
        retried = Ledger(retried_raw, allow_restore=allow_restore)
        check_ledger(retried, retried_raw, "new-delivery-identities")
        compare(retried.history, ledger.history, "distinct_retry_history_invariance", context)
        compare(len(retried.deliveries), len(expected_deliveries) + len(new_retries),
                "distinct_retry_retention", context)

        for order, chunk_sizes in ((raw, (1, 2, 5, 3)), (tuple(shuffled), (7, 1, 4))):
            chunked = Ledger(allow_restore=allow_restore)
            offset = step = 0
            while offset < len(order):
                size = chunk_sizes[step % len(chunk_sizes)]
                before = (chunked.deliveries, chunked.history)
                previous = chunked
                chunked = ingest(chunked, order[offset:offset + size])
                compare((previous.deliveries, previous.history), before,
                        "accepted_ingest_snapshot_preservation", context)
                offset += size
                step += 1
            check_ledger(chunked, order, "chunked")
            compare(chunked, ledger, "batch_chunking_invariance", context)

        cutoffs = _cutoffs(expected_history)
        customers = sorted({row.customer_id for row in expected_history}
                           | {"customer-absent"})
        unordered_history = list(expected_history)
        rng.shuffle(unordered_history)
        for known_at in cutoffs:
            selected = _reference_selection(expected_history, known_at)
            compare(selected_revisions(ledger.history, known_at=known_at), selected,
                    "selection_reference_comparisons", context)
            compare(selected_revisions(unordered_history, known_at=known_at), selected,
                    "history_order_invariance", context)
            compare(selected_revisions(retried.history, known_at=known_at), selected,
                    "retry_selection_invariance", context)
            for start, end in _windows(expected_history, known_at):
                for customer in customers:
                    for history_known in (True, False):
                        arguments = dict(window_start=start, window_end=end,
                                         known_at=known_at, history_known=history_known)
                        expected = _reference_spend(expected_history, customer, **arguments)
                        compare(spend_in_window(ledger.history, customer, **arguments), expected,
                                ("known_history_window_comparisons" if history_known
                                 else "unknown_history_window_comparisons"), context)
            if known_at:
                width = min(60, known_at)
                for customer in customers:
                    for history_known in (True, False):
                        expected = _reference_spend(
                            expected_history, customer, window_start=known_at - width,
                            window_end=known_at, known_at=known_at,
                            history_known=history_known)
                        # .history is deliberately passed without a restore policy.
                        compare(spend(ledger.history, customer, known_at,
                                      window_minutes=width, history_known=history_known),
                                expected, "rolling_window_reference_comparisons", context)
                        compare(spend(retried.history, customer, known_at,
                                      window_minutes=width, history_known=history_known),
                                expected, "retry_spend_invariance", context)

        for category, bad_batch in _corruptions(ledger, number):
            extra = Delivery(f"case-{number}-atomicity-probe", Revision(
                f"case-{number}-atomicity-event", 1, "customer-0", 0, 0, 1), 0)
            batch = (extra,) + bad_batch
            try:
                _reference_normalize(ledger.deliveries + batch, allow_restore=allow_restore)
            except ReferenceConflict as error:
                _require(error.category == category,
                         f"{context}: corruption was not isolated: {category}: {error}")
            else:
                raise AssertionError(f"{context}: reference accepted {category}")
            snapshot = (ledger.deliveries, ledger.history)
            try:
                ingest(ledger, batch)
            except ContractError:
                rejected.append(category)
            else:
                raise AssertionError(f"{context}: implementation accepted {category}")
            compare((ledger.deliveries, ledger.history), snapshot,
                    "rejected_ingest_snapshot_preservation", context)

        case_records.append({
            "coverage": _case_coverage(raw, expected_deliveries, expected_history),
            "input_count": len(raw), "delivery_count": len(expected_deliveries),
            "source_count": len(expected_history), "cutoffs": cutoffs,
            "source_fingerprint": tuple(expected_history),
        })

    # These two explicit checks remain present even if a custom seed/case
    # budget happens not to generate a nonempty history.
    compare(spend_in_window((), "customer-0", window_start=0, window_end=1,
                            known_at=1, history_known=True), 0,
            "explicit_known_empty_check", "empty history")
    compare(spend_in_window((), "customer-0", window_start=0, window_end=1,
                            known_at=1, history_known=False), None,
            "explicit_unknown_empty_check", "empty history")

    coverage = Counter(name for case in case_records
                       for name, present in case["coverage"].items() if present)
    coverage_names = case_records[0]["coverage"]
    input_total = sum(case["input_count"] for case in case_records)
    delivery_total = sum(case["delivery_count"] for case in case_records)
    source_total = sum(case["source_count"] for case in case_records)
    return {
        "status": "passed", "seed": seed, "generated_cases": len(case_records),
        "generated_input_sha256": input_digest.hexdigest(),
        "scope": "Finite synthetic standard-library checks; not a proof or production deployment test.",
        "coverage_cases": {name: coverage[name] for name in sorted(coverage_names)},
        "generated_data": {
            "input_delivery_observations": input_total,
            "canonical_deliveries": delivery_total,
            "canonical_source_versions": source_total,
            "exact_delivery_replay_observations": input_total - delivery_total,
            "distinct_retry_deliveries": delivery_total - source_total,
            "case_cutoff_pairs": sum(len(case["cutoffs"]) for case in case_records),
            "distinct_source_histories": len({case["source_fingerprint"] for case in case_records}),
        },
        "successful_comparisons": dict(sorted(Counter(audit).items())),
        "rejected_corruptions": dict(sorted(Counter(rejected).items())),
        "total_successful_comparisons": len(audit),
        "total_rejected_corruptions": len(rejected),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--cases", type=int, default=DEFAULT_CASES)
    arguments = parser.parse_args()
    print(json.dumps(run_checks(arguments.seed, arguments.cases), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
