"""Worked answers, executable independently of the learner scaffolds."""
from copy import deepcopy
import json

from foundations_lab import ContractError, ledger_from_dict, spend_in_window
from fault_testing_lab import Query, base_fixture, evaluate


def replay_witness() -> dict:
    data = base_fixture()
    repeated = deepcopy(data)
    repeated["deliveries"] *= 2
    mutant = "M2_count_deliveries"
    return {"reference_original": evaluate(data),
            "reference_replayed": evaluate(repeated),
            "mutant_original": evaluate(data, implementation=mutant),
            "mutant_replayed": evaluate(repeated, implementation=mutant)}


def availability_witness() -> dict:
    data = base_fixture()
    row = next(item["record"] for item in data["deliveries"]
               if item["record"]["event_id"] == "B")
    del row["available_at"]
    try:
        evaluate(data)
    except ContractError:
        rejected = True
    else:
        rejected = False
    return {"reference_rejected": rejected,
            "mutant_value": evaluate(data, implementation="M5_infer_availability")}


def coverage_witness() -> dict:
    empty = base_fixture()
    empty["deliveries"] = []
    unknown = Query(history_known=False)
    return {"known_empty": evaluate(empty),
            "unknown_empty": evaluate(empty, unknown),
            "unknown_partial": evaluate(base_fixture(), unknown)}


def later_knowledge_witness() -> dict:
    history = ledger_from_dict(base_fixture()).history
    return {cutoff: spend_in_window(history, "C1", window_start=540,
            window_end=600, known_at=cutoff) for cutoff in (604, 605, 607)}


def answer_report() -> dict:
    return {"exercise_1": replay_witness(),
            "exercise_2": availability_witness(),
            "exercise_3": coverage_witness(),
            "exercise_4": {str(k): v for k, v in later_knowledge_witness().items()}}


if __name__ == "__main__":
    print(json.dumps(answer_report(), indent=2, sort_keys=True))
