"""Boundary and known-counterexample checks for the beginner readiness lab."""
from dataclasses import FrozenInstanceError, replace
import json
import unittest

import readiness_lab as lab


class ReadinessTests(unittest.TestCase):
    def test_two_original_book_examples_match_the_printed_outputs(self):
        result = lab.book_examples()
        self.assertEqual(result['refresher_python_values']['stdout'],'[False, True, False]\nTrue\n')
        self.assertEqual(result['refresher_sql_filtering']['stdout'],'50\n')

    def test_none_zero_and_false_keep_separate_types_and_absence(self):
        result = lab.absence_example()
        self.assertEqual(result['is_missing'],[False,True,False,False])
        self.assertEqual(result['types'],['int','NoneType','bool','int'])
        self.assertTrue(result['zero_equals_false'])

    def test_truthiness_is_not_a_missingness_policy(self):
        result = lab.absence_example()
        self.assertEqual(result['truthiness'],[False,False,False,True])
        self.assertNotEqual(result['truthiness'],result['is_missing'])

    def test_frozen_record_rejects_assignment(self):
        record = lab.Event('A',550,551,20)
        with self.assertRaises(FrozenInstanceError):record.amount = 25
        self.assertEqual(record.amount,20)

    def test_replace_creates_a_new_record(self):
        original = lab.Event('A',550,551,20)
        replacement = replace(original,amount=25)
        self.assertIsNot(original,replacement)
        self.assertEqual((original.amount,replacement.amount),(20,25))

    def test_lower_event_boundary_is_included(self):
        self.assertTrue(lab.eligible(lab.Event('K',540,540,5),540,600,600))

    def test_upper_event_boundary_is_excluded(self):
        self.assertFalse(lab.eligible(lab.Event('U',600,600,7),540,600,600))

    def test_availability_equality_is_allowed_and_later_is_excluded(self):
        self.assertTrue(lab.eligible(lab.Event('K',550,600,5),540,600,600))
        self.assertFalse(lab.eligible(lab.Event('K',550,601,5),540,600,600))

    def test_small_fixture_has_a_hand_calculated_answer(self):
        data = lab.fixture()
        self.assertEqual(lab.total([lab.Event(*row) for row in data['base_events']]),20+30)
        self.assertEqual(lab.boundary_example(data)['lower_boundary_included'],55)

    def test_customer_join_duplicates_decisions(self):
        result = lab.sql_example(lab.fixture())
        self.assertEqual((result['wrong_customer_join_rows'],result['decision_join_rows']),(4,2))
        self.assertEqual(result['decision_values'],[['D1',50],['D2',95]])

    def test_filter_before_rank_preserves_the_eligible_older_revision(self):
        result = lab.sql_example(lab.fixture())
        self.assertEqual(result['latest_eligible_fixed_at_600'],50)
        self.assertEqual(result['wrong_rank_before_availability'],20)
        self.assertEqual(result['latest_eligible_fixed_at_610'],85)

    def test_complete_typed_report_matches_reviewed_expected_output(self):
        expected = json.loads((lab.ROOT/'expected_output.json').read_text())
        self.assertEqual(json.dumps(lab.report(),sort_keys=True),json.dumps(expected,sort_keys=True))


if __name__ == '__main__':
    unittest.main()
