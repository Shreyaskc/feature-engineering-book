"""Discriminating regressions for independent identity and time expectations."""
from dataclasses import asdict, replace
import unittest
from unittest.mock import patch

import randomized_checks as checks
import parity_lab as lab


class IndependentPublicationOracleTests(unittest.TestCase):
    def setUp(self):
        self.key = lab.FeatureKey("oracle-fixed-window-v1", "immediate_then_correct", "C1", 100, 160)
        self.rows = [lab.SourceRevision("X", 1, "C1", 100, 160, 7)]
        self.expected = checks.oracle_publications([asdict(r) for r in self.rows], self.key, 160, 170)
        self.actual = lab.build_publications(lab.SourceHistory(self.rows), self.key, initial_at=160, deadline=170)

    def test_all_five_key_fields_are_compared(self):
        changes = {"feature_definition_id":"wrong-definition", "policy_id":"wrong-policy", "entity":"OTHER", "window_start":101, "window_end":161}
        for name, value in changes.items():
            with self.subTest(field=name), self.assertRaisesRegex(AssertionError, rf"case=focused.*key\.{name}"):
                checks.assert_publications([replace(self.actual[0], key=replace(self.key, **{name:value}))], self.expected, "case=focused publication_sequence")

    def test_all_five_contract_fields_are_compared(self):
        for name in checks.DECLARED_CONTRACTS:
            with self.subTest(field=name), self.assertRaisesRegex(AssertionError, rf"case=focused.*contracts\.{name}"):
                record=replace(self.actual[0], contracts=replace(self.actual[0].contracts, **{name:"wrong-version"}))
                checks.assert_publications([record], self.expected, "case=focused publication_sequence")

    def test_generated_check_rejects_hardcoded_key(self):
        original=checks.build_publications
        def mutant(*args, **kwargs):
            return tuple(replace(row,key=lab.KEY) for row in original(*args,**kwargs))
        with patch.object(checks,"build_publications",mutant), self.assertRaisesRegex(AssertionError,r"case=0.*key\.feature_definition_id"):
            checks.run_checks(cases=1)

    def test_generated_check_rejects_shifted_publication_clock(self):
        original=checks.build_publications
        def mutant(*args, **kwargs):
            return tuple(replace(row,published_at=row.published_at+1) for row in original(*args,**kwargs))
        with patch.object(checks,"build_publications",mutant), self.assertRaisesRegex(AssertionError,r"case=0.*published_at"):
            checks.run_checks(cases=1)

    def test_generated_check_rejects_contract_only_mutation(self):
        original=checks.build_publications
        def mutant(*args, **kwargs):
            return tuple(replace(row,contracts=replace(row.contracts,preprocessing_id="wrong-version")) for row in original(*args,**kwargs))
        with patch.object(checks,"build_publications",mutant), self.assertRaisesRegex(AssertionError,r"case=0.*contracts\.preprocessing_id"):
            checks.run_checks(cases=1)

    def test_expected_delivery_timing_is_independent_of_actual_clock(self):
        plan=[(1,3)]
        shifted=[checks.signature(replace(self.actual[0],published_at=161))]
        self.assertEqual(checks.delivery_times(self.expected,plan),[(163,1)])
        self.assertEqual(checks.delivery_times(shifted,plan),[(164,1)])
        self.assertIsNone(checks.oracle_store(self.expected,[(163,1)],162))
        self.assertEqual(checks.oracle_store(self.expected,[(163,1)],163),self.expected[0])

    def test_store_comparison_rejects_wrong_key(self):
        original=lab.StoreTimeline.at
        def mutant(store,minute):
            snap=original(store,minute)
            return snap if snap.record is None else replace(snap,record=replace(snap.record,key=lab.KEY))
        with patch.object(lab.StoreTimeline,"at",mutant), self.assertRaisesRegex(AssertionError,r"case=0.*store\.record\.key\.feature_definition_id"):
            checks.run_checks(cases=1)

    def test_cache_comparison_rejects_contract_mismatch(self):
        original=lab.CacheTimeline.at
        def mutant(cache,minute):
            snap=original(cache,minute)
            return snap if snap.record is None else replace(snap,record=replace(snap.record,contracts=replace(snap.record.contracts,preprocessing_id="wrong-version")))
        with patch.object(lab.CacheTimeline,"at",mutant), self.assertRaisesRegex(AssertionError,r"case=0.*cache\.record\.contracts\.preprocessing_id"):
            checks.run_checks(cases=1)

    def test_same_value_provenance_deadline_and_same_time_coalescing_survive(self):
        scenarios=[
            ([lab.SourceRevision("X",1,"C1",100,160,5),lab.SourceRevision("X",2,"C1",100,165,5),lab.SourceRevision("X",3,"C1",100,171,7)],[(160,5),(165,5)]),
            ([lab.SourceRevision("A",1,"C1",100,165,4),lab.SourceRevision("B",1,"C1",101,165,6)],[(160,0),(165,10)]),
            ([lab.SourceRevision("on",1,"C1",100,170,4),lab.SourceRevision("after",1,"C1",101,171,8)],[(160,0),(170,4)]),
        ]
        for rows,values in scenarios:
            with self.subTest(values=values):
                expected=checks.oracle_publications([asdict(r) for r in rows],self.key,160,170)
                actual=lab.build_publications(lab.SourceHistory(rows),self.key,initial_at=160,deadline=170)
                self.assertEqual([(r['published_at'],r['value']) for r in expected],values)
                checks.assert_publications(actual,expected,"case=focused publication_sequence")

    def test_expected_oracles_do_not_call_implementation_helpers(self):
        with patch.object(checks,"build_publications",side_effect=AssertionError("builder must not be used")), patch.object(lab.SourceHistory,"reference",side_effect=AssertionError("reference must not be used")), patch.object(lab.StoreTimeline,"at",side_effect=AssertionError("snapshot must not be used")), patch.object(lab.CacheTimeline,"at",side_effect=AssertionError("snapshot must not be used")):
            expected=checks.oracle_publications([asdict(r) for r in self.rows],self.key,160,170)
            self.assertEqual(expected[0]['value'],7)
            self.assertEqual(expected[0]['source_versions'],(("X",1),))
            self.assertEqual(expected[0]['key'],asdict(self.key))
            self.assertEqual(expected[0]['contracts'],checks.DECLARED_CONTRACTS)
            self.assertEqual(checks.oracle_store(expected,[(163,1)],163),expected[0])


if __name__ == '__main__':
    unittest.main()
