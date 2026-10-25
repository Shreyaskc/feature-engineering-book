"""Independent reference, generated backfill and reproducible-report tests."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import backfill_lab as lab
from foundations_lab import Revision
import randomized_checks as checks


class ReferenceOracleTests(unittest.TestCase):
    def test_max_revision_not_input_order_or_largest_amount(self):
        history = (Revision("E", 9, "C", 70, 90, 3),
                   Revision("E", 2, "C", 70, 80, 900),
                   Revision("E", 6, "C", 70, 90, 7),
                   Revision("E", 12, "C", 70, 101, 99))
        result = checks.reference_records(history, (lab.Decision("D", "C", 100),),
                                          lab.Definition(60))
        self.assertEqual(result[0]["value"], 3)
        self.assertEqual(result[0]["contributors"], [["E", 9]])

    def test_exact_window_and_knowledge_boundaries(self):
        history = (
            Revision("before", 1, "C", 39, 39, 1000),
            Revision("lower", 1, "C", 40, 40, 2),
            Revision("inside", 1, "C", 99, 100, 3),
            Revision("upper", 1, "C", 100, 100, 100),
            Revision("late", 1, "C", 99, 101, 200),
            Revision("other", 1, "OTHER", 50, 50, 10000),
        )
        result = checks.reference_records(history, (lab.Decision("D", "C", 100),),
                                          lab.Definition(60))
        self.assertEqual(result[0]["value"], 5)
        self.assertEqual(result[0]["contributors"], [["inside", 1], ["lower", 1]])

    def test_corrected_cutoff_adds_late_arrival_and_latest_eligible_correction(self):
        history = (Revision("E", 1, "C", 90, 95, 10),
                   Revision("E", 3, "C", 90, 110, 4),
                   Revision("E", 8, "C", 90, 111, 200),
                   Revision("L", 1, "C", 99, 110, 20))
        decision = (lab.Decision("D", "C", 100),)
        historical = checks.reference_records(history, decision, lab.Definition())
        corrected = checks.reference_records(history, decision,
                                             lab.Definition(60, "corrected", 110))
        self.assertEqual(historical[0]["value"], 10)
        self.assertEqual(corrected[0]["value"], 24)
        self.assertEqual(corrected[0]["contributors"], [["E", 3], ["L", 1]])
        self.assertEqual(corrected[0]["known_at"], 110)

    def test_reference_does_not_call_production_calculation(self):
        history = (Revision("E", 1, "C", 90, 95, 11),)
        with patch.object(lab, "materialize", side_effect=AssertionError("production used")), \
             patch.object(lab, "selected_revisions", side_effect=AssertionError("selector used")), \
             patch.object(lab, "values", side_effect=AssertionError("values used")):
            result = checks.reference_records(history, (lab.Decision("D", "C", 100),),
                                              lab.Definition())
        self.assertEqual(result[0]["value"], 11)

    def test_empty_history_retains_each_decision_as_zero(self):
        decisions = (lab.Decision("B", "C", 100), lab.Decision("A", "OTHER", 90))
        result = checks.reference_records((), decisions, lab.Definition())
        self.assertEqual([row["decision_id"] for row in result], ["A", "B"])
        self.assertEqual([row["value"] for row in result], [0, 0])
        self.assertEqual([row["contributors"] for row in result], [[], []])


class GeneratedBackfillTests(unittest.TestCase):
    def test_generator_is_repeatable_and_varies_definitions(self):
        first = checks.generated_cases()
        self.assertEqual(first, checks.generated_cases())
        self.assertNotEqual(first, checks.generated_cases(seed=checks.DEFAULT_SEED + 1))
        self.assertEqual({case.definition.mode for case in first}, {"historical", "corrected"})
        self.assertEqual({case.definition.window_minutes for case in first}, set(checks.WINDOWS))
        self.assertTrue(any(not case.history for case in first))
        for case in first:
            with self.subTest(definition=case.definition):
                self.assertTrue(any(row.customer_id == "EMPTY" for row in case.coverage))
                self.assertFalse(any(row.customer_id == "EMPTY" for row in case.history))
                self.assertTrue(any(row.customer_id == "EMPTY" for row in case.decisions))

    def test_all_generated_cases_against_oracle_and_build_paths(self):
        report = checks.run_checks()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["generated_cases"], checks.DEFAULT_CASES)
        self.assertEqual(report["permutation_checks"],
                         checks.DEFAULT_CASES * checks.PERMUTATIONS_PER_CASE)
        self.assertEqual(report["whole_vs_resumed_build_checks"], checks.DEFAULT_CASES)
        self.assertEqual(report["complete_attempt_replay_checks"], checks.DEFAULT_CASES)
        self.assertEqual(report["runtime"], lab.local_runtime())
        self.assertEqual(report["fixture_vectors"]["corrected"], [102, 112, 0])

    def test_invalid_generator_arguments(self):
        for count in (0, -1, True, 2.0):
            with self.subTest(count=count), self.assertRaises(ValueError):
                checks.generated_cases(count=count)
        with self.assertRaises(ValueError):
            checks.generated_cases(seed=True)

    def test_json_cli_is_deterministic(self):
        command = [sys.executable, str(Path(checks.__file__)), "--cases", "2"]
        first = subprocess.run(command, check=True, capture_output=True, text=True)
        second = subprocess.run(command, check=True, capture_output=True, text=True)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first.stderr, "")
        report = json.loads(first.stdout)
        self.assertEqual(report["generated_cases"], 2)
        self.assertEqual(report["status"], "passed")


if __name__ == "__main__":
    unittest.main()
