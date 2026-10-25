"""Typed evidence must not obtain full parity through Python equality aliases."""
from dataclasses import asdict, fields, replace
import unittest

from parity_lab import (CONTRACTS, KEY, LOG_FIELDS, CacheTimeline, Contracts,
                        SourceHistory, StoreTimeline, build_fixture, reconcile)


class MetadataContractTests(unittest.TestCase):
    def setUp(self):
        self.trace, self.logs = build_fixture()
        self.hit = self.logs[1]

    def assert_invalid(self, record, **change):
        with self.assertRaises((TypeError, ValueError)):
            replace(record, **change)

    def test_revision_aliases_cannot_claim_full_parity(self):
        for value in (True, False, 1.0, '1', 0, -1):
            with self.subTest(value=value):
                self.assert_invalid(self.hit, value_revision=value)
                self.assert_invalid(self.trace.publications[0], revision=value)

    def test_present_log_clock_metadata_requires_integer_minutes(self):
        for name, value in (('value_source_cutoff', 600.0), ('cache_capture_at', 601.0),
                            ('requested_at', 602.0)):
            for invalid in (value, True, str(int(value))):
                with self.subTest(name=name, value=invalid):
                    self.assert_invalid(self.hit, **{name: invalid})

    def test_source_version_aliases_are_rejected_in_logs_and_publications(self):
        for versions in ((('A', True), ('C', True)), (('A', 1.0),),
                         ((True, 1),), (('', 1),), (('A', 0),),
                         (('A', 1, 2),), ('A1',), (('A', 1), ('A', 2))):
            with self.subTest(versions=versions):
                self.assert_invalid(self.hit, value_source_versions=versions)
                self.assert_invalid(self.trace.publications[0], source_versions=versions)

    def test_missingness_and_fallback_flags_are_booleans(self):
        for name in ('feature_missing', 'fallback_used'):
            for value in (0, 1, 0.0, 'false'):
                with self.subTest(name=name, value=value):
                    self.assert_invalid(self.hit, **{name: value})

    def test_key_and_contract_objects_have_typed_nonempty_identities(self):
        for name in ('feature_definition_id', 'policy_id', 'entity'):
            for value in (True, 1, '', None):
                with self.subTest(name=name, value=value):
                    self.assert_invalid(KEY, **{name: value})
        for field in fields(Contracts):
            for value in (True, 1, '', None):
                with self.subTest(name=field.name, value=value):
                    self.assert_invalid(CONTRACTS, **{field.name: value})

    def test_key_contract_and_text_log_fields_reject_untyped_values(self):
        for change in ({'key': asdict(KEY)}, {'value_key': asdict(KEY)},
                       {'contracts': asdict(CONTRACTS)}, {'preprocessing_id': True},
                       {'fallback_reason': 1}, {'request_id': True}, {'request_id': ''}):
            with self.subTest(change=change):
                self.assert_invalid(self.hit, **change)
        self.assert_invalid(self.trace.publications[0], key=asdict(KEY))
        self.assert_invalid(self.trace.publications[0], contracts=asdict(CONTRACTS))

    def test_publication_and_trace_times_reject_equal_valued_floats(self):
        for name in ('published_at', 'source_cutoff'):
            self.assert_invalid(self.trace.publications[0], **{name: 600.0})
        for name in ('initial_at', 'deadline'):
            self.assert_invalid(self.trace, **{name: float(getattr(self.trace, name))})

    def test_history_known_flags_cannot_be_numeric_aliases(self):
        with self.assertRaises(TypeError):
            SourceHistory(known=1)
        self.assert_invalid(self.trace.store, known=1)
        self.assert_invalid(self.trace.cache, known=1)
        self.assert_invalid(self.trace.cache.at(602), known=1)

    def test_delivery_revision_and_capture_times_are_typed(self):
        for revision in (True, 1.0):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                StoreTimeline.from_deliveries(self.trace.publications, [(601, revision)])
        for refreshes in ([601.0], [601, 601.0], [601.0, 601]):
            with self.subTest(refreshes=refreshes), self.assertRaises(TypeError):
                CacheTimeline.from_refreshes(self.trace.store, refreshes)
        self.assert_invalid(self.trace.cache.at(602), captured_at=601.0)

    def test_none_and_absent_evidence_still_have_intended_semantics(self):
        miss = reconcile(self.trace, [self.logs[0]])['rows'][0]
        self.assertTrue(miss['comparisons']['trace_to_log'])
        for name in ('value_revision', 'value_source_cutoff', 'value_source_versions',
                     'cache_capture_at', 'key', 'value_key', 'contracts',
                     'feature_missing', 'fallback_used', 'preprocessing_id'):
            with self.subTest(name=name):
                nullable = replace(self.hit, **{name: None})
                row = reconcile(self.trace, [nullable])['rows'][0]
                self.assertIsNot(row['comparisons']['policy_full_match'], True)
                absent = replace(nullable, present_fields=LOG_FIELDS - {name})
                row = reconcile(self.trace, [absent])['rows'][0]
                self.assertIsNone(row['comparisons']['policy_full_match'])
                self.assertIn('insufficient_evidence', row['flags'])

    def test_absent_metadata_is_not_validated_as_present_evidence(self):
        absent = replace(self.hit, value_revision=True,
                         present_fields=LOG_FIELDS - {'value_revision'})
        row = reconcile(self.trace, [absent])['rows'][0]
        self.assertIsNone(row['comparisons']['policy_full_match'])
        self.assertNotIn('value_revision', row['logged'])

    def test_valid_list_and_generator_lineage_is_frozen_without_coercion(self):
        for lineage in ([['A', 1], ['C', 1]], ((event, 1) for event in ('A', 'C'))):
            with self.subTest(lineage=lineage):
                log = replace(self.hit, value_source_versions=lineage)
                self.assertEqual(log.value_source_versions, (('A', 1), ('C', 1)))
                row = reconcile(self.trace, [log])['rows'][0]
                self.assertTrue(row['comparisons']['policy_full_match'])
                self.assertTrue(row['comparisons']['trace_to_log'])
                self.assertEqual(row['flags'], [])


if __name__ == '__main__':
    unittest.main()
