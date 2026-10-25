"""Seeded independent oracles for reference, policy, sink, and cache semantics.

Oracles use plain dictionaries and exhaustive integer-time scans. They never
call the implementation's reference, publication builder, or snapshot methods.
Counts report comparisons actually executed, not a requested target count.
"""

from collections import Counter
from dataclasses import asdict
import random

from parity_lab import (CacheTimeline, FeatureKey, SourceHistory, SourceRevision,
                        StoreTimeline, build_publications, canonical_json)

SEED = 20261003
CASES = 128

# Expected metadata is a declared acceptance contract, never copied from output.
DECLARED_CONTRACTS = {
    "policy_contract_version": "policy-v1",
    "source_schema_version": "source-v1",
    "publication_schema_version": "publication-v1",
    "serving_log_schema_version": "serving-log-v1",
    "preprocessing_id": "identity-v1",
}
KEY_FIELDS = ("feature_definition_id", "policy_id", "entity", "window_start", "window_end")


def oracle_reference(rows: list[dict], key: FeatureKey, cutoff: int) -> tuple:
    chosen = []
    for event_id in sorted({row["source_event_id"] for row in rows}):
        eligible = [row for row in rows if row["source_event_id"] == event_id
                    and row["available_at"] <= cutoff]
        if eligible:
            winner = max(eligible, key=lambda row: row["revision"])
            if winner["entity"] == key.entity and key.window_start <= winner["event_time"] < key.window_end:
                chosen.append(winner)
    return (sum(row["amount"] for row in chosen),
            tuple((row["source_event_id"], row["revision"]) for row in chosen))


def oracle_publications(rows: list[dict], key: FeatureKey, initial: int, deadline: int,
                        contracts: dict | None = None) -> list[dict]:
    """Enumerate expected states/times from raw source and declared inputs only."""
    declared = DECLARED_CONTRACTS if contracts is None else contracts
    output = []
    for minute in range(initial, deadline + 1):
        value, versions = oracle_reference(rows, key, minute)
        if not output or versions != output[-1]["source_versions"]:
            output.append({"key": {name: getattr(key, name) for name in KEY_FIELDS},
                           "contracts": dict(declared),
                           "revision": len(output) + 1, "published_at": minute,
                           "source_cutoff": minute, "value": value, "source_versions": versions})
    return output


def oracle_store(publications: list[dict], deliveries: list[tuple[int, int]], minute: int) -> dict | None:
    eligible = [revision for visible_at, revision in deliveries if visible_at <= minute]
    if not eligible:
        return None
    revision = max(eligible)
    return next(row for row in publications if row["revision"] == revision)


def signature(record) -> dict | None:
    """A complete explicit publication view, including identity and clock."""
    return None if record is None else {
        "key": {name: getattr(record.key, name) for name in KEY_FIELDS},
        "contracts": {name: getattr(record.contracts, name) for name in DECLARED_CONTRACTS},
        "published_at": record.published_at, "source_cutoff": record.source_cutoff,
        "revision": record.revision, "value": record.value,
        "source_versions": record.source_versions,
    }


def oracle_signature(record: dict | None) -> dict | None:
    return record


def assert_fields(actual, expected, context: str) -> None:
    """Typed, field-specific diagnostics; a case identifies the failed promise."""
    if type(actual) is not type(expected):
        raise AssertionError(f"{context}: expected {expected!r}, observed {actual!r} (type differs)")
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            raise AssertionError(f"{context}.fields: expected {tuple(expected)}, observed {tuple(actual)}")
        for name, value in expected.items():
            assert_fields(actual[name], value, f"{context}.{name}")
    elif actual != expected:
        raise AssertionError(f"{context}: expected {expected!r}, observed {actual!r}")


def assert_publications(actual, expected, context: str) -> None:
    assert_fields(len(actual), len(expected), context + ".length")
    for index, (record, reference) in enumerate(zip(actual, expected)):
        assert_fields(signature(record), oracle_signature(reference), f"{context}[{index}]")


