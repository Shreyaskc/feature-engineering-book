"""Finite one-shot inputs must preserve values, labels, lineage, and failures."""
from dataclasses import replace
import unittest

from chapter4 import (DECISIONS, EVENTS, FINALIZED_AT, OUTCOMES,
                      build_dataset, canonical_events, historical_sum, label_at)


class Once:
    """An iterable that fails if its input stream is traversed more than once."""
    def __init__(self, rows):
        self.rows = rows
        self.used = False

    def __iter__(self):
        if self.used:
            raise AssertionError("input stream was traversed twice")
        self.used = True
        return iter(self.rows)


FACTORIES = (list, tuple, iter, lambda rows: (row for row in rows), Once)


class IterableInputTests(unittest.TestCase):
    def test_canonical_event_records_preserve_source_provenance(self):
        expected = canonical_events(EVENTS)
        for factory in FACTORIES:
            with self.subTest(factory=factory):
                actual = canonical_events(factory(EVENTS))
                self.assertEqual(actual, expected)
                self.assertEqual([(e.customer, e.event, e.version, e.available_at)
                                  for e in actual],
                                 [(e.customer, e.event, e.version, e.available_at)
                                  for e in expected])

    def test_historical_sum_accepts_each_iterable_variant(self):
        for factory in FACTORIES:
            for cutoff, value in ((600, 50), (610, 95)):
                with self.subTest(factory=factory, cutoff=cutoff):
                    self.assertEqual(historical_sum(factory(EVENTS), 'C1', cutoff), value)

    def test_dataset_events_preserve_complete_rows_labels_and_cutoffs(self):
        for factory in FACTORIES:
            with self.subTest(factory=factory):
                self.assertEqual(build_dataset(events=factory(EVENTS)), build_dataset())

    def test_dataset_decisions_preserve_complete_rows_and_exclusions(self):
        for factory in FACTORIES:
            with self.subTest(factory=factory):
                self.assertEqual(build_dataset(decisions=factory(DECISIONS)), build_dataset())

    def test_dataset_outcomes_preserve_complete_rows_and_labels(self):
        for factory in FACTORIES:
            with self.subTest(factory=factory):
                self.assertEqual(build_dataset(outcomes=factory(OUTCOMES)), build_dataset())

    def test_all_inputs_can_be_one_shot_together(self):
        self.assertEqual(build_dataset(Once(DECISIONS), Once(EVENTS), Once(OUTCOMES)),
                         build_dataset())

    def test_direct_label_boundary_accepts_one_shot_outcomes(self):
        for factory in FACTORIES:
            for decision in DECISIONS:
                with self.subTest(factory=factory, decision=decision.decision_id):
                    self.assertEqual(label_at(decision, factory(OUTCOMES), FINALIZED_AT, 1500),
                                     label_at(decision, OUTCOMES, FINALIZED_AT, 1500))

    def test_empty_iterables_preserve_empty_and_zero_semantics(self):
        for factory in FACTORIES:
            with self.subTest(factory=factory):
                self.assertEqual(canonical_events(factory([])), [])
                self.assertEqual(historical_sum(factory([]), 'C1', 600), 0)
                self.assertEqual(build_dataset(factory([]), factory([]), factory([])), ([], []))
                self.assertEqual(build_dataset(events=factory([]), outcomes=factory([])),
                                 build_dataset(events=[], outcomes=[]))

    def test_replayed_one_shot_records_remain_idempotent(self):
        self.assertEqual(build_dataset(events=Once(EVENTS * 2), outcomes=Once(OUTCOMES * 2)),
                         build_dataset())

    def test_conflicting_event_identity_is_rejected_for_every_variant(self):
        for factory in FACTORIES:
            with self.subTest(factory=factory), self.assertRaisesRegex(ValueError, 'conflicting'):
                build_dataset(events=factory(EVENTS + [replace(EVENTS[0], amount=21)]))

    def test_duplicate_decisions_are_rejected_for_every_variant(self):
        for factory in FACTORIES:
            with self.subTest(factory=factory), self.assertRaisesRegex(ValueError, 'unique'):
                build_dataset(decisions=factory(DECISIONS + [DECISIONS[0]]))

    def test_conflicting_outcome_identity_is_rejected_for_every_variant(self):
        for factory in FACTORIES:
            with self.subTest(factory=factory), self.assertRaisesRegex(ValueError, 'conflicting'):
                build_dataset(outcomes=factory(OUTCOMES + [replace(OUTCOMES[0], occurred_at=681)]))


if __name__ == '__main__':
    unittest.main()
