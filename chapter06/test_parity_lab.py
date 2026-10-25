"""Regression cases focus on semantic failures, not implementation structure."""

from dataclasses import FrozenInstanceError, asdict, replace
import json
from pathlib import Path
import unittest

from parity_lab import (CONTRACTS, KEY, LOG_FIELDS, CacheTimeline, FeatureKey,
                        SourceHistory, SourceRevision, StoreTimeline, Trace,
                        build_fixture, build_publications, log_request,
                        numeric_equal, reconcile)
from printed_examples import LISTINGS, run_listings


class SourceAndPolicyTests(unittest.TestCase):
    def setUp(self):
        self.trace, self.logs = build_fixture()

    def test_reference_cutoff_boundaries(self):
        expected = {550: 0, 551: 20, 585: 20, 586: 50, 600: 50,
                    604: 50, 605: 45, 606: 45, 607: 85, 610: 85, 611: 85, 612: 100}
        for cutoff, value in expected.items():
            with self.subTest(cutoff=cutoff):
                self.assertEqual(self.trace.source.reference(KEY, cutoff).value, value)

    def test_publications_retain_chapter5_contract(self):
        self.assertEqual(KEY.feature_definition_id, "known_spend_fixed_window_v1")
        self.assertEqual(KEY.policy_id, "immediate_then_correct")
        self.assertEqual([(p.revision, p.published_at, p.source_cutoff, p.value)
                          for p in self.trace.publications],
                         [(1, 600, 600, 50), (2, 605, 605, 45), (3, 607, 607, 85)])
        self.assertEqual(self.trace.publications[-1].source_versions, (("A", 1), ("B", 1), ("C", 2)))

    def test_half_open_window_and_other_entity(self):
        source = SourceHistory([SourceRevision("left", 1, "C1", 540, 600, 3),
                                SourceRevision("before", 1, "C1", 539, 600, 100),
                                SourceRevision("right", 1, "C1", 600, 600, 100),
                                SourceRevision("other", 1, "C2", 550, 600, 100)])
        self.assertEqual(source.reference(KEY, 600).value, 3)

    def test_latest_eligible_revision_not_latest_arrival(self):
        history = SourceHistory([SourceRevision("X", 1, "C1", 550, 605, 999),
                                 SourceRevision("X", 2, "C1", 550, 600, 7)])
        self.assertEqual(history.reference(KEY, 610).value, 7)

    def test_reordered_source_and_exact_retries_are_idempotent(self):
        rows = self.trace.source.revisions
        reordered = SourceHistory(tuple(reversed(rows)) + (rows[0], rows[0]))
        self.assertEqual(reordered, self.trace.source)

    def test_conflicting_revision_is_rejected(self):
        row = self.trace.source.revisions[0]
        for change in ({"amount": row.amount + 1}, {"available_at": row.available_at + 1}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "conflicting"):
                SourceHistory([row, replace(row, **change)])

    def test_event_identity_entity_and_time_are_stable(self):
        row = self.trace.source.revisions[0]
        for change in ({"entity": "C2"}, {"event_time": 549}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "unstable"):
                SourceHistory([row, replace(row, revision=2, **change)])

    def test_source_clock_amount_and_version_validation(self):
        for change in ({"available_at": 549}, {"amount": -1}, {"amount": 1.0},
                       {"amount": True}, {"revision": 0}, {"revision": True}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(self.trace.source.revisions[0], **change)

    def test_deadline_inclusive_and_later_source_retained_for_reconciliation(self):
        history = SourceHistory([SourceRevision("on", 1, "C1", 550, 610, 4),
                                 SourceRevision("after", 1, "C1", 551, 611, 8)])
        publications = build_publications(history, KEY, initial_at=600, deadline=610)
        self.assertEqual([(p.published_at, p.value) for p in publications], [(600, 0), (610, 4)])
        self.assertEqual(history.reference(KEY, 611).value, 12)

    def test_outside_window_does_not_publish(self):
        self.assertNotIn(603, [p.published_at for p in self.trace.publications])
        self.assertNotIn(("D", 1), self.trace.publications[-1].source_versions)

    def test_same_value_new_revision_still_publishes(self):
        history = SourceHistory([SourceRevision("X", 1, "C1", 550, 600, 5),
                                 SourceRevision("X", 2, "C1", 550, 605, 5)])
        publications = build_publications(history, KEY, initial_at=600, deadline=610)
        self.assertEqual([p.value for p in publications], [5, 5])
        self.assertEqual([p.source_versions for p in publications], [(("X", 1),), (("X", 2),)])

    def test_full_source_snapshot_at_same_minute(self):
        history = SourceHistory([SourceRevision("A", 1, "C1", 550, 600, 4),
                                 SourceRevision("B", 1, "C1", 551, 600, 6)])
        publications = build_publications(history, KEY, initial_at=600, deadline=610)
        self.assertEqual(len(publications), 1)
        self.assertEqual(publications[0].value, 10)

    def test_publication_clock_contract(self):
        for initial, deadline in ((599, 610), (611, 610)):
            with self.subTest(initial=initial), self.assertRaisesRegex(ValueError, "window_end"):
                build_publications(self.trace.source, KEY, initial_at=initial, deadline=deadline)

    def test_unknown_history_is_not_known_empty(self):
        self.assertEqual(SourceHistory().reference(KEY, 600).value, 0)
        unknown = SourceHistory(known=False).reference(KEY, 600)
        self.assertIsNone(unknown.value)
        self.assertFalse(unknown.history_known)
        with self.assertRaisesRegex(ValueError, "unknown"):
            build_publications(SourceHistory(known=False), KEY, initial_at=600, deadline=610)

    def test_policy_lookup_independent_of_input_order(self):
        reordered = replace(self.trace, publications=tuple(reversed(self.trace.publications)))
        self.assertEqual(reordered.policy_at(620).revision, 3)


class ServingAndReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.trace, self.logs = build_fixture()

    def row(self, log):
        return reconcile(self.trace, [log])["rows"][0]

    def test_visibility_before_cache_and_request_at_same_minute(self):
        store = StoreTimeline.from_deliveries(self.trace.publications, [(600, 1), (605, 2), (607, 3)])
        cache = CacheTimeline.from_refreshes(store, [600, 605, 607])
        self.assertEqual(log_request("same-time", 607, KEY, cache).model_input, 85)

    def test_cache_captures_are_frozen_between_refreshes(self):
        self.assertEqual(self.trace.cache.at(608).record.revision, 1)
        self.assertEqual(self.trace.cache.at(608).captured_at, 601)
        self.assertEqual(self.trace.store.at(608).record.revision, 2)
        self.assertEqual(self.trace.cache.at(609).record.revision, 3)

    def test_sink_never_rolls_back_after_reordered_retries(self):
        store = StoreTimeline.from_deliveries(self.trace.publications, [(609, 3), (610, 1), (611, 2), (612, 3)])
        self.assertEqual([(at, p.revision) for at, p in store.accepted], [(609, 3)])
        self.assertEqual(store.at(620).record.revision, 3)

    def test_sink_rejects_impossible_delivery_or_mixed_key(self):
        with self.assertRaisesRegex(ValueError, "before"):
            StoreTimeline.from_deliveries(self.trace.publications, [(599, 1)])
        with self.assertRaisesRegex(ValueError, "unknown"):
            StoreTimeline.from_deliveries(self.trace.publications, [(620, 99)])
        wrong = replace(self.trace.publications[1], key=replace(KEY, entity="other"))
        with self.assertRaisesRegex(ValueError, "one full key"):
            StoreTimeline.from_deliveries([self.trace.publications[0], wrong], [])

    def test_missing_cell_is_explicit_fallback_not_observed_zero(self):
        miss = self.logs[0]
        self.assertIsNone(miss.raw_value)
        self.assertTrue(miss.feature_missing)
        self.assertTrue(miss.fallback_used)
        self.assertEqual((miss.fallback_reason, miss.fallback_value, miss.model_input), ("cache_miss", 0, 0))
        row = self.row(miss)
        self.assertIsNone(row["comparisons"]["raw_policy_numeric_match"])
        self.assertIsNone(row["comparisons"]["trace_numeric_match"])
        self.assertTrue(row["comparisons"]["trace_to_log"])
        self.assertEqual(row["model_delta_from_policy"], -50)

    def test_known_empty_history_can_serve_observed_zero(self):
        source = SourceHistory()
        pubs = build_publications(source, KEY, initial_at=600, deadline=610)
        store = StoreTimeline.from_deliveries(pubs, [(600, 1)])
        cache = CacheTimeline.from_refreshes(store, [600])
        trace = Trace(KEY, source, 600, 610, pubs, store, cache)
        log = log_request("zero", 600, KEY, cache)
        self.assertEqual(log.raw_value, 0)
        self.assertFalse(log.feature_missing)
        self.assertFalse(log.fallback_used)
        self.assertTrue(reconcile(trace, [log])["rows"][0]["comparisons"]["policy_full_match"])

    def test_both_lag_causes_can_coexist(self):
        row = self.row(self.logs[3])
        self.assertEqual(row["flags"], ["materialization_lag", "cache_lag", "numeric_mismatch"])
        self.assertEqual((row["expected_policy"]["value"], row["expected_store"]["record"]["value"],
                          row["expected_cache"]["record"]["value"]), (85, 45, 50))

    def test_late_source_is_policy_consistent_and_source_mismatched(self):
        row = self.row(self.logs[5])
        self.assertEqual(row["flags"], ["source_after_deadline"])
        self.assertTrue(row["comparisons"]["policy_full_match"])
        self.assertFalse(row["comparisons"]["raw_source_numeric_match"])
        self.assertEqual(row["expected_source"]["value"], 100)
        self.assertEqual(row["expected_policy"]["value"], 85)

    def test_optional_late_source_does_not_change_policy(self):
        trace, logs = build_fixture(include_late=False)
        self.assertEqual(trace.publications, self.trace.publications)
        self.assertEqual(self.row(self.logs[5])["logged_model_input"], logs[5].model_input)
        self.assertEqual(reconcile(trace, logs)["rows"][5]["flags"], [])

    def test_same_value_wrong_revision_is_not_provenance_parity(self):
        row = self.row(replace(self.logs[4], value_revision=1))
        self.assertTrue(row["comparisons"]["policy_numeric_match"])
        self.assertFalse(row["comparisons"]["trace_provenance_match"])
        self.assertFalse(row["comparisons"]["policy_full_match"])
        self.assertIn("provenance_mismatch", row["flags"])
        self.assertNotIn("numeric_mismatch", row["flags"])
        self.assertEqual(row["logged"]["value_revision"], 1)

    def test_wrong_rolling_window_is_not_the_requested_feature(self):
        rolling_key = replace(KEY, window_start=550, window_end=610)
        rolling_value = self.trace.source.reference(rolling_key, 610).value
        self.assertEqual(rolling_value, 95)
        row = self.row(replace(self.logs[4], value_key=rolling_key,
                               raw_value=rolling_value, model_input=rolling_value))
        self.assertIn("definition_or_key_mismatch", row["flags"])
        self.assertIsNone(row["comparisons"]["policy_numeric_match"])
        self.assertIsNone(row["comparisons"]["raw_policy_numeric_match"])
        self.assertEqual(row["model_delta_from_policy"], 10)

    def test_every_key_dimension_matters_even_if_value_matches(self):
        for change in ({"feature_definition_id": "v2"}, {"policy_id": "freeze"}, {"entity": "C2"},
                       {"window_start": 539}, {"window_end": 601}):
            with self.subTest(change=change):
                row = self.row(replace(self.logs[4], value_key=replace(KEY, **change)))
                self.assertIn("definition_or_key_mismatch", row["flags"])
                self.assertIsNone(row["comparisons"]["policy_numeric_match"])

    def test_missing_key_or_contract_excludes_semantic_numeric_metrics(self):
        for field in ("key", "value_key", "contracts"):
            with self.subTest(field=field):
                row = self.row(replace(self.logs[4], present_fields=LOG_FIELDS - {field}))
                self.assertIsNone(row["comparisons"]["policy_numeric_match"])
                self.assertIsNone(row["comparisons"]["raw_policy_numeric_match"])
                self.assertIn("insufficient_evidence", row["flags"])
                self.assertNotIn(field, row["logged"])

    def test_contradictory_missingness_cannot_improve_numeric_parity(self):
        contradictory = replace(self.logs[1], feature_missing=True, value_key=None)
        row = self.row(contradictory)
        self.assertFalse(row["semantic_key_verified"])
        self.assertIsNone(row["comparisons"]["policy_numeric_match"])
        self.assertIsNone(row["comparisons"]["raw_policy_numeric_match"])
        self.assertIn("provenance_mismatch", row["flags"])

    def test_cache_miss_cannot_have_value_provenance(self):
        row = self.row(replace(self.logs[0], value_key=KEY))
        self.assertFalse(row["comparisons"]["trace_to_log"])
        self.assertIn("provenance_mismatch", row["flags"])

    def test_missing_revision_is_unverifiable_even_when_number_matches(self):
        log = replace(self.logs[4], present_fields=LOG_FIELDS - {"value_revision"})
        row = self.row(log)
        self.assertTrue(row["comparisons"]["policy_numeric_match"])
        self.assertIsNone(row["comparisons"]["policy_full_match"])
        self.assertIsNone(row["comparisons"]["trace_provenance_match"])
        self.assertIn("insufficient_evidence", row["flags"])

    def test_unknown_store_cannot_be_diagnosed_as_materialization_lag(self):
        trace = replace(self.trace, store=replace(self.trace.store, known=False))
        row = reconcile(trace, [self.logs[3]])["rows"][0]
        self.assertIn("insufficient_evidence", row["flags"])
        self.assertNotIn("materialization_lag", row["flags"])
        self.assertNotIn("store_missing", row["flags"])
        self.assertIsNone(row["comparisons"]["policy_to_store"])

    def test_preprocessing_disagreement_is_separate(self):
        row = self.row(replace(self.logs[4], model_input=170))
        self.assertIn("preprocessing_mismatch", row["flags"])
        self.assertIn("numeric_mismatch", row["flags"])
        self.assertTrue(row["comparisons"]["trace_provenance_match"])
        unknown_transform = self.row(replace(self.logs[4], preprocessing_id="double-v1"))
        self.assertIsNone(unknown_transform["comparisons"]["policy_numeric_match"])
        self.assertIn("preprocessing_mismatch", unknown_transform["flags"])

    def test_numeric_difference_alone_is_not_a_lag_diagnosis(self):
        row = self.row(replace(self.logs[4], raw_value=84, model_input=84))
        self.assertIn("numeric_mismatch", row["flags"])
        self.assertNotIn("cache_lag", row["flags"])
        self.assertNotIn("materialization_lag", row["flags"])

    def test_request_replays_cannot_inflate_denominators(self):
        for duplicate in (self.logs[4], replace(self.logs[4], model_input=170)):
            with self.subTest(duplicate=duplicate.model_input), self.assertRaisesRegex(ValueError, "duplicate request_id"):
                reconcile(self.trace, [self.logs[4], duplicate])

    def test_reconciliation_preserves_logs_and_defensively_freezes_collections(self):
        before = tuple(asdict(log) for log in self.logs)
        reconcile(self.trace, self.logs)
        self.assertEqual(before, tuple(asdict(log) for log in self.logs))
        mutable_presence = set(LOG_FIELDS)
        mutable_lineage = [["A", 1]]
        log = replace(self.logs[4], present_fields=mutable_presence, value_source_versions=mutable_lineage)
        mutable_presence.clear()
        mutable_lineage[0][1] = 99
        self.assertEqual(log.present_fields, LOG_FIELDS)
        self.assertEqual(log.value_source_versions, (("A", 1),))
        with self.assertRaises(FrozenInstanceError):
            log.model_input = 0

    def test_report_denominators_and_expected_json(self):
        report = reconcile(self.trace, self.logs)
        self.assertEqual(report["metrics"]["policy_numeric"], {"matches": 3, "evaluable": 6, "excluded": 0})
        self.assertEqual(report["metrics"]["raw_policy_numeric"], {"matches": 3, "evaluable": 5, "excluded": 1})
        self.assertEqual(report["metrics"]["trace_logging"], {"matches": 6, "evaluable": 6, "excluded": 0})
        self.assertEqual(report["metrics"]["raw_source_numeric"], {"matches": 2, "evaluable": 5, "excluded": 1})
        expected = json.loads((Path(__file__).parent / "expected_outputs" / "parity_report.json").read_text())
        self.assertEqual(json.loads(json.dumps(report)), expected)


class NumericAndPrintedTests(unittest.TestCase):
    def test_exact_integer_missing_and_explicit_float_rules(self):
        self.assertTrue(numeric_equal(85, 85))
        self.assertFalse(numeric_equal(84, 85))
        self.assertFalse(numeric_equal(None, None))
        self.assertFalse(numeric_equal(None, 0))
        self.assertFalse(numeric_equal(0.1 + 0.2, 0.3))
        self.assertTrue(numeric_equal(0.1 + 0.2, 0.3, rel_tol=1e-9, abs_tol=1e-12))
        self.assertTrue(numeric_equal(0.0, 5e-13, rel_tol=1e-9, abs_tol=1e-12))
        self.assertFalse(numeric_equal(0.0, 2e-12, rel_tol=1e-9, abs_tol=1e-12))

    def test_nonfinite_values_never_pass_comparison_or_logging(self):
        _, logs = build_fixture()
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    numeric_equal(value, value)
                with self.assertRaises(ValueError):
                    replace(logs[4], model_input=value)
        with self.assertRaises(TypeError):
            numeric_equal(True, 1)
        with self.assertRaises(ValueError):
            numeric_equal(1, 1, rel_tol=-1)

    def test_all_seven_printed_listings_execute_verbatim(self):
        self.assertEqual(len(LISTINGS), 7)
        self.assertTrue(all(len(listing.splitlines()) <= 12 for listing in LISTINGS))
        expected = json.loads((Path(__file__).parent / "expected_outputs" / "printed_examples.json").read_text())
        self.assertEqual(json.loads(json.dumps(run_listings())), expected)


if __name__ == "__main__":
    unittest.main()
