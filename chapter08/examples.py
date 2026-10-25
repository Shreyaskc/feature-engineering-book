"""Small, reproducible observations used in the chapter narrative."""
import json

from foundations_lab import ledger_from_dict, spend_in_window
from fault_testing_lab import (
    Query, base_fixture, blind_spot_report, evaluate, malformed_cases,
    mutation_report, run_check,
)


def example_report() -> dict:
    report = mutation_report()
    history = ledger_from_dict(base_fixture()).history
    fixed = {str(cutoff): spend_in_window(history, "C1", window_start=540,
             window_end=600, known_at=cutoff) for cutoff in (604, 605, 606, 607)}
    reversed_data = base_fixture()
    reversed_data["deliveries"].reverse()
    upper = base_fixture()
    upper["deliveries"].append({"delivery_id": "upper", "delivered_at": 600,
        "record": {"event_id": "U", "revision": 1, "customer_id": "C1",
                   "event_time": 600, "available_at": 600,
                   "amount": 7, "op": "upsert"}})
    return {
        "reference": {"D1": evaluate(base_fixture()),
                      "D2": evaluate(base_fixture(), Query(decision_at=610))},
        "five_fault_witnesses": {
            "M1_D1": evaluate(base_fixture(), implementation="M1_latest_before_cutoff"),
            "M2_D2": evaluate(base_fixture(), Query(decision_at=610), implementation="M2_count_deliveries"),
            "M3_D1_plus_upper": evaluate(upper, implementation="M3_inclusive_upper"),
            "M4_reversed_D2": evaluate(reversed_data, Query(decision_at=610), implementation="M4_input_order_latest"),
            "M5_missing_B_available_at": evaluate(malformed_cases()["missing_available_at"], implementation="M5_infer_availability")},
        "schema_reference": {x["case"]: x["observed"] for x in run_check("source_schema")["observations"]},
        "fixed_window_later_knowledge": fixed,
        "why_monotonicity_is_invalid": "The window stays [540,600). C2 reduces C from30 to25 at605; B adds40 at607. Later knowledge does not imply nondecreasing spend.",
        "matrix": report["matrix"], "suite_results": report["suite_results"],
        "blind_spots": blind_spot_report(),
        "scope": "source-availability reference, not a claim about the value actually served"
    }


if __name__ == "__main__":
    print(json.dumps(example_report(), indent=2, sort_keys=True))
