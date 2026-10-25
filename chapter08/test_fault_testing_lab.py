"""Contract, fault-witness and harness-integrity checks."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import fault_testing_lab as lab
from foundations_lab import ContractError, ledger_from_dict, spend_in_window


class ReferenceContractTests(unittest.TestCase):
    def test_hand_calculated_decisions(self):
        self.assertEqual(lab.evaluate(lab.base_fixture()), 50)
        self.assertEqual(lab.evaluate(lab.base_fixture(), lab.Query(decision_at=610)), 95)

    def test_availability_is_inclusive_but_amount_need_not_increase(self):
        history = ledger_from_dict(lab.base_fixture()).history
        answers = [spend_in_window(history, "C1", window_start=540,
                   window_end=600, known_at=cutoff) for cutoff in (604, 605, 606, 607)]
        self.assertEqual(answers, [50, 45, 45, 85])

    def test_event_boundary_neighbors(self):
        for event_time, expected in ((539, 0), (540, 5), (599, 5), (600, 0)):
            with self.subTest(event_time=event_time):
                data = lab.boundary_fixture()
                data["deliveries"] = [data["deliveries"][0]]
                item = data["deliveries"][0]
                item["record"]["event_time"] = event_time
                item["record"]["available_at"] = 600
                item["delivered_at"] = 600
                self.assertEqual(lab.evaluate(data), expected)

    def test_coverage_is_explicit_not_inferred_from_rows(self):
        empty = lab.base_fixture()
        empty["deliveries"] = []
        self.assertEqual(lab.evaluate(empty), 0)
        self.assertIsNone(lab.evaluate(empty, lab.Query(history_known=False)))
        self.assertIsNone(lab.evaluate(lab.base_fixture(), lab.Query(history_known=False)))

    def test_missing_null_boolean_availability_fail_closed(self):
        for name, data in lab.malformed_cases().items():
            for known in (True, False):
                with self.subTest(name=name, history_known=known):
                    with self.assertRaises(ContractError):
                        lab.evaluate(deepcopy(data), lab.Query(history_known=known))

    def test_false_available_at_also_rejects(self):
        data = lab.base_fixture()
        data["deliveries"][0]["record"]["available_at"] = False
        with self.assertRaises(ContractError):
            lab.evaluate(data)

    def test_invalid_query_rejects(self):
        queries = (lab.Query(decision_at=True), lab.Query(window_minutes=False),
                   lab.Query(history_known=0), lab.Query(customer_id=""),
                   lab.Query(window_minutes=601))
        for query in queries:
            with self.subTest(query=query), self.assertRaises(ContractError):
                lab.evaluate(lab.base_fixture(), query)

    def test_source_availability_does_not_claim_served_value(self):
        data = lab.base_fixture()
        for item in data["deliveries"]:
            item["delivered_at"] += 1000
        # Source-availability query does not select by transport delivery.
        self.assertEqual(lab.evaluate(data), 50)

    def test_no_inputs_are_modified(self):
        for name in lab.IMPLEMENTATIONS:
            for data in (lab.base_fixture(), lab.malformed_cases()["missing_available_at"]):
                with self.subTest(implementation=name):
                    original = deepcopy(data)
                    try:
                        lab.evaluate(data, implementation=name)
                    except ContractError:
                        pass
                    self.assertEqual(data, original)

    def test_inherited_files_match_declared_original_hashes(self):
        root = Path(__file__).parent
        manifest = json.loads((root / "vendor_manifest.json").read_text("utf-8"))
        for relative, expected in manifest["sha256"].items():
            with self.subTest(path=relative):
                self.assertEqual(hashlib.sha256((root / relative).read_bytes()).hexdigest(), expected)


class ControlledFaultTests(unittest.TestCase):
    def test_reducing_C_counterexample_preserves_only_necessary_versions(self):
        data = lab.base_fixture()
        data["deliveries"] = [item for item in data["deliveries"]
                               if item["record"]["event_id"] == "C"]
        for kept, expected_reference, expected_mutant in (
                ((1, 2), 30, 0), ((2,), 0, 0), ((1,), 30, 30)):
            with self.subTest(kept=kept):
                candidate = deepcopy(data)
                candidate["deliveries"] = [item for item in candidate["deliveries"]
                    if item["record"]["revision"] in kept]
                self.assertEqual(lab.evaluate(candidate), expected_reference)
                self.assertEqual(lab.evaluate(candidate,
                    implementation="M1_latest_before_cutoff"), expected_mutant)

    def test_five_diagnostic_numeric_witnesses(self):
        from examples import example_report
        self.assertEqual(example_report()["five_fault_witnesses"], {
            "M1_D1": 20, "M2_D2": 125, "M3_D1_plus_upper": 57,
            "M4_reversed_D2": 100, "M5_missing_B_available_at": 90})

    def test_schema_mutant_only_infers_absent_key(self):
        for case in ("null_available_at", "bool_available_at", "string_available_at"):
            with self.subTest(case=case), self.assertRaises(ContractError):
                lab.evaluate(lab.malformed_cases()[case], implementation="M5_infer_availability")

    def test_reference_passes_all_named_checks(self):
        for name in lab.CHECKS:
            with self.subTest(check=name):
                self.assertEqual(lab.run_check(name)["status"], "PASS")

    def test_detection_matrix_matches_discriminating_witnesses(self):
        expected = {
            "d1_happy_path": ["M1_latest_before_cutoff"],
            "nonnegative_integer": [],
            "hand_calculated": ["M1_latest_before_cutoff", "M2_count_deliveries"],
            "shuffled_input": ["M4_input_order_latest"],
            "replayed_input": ["M2_count_deliveries"],
            "half_open_boundary": ["M3_inclusive_upper"],
            "later_info_invariance": ["M1_latest_before_cutoff"],
            "source_schema": ["M5_infer_availability"],
            "unknown_coverage": [],
        }
        actual = {name: [implementation for implementation, status in row.items()
                         if status == "ASSERTION_FAILED"]
                  for name, row in lab.mutation_report()["matrix"].items()}
        self.assertEqual(actual, expected)

    def test_weak_suite_survival_is_false_confidence(self):
        result = lab.mutation_report()["suite_results"]
        self.assertEqual(result["weak"]["detected_count"], 1)
        self.assertEqual(result["diagnostic"]["detected_count"], 5)
        self.assertTrue(lab.run_suite("M2_count_deliveries", suite="weak")["passed"])

    def test_constant_zero_can_pass_relations_and_fail_known_answers(self):
        result = lab.blind_spot_report()["constant_zero_probe_outside_mutant_registry"]
        for relation in ("shuffled_input", "replayed_input", "later_info_invariance"):
            self.assertEqual(result[relation], "PASS")
        self.assertEqual(result["hand_calculated"], "ASSERTION_FAILED")
        self.assertEqual(result["unknown_coverage"], "ASSERTION_FAILED")
        self.assertEqual(len(lab.MUTANTS), 5)


class HarnessIntegrityTests(unittest.TestCase):
    def test_each_check_invocation_isolated_from_mutating_candidate(self):
        def mutating_candidate(data, query):
            answer = lab.reference(data, query)
            data["deliveries"].clear()
            return answer
        with patch.dict(lab.IMPLEMENTATIONS, {"M4_input_order_latest": mutating_candidate}):
            for name in lab.CHECKS:
                with self.subTest(check=name):
                    self.assertEqual(lab.run_check(name,
                        "M4_input_order_latest")["status"], "PASS")

    def test_registry_rejects_arbitrary_code_or_callable(self):
        for name in ("unknown", "__import__('os')", "reference()"):
            with self.subTest(name=name), self.assertRaises(ContractError):
                lab.evaluate(lab.base_fixture(), implementation=name)

    def test_unknown_check_suite_and_query_are_rejected(self):
        with self.assertRaises(ContractError):
            lab.run_check("unknown")
        with self.assertRaises(ContractError):
            lab.run_suite(suite="unknown")
        with self.assertRaises(ContractError):
            lab.evaluate(lab.base_fixture(), query={})

    def test_boolean_output_cannot_masquerade_as_zero(self):
        self.assertFalse(lab._observation("typed result", False, 0)["passed"])

    def test_unexpected_error_is_never_counted_as_detection(self):
        def crashed(data, query):
            raise RuntimeError("synthetic harness-integrity probe")
        # This patches only the lab's registry, never the foundation module.
        with patch.dict(lab.IMPLEMENTATIONS, {"M1_latest_before_cutoff": crashed}):
            cell = lab.run_check("hand_calculated", "M1_latest_before_cutoff")
            self.assertEqual(cell["status"], "ERROR")
            with self.assertRaisesRegex(AssertionError, "harness error"):
                lab.mutation_report()

    def test_reference_failure_aborts_report(self):
        with patch.dict(lab.IMPLEMENTATIONS, {"reference": lambda data, query: 0}):
            with self.assertRaisesRegex(AssertionError, "reference failed"):
                lab.mutation_report()


if __name__ == "__main__":
    unittest.main()
