"""Chapter 8: controlled faults and the evidence that exposes them.

Python 3.12, standard library only. All implementations are explicit local
functions. Nothing rewrites, patches, imports arbitrary code into, or changes
the unchanged foundation module. These mutants are teaching examples, never
production alternatives. Source availability is not a served-value log.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import random
from typing import Callable

from foundations_lab import ContractError, Ledger, ledger_from_dict, spend

ROOT = Path(__file__).parent


@dataclass(frozen=True)
class Query:
    customer_id: str = "C1"
    decision_at: int = 600
    window_minutes: int = 60
    history_known: bool = True


def base_fixture() -> dict:
    """Return a fresh raw JSON-shaped fixture; callers may safely edit it."""
    return json.loads((ROOT / "fixtures" / "base.json").read_text("utf-8"))


def _value(ledger: Ledger, query: Query) -> int | None:
    return spend(ledger.history, query.customer_id, query.decision_at,
                 window_minutes=query.window_minutes,
                 history_known=query.history_known)


def reference(data: object, query: Query) -> int | None:
    """Strict source schema followed by the unchanged foundation contract."""
    return _value(ledger_from_dict(data), query)


def _validated(data: object, query: Query) -> Ledger:
    ledger = ledger_from_dict(data)
    # Mutants keep the same source and query validation. Only the named
    # calculation fault changes. The inference mutant changes parsing instead.
    _value(ledger, query)
    return ledger


def _sum(rows, query: Query, *, inclusive_upper: bool = False) -> int | None:
    if not query.history_known:
        return None
    lower = query.decision_at - query.window_minutes
    return sum(row.amount for row in rows
               if row.customer_id == query.customer_id
               and row.op == "upsert"
               and lower <= row.event_time
               and (row.event_time <= query.decision_at if inclusive_upper
                    else row.event_time < query.decision_at))


def latest_before_cutoff(data: object, query: Query) -> int | None:
    """FAULT M1: choose latest overall, then discard unavailable versions.

    This loses the earlier eligible revision when a future revision exists;
    it does not literally add the future revision's amount to the answer.
    """
    ledger = _validated(data, query)
    latest = {}
    for row in ledger.history:
        latest[row.event_id] = row
    return _sum((r for r in latest.values()
                 if r.available_at <= query.decision_at), query)


def count_deliveries(data: object, query: Query) -> int | None:
    """FAULT M2: count every eligible transport row, including revisions."""
    _validated(data, query)
    # Read the raw rows intentionally: a Ledger would remove equal retries.
    from foundations_lab import Revision
    rows = (Revision(**item["record"]) for item in data["deliveries"])
    return _sum((r for r in rows if r.available_at <= query.decision_at), query)


def inclusive_upper(data: object, query: Query) -> int | None:
    """FAULT M3: include an event exactly at the decision time."""
    ledger = _validated(data, query)
    from foundations_lab import selected_revisions
    rows = selected_revisions(ledger.history, known_at=query.decision_at)
    return _sum(rows, query, inclusive_upper=True)


def input_order_latest(data: object, query: Query) -> int | None:
    """FAULT M4: last eligible input row wins, independent of revision."""
    _validated(data, query)
    from foundations_lab import Revision
    latest = {}
    for item in data["deliveries"]:
        row = Revision(**item["record"])
        if row.available_at <= query.decision_at:
            latest[row.event_id] = row
    return _sum(latest.values(), query)


def infer_availability(data: object, query: Query) -> int | None:
    """FAULT M5: invent source availability when its key is absent.

    Nulls and booleans are still rejected. The source-schema check exercises
    each separately, so absence is not confused with a present invalid value.
    """
    candidate = deepcopy(data)
    if isinstance(candidate, dict) and isinstance(candidate.get("deliveries"), list):
        for item in candidate["deliveries"]:
            if isinstance(item, dict) and isinstance(item.get("record"), dict):
                row = item["record"]
                if "available_at" not in row:
                    row["available_at"] = row.get("event_time")
    return reference(candidate, query)


IMPLEMENTATIONS: dict[str, Callable] = {
    "reference": reference,
    "M1_latest_before_cutoff": latest_before_cutoff,
    "M2_count_deliveries": count_deliveries,
    "M3_inclusive_upper": inclusive_upper,
    "M4_input_order_latest": input_order_latest,
    "M5_infer_availability": infer_availability,
}
MUTANTS = tuple(name for name in IMPLEMENTATIONS if name != "reference")


def evaluate(data: object, query: Query = Query(), *,
             implementation: str = "reference") -> int | None:
    """Run one allowlisted implementation; reference is the safe default."""
    if implementation not in IMPLEMENTATIONS:
        raise ContractError("unknown implementation; select an explicit registry name")
    if not isinstance(query, Query):
        raise ContractError("query must be a Query")
    return IMPLEMENTATIONS[implementation](data, query)


def _observation(case: str, observed: object, expected: object) -> dict:
    # bool is not accepted as an integer result, even though True == 1.
    return {"case": case, "observed": observed, "expected": expected,
            "passed": type(observed) is type(expected) and observed == expected}


def _check_d1(run: Callable) -> list[dict]:
    return [_observation("D1", run(base_fixture(), Query()), 50)]


def _check_nonnegative(run: Callable) -> list[dict]:
    values = [run(base_fixture(), Query(decision_at=t)) for t in (600, 610)]
    return [_observation("nonnegative numeric outputs", all(
        type(value) is int and value >= 0 for value in values), True)]


def _check_example(run: Callable) -> list[dict]:
    return [_observation("D1: A1 + C1", run(base_fixture(), Query()), 50),
            _observation("D2: A1 + B1 + C2 + D1",
                         run(base_fixture(), Query(decision_at=610)), 95)]


def _check_shuffle(run: Callable) -> list[dict]:
    data, query = base_fixture(), Query(decision_at=610)
    expected = run(data, query)
    observations = []
    reversed_data = deepcopy(data)
    reversed_data["deliveries"].reverse()
    observations.append(_observation("reversed input", run(reversed_data, query), expected))
    rng = random.Random(802)
    for index in range(6):
        shuffled = deepcopy(data)
        rng.shuffle(shuffled["deliveries"])
        observations.append(_observation(f"shuffle {index + 1}", run(shuffled, query), expected))
    return observations


def _check_replay(run: Callable) -> list[dict]:
    data, query = base_fixture(), Query()
    expected = run(data, query)
    replay = deepcopy(data)
    replay["deliveries"] *= 2
    retry = deepcopy(data)
    extra = deepcopy(retry["deliveries"][0])
    extra["delivery_id"] = "a1-second-delivery"
    extra["delivered_at"] = 609
    retry["deliveries"].append(extra)
    return [_observation("identical batch replay", run(replay, query), expected),
            _observation("new delivery ID for A1", run(retry, query), expected)]


def boundary_fixture() -> dict:
    data = {"schema_version": 1, "allow_restore": False, "deliveries": []}
    for key, event_time, amount in (("L", 540, 5), ("I", 599, 7), ("U", 600, 11)):
        data["deliveries"].append({"delivery_id": key.lower(), "delivered_at": event_time,
            "record": {"event_id": key, "revision": 1, "customer_id": "C1",
                       "event_time": event_time, "available_at": event_time,
                       "amount": amount, "op": "upsert"}})
    return data


def _check_boundary(run: Callable) -> list[dict]:
    return [_observation("[540, 600): 5 + 7; exclude 11",
                         run(boundary_fixture(), Query()), 12)]


def _check_later(run: Callable) -> list[dict]:
    full = base_fixture()
    full["deliveries"] = [item for item in full["deliveries"]
                           if item["record"]["event_id"] == "C"]
    earlier = deepcopy(full)
    earlier["deliveries"] = [item for item in earlier["deliveries"]
                             if item["record"]["available_at"] <= 600]
    return [_observation("append valid source information available after 600",
                         run(full, Query()), run(earlier, Query()))]


def malformed_cases() -> dict[str, dict]:
    """Separate absence, null and bool witnesses; no implicit coercion."""
    cases = {}
    for name, value in (("missing_available_at", "absent"),
                        ("null_available_at", None),
                        ("bool_available_at", True),
                        ("string_available_at", "551")):
        data = base_fixture()
        row = data["deliveries"][1]["record"]  # B: 575 event, 607 availability
        if name == "missing_available_at":
            del row["available_at"]
        else:
            row["available_at"] = value
        cases[name] = data
    data = base_fixture()
    data["deliveries"][0]["record"]["revision"] = True
    cases["bool_revision"] = data
    data = base_fixture()
    data["deliveries"][0]["record"]["unexpected"] = 1
    cases["unexpected_record_field"] = data
    data = base_fixture()
    conflicting = deepcopy(data["deliveries"][0])
    conflicting["delivery_id"] = "conflict"
    conflicting["record"]["amount"] = 21
    data["deliveries"].append(conflicting)
    cases["conflicting_source_revision"] = data
    return cases


def _check_schema(run: Callable) -> list[dict]:
    observations = []
    for name, data in malformed_cases().items():
        try:
            value = run(data, Query())
        except ContractError:
            outcome = "ContractError"
        else:
            outcome = f"returned {value!r}"
        observations.append(_observation(name, outcome, "ContractError"))
    return observations


def _check_coverage(run: Callable) -> list[dict]:
    empty = base_fixture()
    empty["deliveries"] = []
    return [_observation("known empty", run(empty, Query()), 0),
            _observation("unknown empty", run(empty, Query(history_known=False)), None),
            _observation("unknown partial", run(base_fixture(), Query(history_known=False)), None)]


CHECKS: dict[str, Callable] = {
    "d1_happy_path": _check_d1,
    "nonnegative_integer": _check_nonnegative,
    "hand_calculated": _check_example,
    "shuffled_input": _check_shuffle,
    "replayed_input": _check_replay,
    "half_open_boundary": _check_boundary,
    "later_info_invariance": _check_later,
    "source_schema": _check_schema,
    "unknown_coverage": _check_coverage,
}
WEAK_SUITE = ("d1_happy_path", "nonnegative_integer")
DIAGNOSTIC_SUITE = tuple(name for name in CHECKS if name not in WEAK_SUITE)

CHECK_NOTES = {
    "d1_happy_path": "One known answer does not cover other cutoffs, order, invalid data or boundaries.",
    "nonnegative_integer": "A wrong positive integer still passes; unknown coverage is never exercised.",
    "hand_calculated": "These two examples omit exact upper boundaries, malformed schema and reordered input.",
    "shuffled_input": "Order invariance can hold for a consistently wrong sum; the expected total is not fixed here.",
    "replayed_input": "Replay invariance alone cannot prove revision cutoff or boundary semantics.",
    "half_open_boundary": "Three single-version events do not probe retries, future revisions or malformed records.",
    "later_info_invariance": "A consistently wrong historical result can remain invariant; add an independent answer.",
    "source_schema": "Correctly shaped records can contain a false real-world availability timestamp.",
    "unknown_coverage": "Coverage semantics need an explicit assertion; the caller's coverage claim may itself be wrong.",
}


def run_check(name: str, implementation: str = "reference") -> dict:
    if name not in CHECKS or implementation not in IMPLEMENTATIONS:
        raise ContractError("unknown named check or implementation")
    try:
        observations = CHECKS[name](lambda data, query: evaluate(
            deepcopy(data), query, implementation=implementation))
    except Exception as error:
        # ERROR is distinct from evidence of the intended mutant fault.
        return {"status": "ERROR", "observations": [],
                "error": f"{type(error).__name__}: {error}"}
    return {"status": "PASS" if all(x["passed"] for x in observations) else "ASSERTION_FAILED",
            "observations": observations}


def run_suite(implementation: str = "reference", *, suite: str = "diagnostic") -> dict:
    if suite not in ("weak", "diagnostic"):
        raise ContractError("suite must be weak or diagnostic")
    names = WEAK_SUITE if suite == "weak" else DIAGNOSTIC_SUITE
    results = {name: run_check(name, implementation) for name in names}
    return {"implementation": implementation, "suite": suite,
            "passed": all(result["status"] == "PASS" for result in results.values()),
            "checks": results}


def mutation_report() -> dict:
    results = {name: {implementation: run_check(name, implementation)
                      for implementation in IMPLEMENTATIONS} for name in CHECKS}
    if any(cell["status"] == "ERROR" for row in results.values() for cell in row.values()):
        raise AssertionError("harness error; investigate instead of counting as detection")
    if any(row["reference"]["status"] != "PASS" for row in results.values()):
        raise AssertionError("reference failed; check the contract and harness first")
    detected = {}
    for suite, names in (("weak", WEAK_SUITE), ("diagnostic", DIAGNOSTIC_SUITE)):
        killed = [mutant for mutant in MUTANTS if any(
            results[name][mutant]["status"] == "ASSERTION_FAILED" for name in names)]
        detected[suite] = {"detected": killed, "detected_count": len(killed),
                           "survived": [m for m in MUTANTS if m not in killed],
                           "total_selected_mutants": len(MUTANTS)}
    return {"schema_version": 1, "implementations": list(IMPLEMENTATIONS),
            "checks": list(CHECKS), "matrix": {name: {
                impl: cell["status"] for impl, cell in row.items()}
                for name, row in results.items()}, "evidence": results,
            "suite_results": detected, "known_blind_spots": CHECK_NOTES,
            "interpretation": "PASS means this check did not expose a mismatch. ASSERTION_FAILED detects a specified mismatch. ERROR means an unexpected exception and aborts the report. No status proves general correctness.",
            "mutation_score_limit": "The diagnostic suite detects these five chosen artificial faults. The ratio is conditional on this mutant set, fixtures and assertions; it is not production reliability or exhaustive coverage.",
            "unmeasured": ["real-world timestamp truth", "served-value equality", "distributed failures", "performance and load", "unselected faults"]}


def blind_spot_report() -> dict:
    """Counterexamples to overclaiming; these are not additional mutants."""
    always_zero = lambda data, query: 0
    checks = {name: CHECKS[name](always_zero) for name in (
        "shuffled_input", "replayed_input", "later_info_invariance",
        "hand_calculated", "unknown_coverage", "nonnegative_integer")}
    empty = base_fixture()
    empty["deliveries"] = []
    return {
        "weak_suite_missed_count_deliveries": {
            "weak_passed": run_suite("M2_count_deliveries", suite="weak")["passed"],
            "D1_mutant": evaluate(base_fixture(), implementation="M2_count_deliveries"),
            "D2_mutant": evaluate(base_fixture(), Query(decision_at=610), implementation="M2_count_deliveries"),
            "D2_reference": evaluate(base_fixture(), Query(decision_at=610))},
        "constant_zero_probe_outside_mutant_registry": {
            name: "PASS" if all(item["passed"] for item in observations)
            else "ASSERTION_FAILED" for name, observations in checks.items()},
        "unknown_is_not_zero": {
            "known_empty": evaluate(empty),
            "unknown_empty": evaluate(empty, Query(history_known=False)),
            "unknown_partial": evaluate(base_fixture(), Query(history_known=False)),
            "arithmetic_only_suite_exercises_unknown_coverage": False},
        "limits": "A constant function passes these three invariance relations. Numeric anchors and explicit unknown-coverage assertions expose it. This probe is outside the five-mutant denominator."
    }


if __name__ == "__main__":
    print(json.dumps(mutation_report(), indent=2, sort_keys=True))
