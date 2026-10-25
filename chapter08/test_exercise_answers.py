import unittest
from exercise_answers import (
    replay_witness, availability_witness, coverage_witness,
    later_knowledge_witness,
)


class ExerciseAnswerTests(unittest.TestCase):
    def test_replay(self):
        self.assertEqual(replay_witness(), {"reference_original": 50,
            "reference_replayed": 50, "mutant_original": 50,
            "mutant_replayed": 100})

    def test_schema(self):
        self.assertEqual(availability_witness(), {
            "reference_rejected": True, "mutant_value": 90})

    def test_coverage(self):
        self.assertEqual(coverage_witness(), {
            "known_empty": 0, "unknown_empty": None, "unknown_partial": None})

    def test_fixed_window(self):
        self.assertEqual(later_knowledge_witness(), {604: 50, 605: 45, 607: 85})


if __name__ == "__main__":
    unittest.main()