def delivery_times(publications: list[dict], plan: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Apply exogenous delays to the supplied timeline, without inspecting a sink."""
    times = {row["revision"]: row["published_at"] for row in publications}
    return [(times[revision] + delay, revision) for revision, delay in plan]


def assert_snapshot(actual, expected, captured_at, context: str) -> None:
    assert_fields(signature(actual.record), oracle_signature(expected), context + ".record")
    assert_fields(actual.known, True, context + ".known")
    assert_fields(actual.captured_at, captured_at, context + ".captured_at")


def run_checks(*, cases: int = CASES, seed: int = SEED) -> dict:
    rng = random.Random(seed)
    counts: Counter[str] = Counter()
    for case in range(cases):
        key = FeatureKey("oracle-fixed-window-v1", "immediate_then_correct", "C1", 100, 160)
        revisions = []
        for event in range(8):
            event_time = rng.choice([99, 100, 101, 159, 160, 161, rng.randrange(90, 171)])
            entity = rng.choice(["C1", "C1", "C1", "OTHER"])
            for revision in range(1, rng.randrange(2, 5)):
                revisions.append(SourceRevision(f"event-{event}", revision, entity, event_time,
                                                max(event_time, rng.randrange(140, 181)), rng.randrange(0, 51)))
        # Idempotent source retries and out-of-order input are both intentional.
        deliveries = revisions + rng.sample(revisions, k=min(4, len(revisions)))
        rng.shuffle(deliveries)
        history = SourceHistory(deliveries)
        plain_rows = [asdict(row) for row in revisions]
        query_times = sorted({99, 100, 159, 160, 169, 170, 171, 200,
                              *(row.available_at + offset for row in revisions for offset in (-1, 0, 1))})
        for cutoff in query_times:
            expected = oracle_reference(plain_rows, key, cutoff)
            actual = history.reference(key, cutoff)
            assert (actual.value, actual.source_versions) == expected, (case, cutoff, "reference")
            counts["reference_comparisons"] += 1
        expected_publications = oracle_publications(plain_rows, key, 160, 170)
        publications = build_publications(history, key, initial_at=160, deadline=170)
        assert_publications(publications, expected_publications, f"case={case} publication_sequence")
        counts["publication_sequence_comparisons"] += 1
        for _ in range(3):
            rng.shuffle(deliveries)
            reordered = build_publications(SourceHistory(deliveries), key, initial_at=160, deadline=170)
            assert reordered == publications, (case, "source reorder")
            counts["reordered_source_comparisons"] += 1
        # Draw delays from the expected population, independently of actual clocks.
        plan = [(row["revision"], rng.randrange(0, 13)) for row in expected_publications]
        plan += [(revision, delay + rng.randrange(0, 8)) for revision, delay in plan[:2]]
        rng.shuffle(plan)
        expected_deliveries = delivery_times(expected_publications, plan)
        actual_deliveries = delivery_times([signature(row) for row in publications], plan)
        store = StoreTimeline.from_deliveries(publications, actual_deliveries)
        refreshes = sorted({159, 161, 169, 178, *(rng.randrange(159, 186) for _ in range(6))})
        cache = CacheTimeline.from_refreshes(store, refreshes)
        request_times = sorted({158, 159, 160, 170, 200,
                                *(at + offset for at, _ in expected_deliveries for offset in (-1, 0, 1)),
                                *(at + offset for at in refreshes for offset in (-1, 0, 1))})
        for minute in request_times:
            expected_store = oracle_store(expected_publications, expected_deliveries, minute)
            assert_snapshot(store.at(minute), expected_store, None, f"case={case} minute={minute} store")
            counts["store_snapshot_comparisons"] += 1
            prior_refreshes = [at for at in refreshes if at <= minute]
            capture_at = max(prior_refreshes) if prior_refreshes else None
            expected_cache = None if capture_at is None else oracle_store(expected_publications, expected_deliveries, capture_at)
            actual_cache = cache.at(minute)
            assert_snapshot(actual_cache, expected_cache, capture_at, f"case={case} minute={minute} cache")
            counts["cache_snapshot_comparisons"] += 1
        for left, right in zip(store.accepted, store.accepted[1:]):
            assert left[1].revision < right[1].revision, (case, "sink regression")
            counts["sink_monotonic_transitions_checked"] += 1
        counts["generated_cases"] += 1
    return {"seed": seed, "counts": dict(sorted(counts.items())), "status": "passed"}


if __name__ == "__main__":
    print(canonical_json(run_checks()), end="")
