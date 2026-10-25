"""Seeded finite checks with independent raw-input historical/policy oracles.

The oracles use only Python dictionaries and the declared 60-minute contract.
They never call the lab's parser, selector, window, or publication functions.
Valid-input generation and malformed-input regression tests are separate.
These checks give repeatable evidence, not an exhaustive proof or ML claim.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
import random


DEFAULT_SEED = 20261005
DEFAULT_CASES = 160


def _selected(raw: dict, cutoff: int) -> list[dict]:
    """Scan every raw delivery per event; retry arrival time is irrelevant."""
    rows = [delivery["record"] for delivery in raw["deliveries"]]
    selected = []
    for event in sorted({row["event_id"] for row in rows}):
        eligible = [row for row in rows if row["event_id"] == event
                    and row["available_at"] <= cutoff]
        if eligible:
            selected.append(max(eligible, key=lambda row: row["revision"]))
    return selected


def historical_oracle(raw: dict, decision: dict, *, cutoff: int | None = None) -> dict:
    """A complete row, with a hardcoded half-open 60-minute rolling window."""
    at = decision["decision_at"]
    cutoff = at if cutoff is None else cutoff
    chosen = [row for row in _selected(raw, cutoff)
              if decision["history_known"] and row["op"] == "upsert"
              and row["customer_id"] == decision["customer_id"]
              and at - 60 <= row["event_time"] < at]
    return {**decision, "window_start": at - 60, "window_end": at,
            "source_cutoff": cutoff,
            "value": sum(row["amount"] for row in chosen)
            if decision["history_known"] else None,
            "missing": not decision["history_known"],
            "source_versions": [[row["event_id"], row["revision"]]
                                for row in chosen],
            "definition_id": "known_spend_60m_v1"}


def publication_oracle(raw: dict) -> list[dict]:
    """Recompute each minute 600..610, inclusive, from raw source evidence.

    This deliberately scans all eleven minutes rather than borrowing the
    implementation's event-time schedule. Provenance changes publish even
    when the value is unchanged. Evidence arriving at 611 cannot reopen it.
    """
    result = []
    for minute in range(600, 611):
        included = [row for row in _selected(raw, minute)
                    if row["op"] == "upsert" and row["customer_id"] == "C1"
                    and 540 <= row["event_time"] < 600]
        versions = [[row["event_id"], row["revision"]] for row in included]
        if not result or versions != result[-1]["source_versions"]:
            result.append({"revision": len(result) + 1,
                           "published_at": minute, "source_cutoff": minute,
                           "value": sum(row["amount"] for row in included),
                           "source_versions": versions})
    return result


def _equal(actual: object, expected: object, context: str) -> None:
    # Keep checks active under python -O; a crash is never a passing check.
    if type(actual) is not type(expected) or actual != expected:
        raise AssertionError(f"{context}: expected {expected!r}, got {actual!r}")


def _record(event: str, revision: int, customer: str, time: int,
            available: int, amount: int) -> dict:
    return {"event_id": event, "revision": revision, "customer_id": customer,
            "event_time": time, "available_at": available, "amount": amount,
            "op": "upsert"}


def _fixture(rng: random.Random, number: int) -> dict:
    raw = {"schema_version": 1, "allow_restore": False, "deliveries": []}
    if number % 17 == 0:
        return raw
    # Anchors guarantee edge coverage; random rows add a broader distribution.
    rows = [
        _record("lower", 1, "C1", 540, 540, 3),
        _record("lower", 3, "C1", 540, 600, 5),
        _record("lower", 7, "C1", 540, 600, 7),
        _record("lower", 8, "C1", 540, 611, 91),
        _record("before", 1, "C1", 539, 550, 11),
        _record("upper", 1, "C1", 600, 600, 13),
        _record("deadline", 1, "C1", 590, 610, 17),
        _record("after-deadline", 1, "C1", 599, 611, 19),
        _record("unchanged", 1, "C1", 580, 581, 23),
        _record("unchanged", 2, "C1", 580, 605, 23),
        _record("other-customer", 1, "C2", 575, 576, 29),
        _record("zero", 1, "C3", 575, 576, 0),
    ]
    for event in range(rng.randint(1, 7)):
        time = rng.randint(520, 619)
        available = time + rng.randint(0, 30)
        revision = rng.randint(1, 3)
        customer = rng.choice(("C1", "C2", "C3"))
        for position in range(rng.randint(1, 5)):
            if position:
                revision += rng.randint(1, 4)
                available += rng.choice((0, 1, 3, 10, 25))
            rows.append(_record(f"random-{event}", revision, customer, time,
                                available, rng.choice((0, 1, 7, rng.randint(0, 999)))))
    for index, row in enumerate(rows):
        raw["deliveries"].append({"delivery_id": f"case-{number}-delivery-{index}",
                                  "delivered_at": row["available_at"] + rng.randint(0, 80),
                                  "record": row})
    rng.shuffle(raw["deliveries"])
    return raw


def _variants(raw: dict, rng: random.Random) -> dict[str, dict]:
    shuffled = deepcopy(raw)
    rng.shuffle(shuffled["deliveries"])
    duplicate = deepcopy(raw)
    duplicate["deliveries"] += deepcopy(raw["deliveries"])
    retried = deepcopy(raw)
    for item in raw["deliveries"]:
        retry = deepcopy(item)
        retry["delivery_id"] += "-retry"
        retry["delivered_at"] += 100
        retried["deliveries"].append(retry)
    return {"source_shuffle": shuffled, "exact_delivery_replay": duplicate,
            "distinct_delivery_retry": retried}


def _publication_view(records: tuple) -> list[dict]:
    return [{"revision": row.revision, "published_at": row.published_at,
             "source_cutoff": row.source_cutoff, "value": row.value,
             "source_versions": [list(pair) for pair in row.source_versions]}
            for row in records]


def _coverage(raw: dict) -> dict[str, bool]:
    """Measure edges in the generated input, rather than assuming anchors."""
    deliveries = raw["deliveries"]
    rows = [delivery["record"] for delivery in deliveries]
    pairs = [(left, right) for left in rows for right in rows
             if left["event_id"] == right["event_id"]
             and left["revision"] < right["revision"]]
    relevant = [row for row in rows if row["customer_id"] == "C1"
                and 540 <= row["event_time"] < 600]
    return {
        "known_empty_source": not rows,
        "inclusive_lower_boundary": any(row["event_time"] == 540 for row in relevant),
        "exclusive_upper_boundary": any(row["event_time"] == 600 for row in rows),
        "availability_at_decision": any(row["available_at"] == 600 for row in relevant),
        "equal_availability_revisions": any(a["available_at"] == b["available_at"] for a, b in pairs),
        "revision_gaps": any(b["revision"] - a["revision"] > 1 for a, b in pairs),
        "inclusive_publication_deadline": any(row["available_at"] == 610 for row in relevant),
        "after_deadline_source": any(row["available_at"] == 611 for row in relevant),
        "same_value_new_provenance": any(a["amount"] == b["amount"]
            and a["available_at"] < b["available_at"] <= 610 for a, b in pairs),
        "multiple_customers": len({row["customer_id"] for row in rows}) > 1,
        "delayed_transport_delivery": any(delivery["delivered_at"] > delivery["record"]["available_at"]
                                          for delivery in deliveries),
    }


def run_checks(seed: int = DEFAULT_SEED, cases: int = DEFAULT_CASES) -> dict:
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(cases) is not int or cases < 1:
        raise ValueError("cases must be a positive integer")
    # The harness imports implementation code; the two oracles above do not.
    import capstone_lab as lab
    import foundations_lab as foundation
    import parity_lab as serving

    rng = random.Random(seed)
    counts = Counter()
    coverage = Counter()
    corpus = sha256()
    for number in range(cases):
        raw = _fixture(rng, number)
        original = deepcopy(raw)
        decisions = (
            lab.Decision("D1", "C1", 600), lab.Decision("D2", "C1", 610),
            lab.Decision("D3", "C2", rng.choice((60, 540, 599, 605, 620))),
            lab.Decision("Z1", "C9", 600), lab.Decision("U1", "C1", 600, False))
        expected = {mode: [historical_oracle(raw, asdict(decision),
                                cutoff=620 if mode == "snapshot_baseline" else None)
                           for decision in decisions]
                    for mode in ("snapshot_baseline", "contract_pipeline")}
        expected_publications = publication_oracle(raw)
        corpus.update(json.dumps({"raw": raw, "decisions": [asdict(d) for d in decisions]},
                                 sort_keys=True, separators=(",", ":")).encode())
        case = lab.Case("base", foundation.ledger_from_dict(raw), decisions=decisions)
        for mode in ("snapshot_baseline", "contract_pipeline"):
            _equal(lab.build_dataset(case, mode), expected[mode],
                   f"case {number} historical {mode}")
            counts["historical_oracle_rows"] += len(decisions)
        records = lab.publications(case)
        _equal(_publication_view(records), expected_publications,
               f"case {number} publication oracle")
        counts["publication_oracle_cases"] += 1
        for label, variant in _variants(raw, rng).items():
            replay = lab.Case("base", foundation.ledger_from_dict(variant), decisions=decisions)
            _equal(lab.source_identity(replay.ledger), lab.source_identity(case.ledger),
                   f"case {number} {label} identity")
            for mode in ("snapshot_baseline", "contract_pipeline"):
                _equal(lab.build_dataset(replay, mode), expected[mode],
                       f"case {number} {label} {mode}")
                counts["metamorphic_historical_rows"] += len(decisions)
            _equal(_publication_view(lab.publications(replay)), expected_publications,
                   f"case {number} {label} publications")
            counts[label] += 1

        # Check Q0-Q5 independently from the implementation's request constant.
        for mode in ("snapshot_baseline", "contract_pipeline"):
            actual = lab.online_lookups(case, mode)
            _equal([row["requested_at"] for row in actual],
                   [599, 600, 605, 606, 610, 620], f"case {number} request clocks")
            for minute, row in zip((599, 600, 605, 606, 610, 620), actual):
                eligible = [p for p in expected_publications if p["published_at"] <= minute]
                value = None if not eligible else (
                    sum(p["value"] for p in eligible) if mode == "snapshot_baseline"
                    else eligible[-1]["value"])
                _equal(row["raw_value"], value, f"case {number} online {minute} {mode}")
                _equal(row["feature_missing"], value is None, f"case {number} missing flag")
                _equal(row["fallback_used"], value is None, f"case {number} fallback flag")
                counts["online_oracle_rows"] += 1

        # Independent sink data: source generation/publication correctness
        # cannot make these order checks pass accidentally. Start with unique
        # out-of-order snapshots; only the next variant introduces duplicates.
        values = [rng.randint(0, 1000) for _ in range(rng.randint(2, 7))]
        synthetic = tuple(serving.PublishedRevision(
            serving.KEY, index + 1, 600 + index, 600 + index, value,
            (("sink-event", index + 1),)) for index, value in enumerate(values))
        shuffled = list(synthetic)
        rng.shuffle(shuffled)
        sink_variants = {"sink_unique_shuffle": shuffled,
                         "sink_stale_arrives_last": list(reversed(synthetic)),
                         "sink_duplicate_replay": shuffled + list(synthetic) * 2}
        for label, deliveries in sink_variants.items():
            for mode in ("snapshot_baseline", "contract_pipeline"):
                cell = lab.consume_snapshots(deliveries, mode)
                wanted = sum(values) if mode == "snapshot_baseline" else values[-1]
                _equal(cell["value"], wanted, f"case {number} {label} {mode}")
                _equal(cell["source_versions"], [["sink-event", len(values)]],
                       f"case {number} {label} final lineage")
                counts[label] += 1
        _equal(raw, original, f"case {number} input mutation")
        for category, covered in _coverage(raw).items():
            coverage[category] += covered
        coverage["known_zero_history"] += 1
        coverage["unknown_history"] += 1
    if cases >= 2 and not all(coverage.values()):
        raise AssertionError("generator lost a required edge category")
    return {"status": "passed", "seed": seed, "generated_cases": cases,
            "checks": dict(sorted(counts.items())),
            "coverage": dict(sorted(coverage.items())),
            "corpus_sha256": corpus.hexdigest(),
            "scope": "Finite deterministic checks; not exhaustive or a proof."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--cases", type=int, default=DEFAULT_CASES)
    args = parser.parse_args()
    print(json.dumps(run_checks(args.seed, args.cases), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
