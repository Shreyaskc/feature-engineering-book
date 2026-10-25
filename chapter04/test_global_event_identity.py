"""Global business-event identities cannot be reused by another customer."""
from dataclasses import replace
import unittest

from chapter4 import Event, build_dataset, canonical_events, historical_sum


class GlobalEventIdentityTests(unittest.TestCase):
    def histories(self, revision):
        original = Event('C1', 'global-event', 1, 550, 551, 20)
        reassigned = replace(original, customer='C2', version=revision,
                             available_at=551 if revision == 1 else 552)
        return ([original, reassigned], [reassigned, original])

    def test_same_revision_cannot_be_reused_by_another_customer(self):
        for rows in self.histories(1):
            for factory in (list, iter):
                with self.subTest(rows=rows, factory=factory), self.assertRaises(ValueError):
                    canonical_events(factory(rows))

    def test_later_revision_cannot_change_the_customer(self):
        for rows in self.histories(2):
            for factory in (list, iter):
                with self.subTest(rows=rows, factory=factory), self.assertRaises(ValueError):
                    canonical_events(factory(rows))

    def test_query_rejects_invalid_global_identity_before_customer_filtering(self):
        for revision in (1, 2):
            for rows in self.histories(revision):
                for customer in ('C1', 'C2', 'unrelated-customer'):
                    with self.subTest(revision=revision, rows=rows, customer=customer), self.assertRaises(ValueError):
                        historical_sum(iter(rows), customer, 600)

    def test_dataset_rejects_invalid_identity_even_with_no_decisions(self):
        for revision in (1, 2):
            for rows in self.histories(revision):
                with self.subTest(revision=revision, rows=rows), self.assertRaises(ValueError):
                    build_dataset(decisions=[], events=iter(rows), outcomes=[], finalized_at={})


if __name__ == '__main__':
    unittest.main()
