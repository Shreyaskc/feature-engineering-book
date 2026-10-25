"""Learner scaffolds; import safely, then implement each TODO.

Run your work with: python -m unittest test_exercise_answers.py
Those tests target the worked answers by default. To test your versions,
change their import from exercise_answers to exercises in a personal copy.
Never weaken the expectations merely to get a green run.
"""
from copy import deepcopy
from fault_testing_lab import Query, base_fixture, evaluate


def replay_witness() -> dict:
    """Exercise 1: original/replayed D1 for reference and count-deliveries.

    Return keys reference_original, reference_replayed, mutant_original,
    mutant_replayed. Duplicate the full raw delivery list, keeping the
    cutoff fixed at600; use two independent deep copies.
    """
    data = base_fixture()
    repeated = deepcopy(data)
    # TODO: transform repeated, evaluate both implementations and return.
    raise NotImplementedError("Implement the replay relation")


def availability_witness() -> dict:
    """Exercise 2: remove B.available_at, recording reference rejection and
    M5's returned number. Return reference_rejected and mutant_value.
    Do not change event_time, availability in other rows, or decision_at.
    """
    data = base_fixture()
    # TODO: remove the required field; catch ContractError specifically.
    raise NotImplementedError("Implement the malformed-source witness")


def coverage_witness() -> dict:
    """Exercise 3: return known_empty, unknown_empty and unknown_partial.
    Unknown coverage is supplied explicitly; never derive it from length.
    """
    data = base_fixture()
    # TODO: use fresh empty and partial fixtures with both coverage flags.
    raise NotImplementedError("Implement the coverage witness")


def later_knowledge_witness() -> dict:
    """Exercise 4: fixed [540,600), known_at604/605/607; return integer-keyed
    mapping. Explain why 'adding later information never reduces spend' is
    invalid while adding information unavailable at a fixed cutoff is safe.
    """
    # TODO: use the inherited ledger_from_dict and spend_in_window API.
    raise NotImplementedError("Distinguish fixed-cutoff invariance from monotonicity")
