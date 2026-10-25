"""Cross-artifact semantics must hold even when every content hash agrees."""
from dataclasses import fields, replace
import unittest
from unittest.mock import patch

import operations_lab as lab
from parity_lab import SourceHistory, build_publications


KEY_CHANGES = (
    ("entity", "C999"),
    ("feature_definition_id", "other-feature-v1"),
    ("policy_id", "other-policy"),
    ("window_start", 539),
    ("window_end", 601),
)
CONTRACT_CHANGES = (
    ("policy_contract_version", "policy-v99"),
    ("source_schema_version", "source-v99"),
    ("publication_schema_version", "publication-v99"),
    ("serving_log_schema_version", "serving-log-v99"),
    ("preprocessing_id", "double-v1"),
)


def rebind_packet(packet, trace, context=None):
    """Keep supplied 85/180 reports, but coherently rebind all declared hashes.

    This deliberately creates untrusted evidence without using replay(), so the
    action gate must independently reject it even after replay rejects its input.
    """
    context = lab.context_for(trace) if context is None else context
    baseline = lab.release_for(lab.BASELINE, "replace", context)
    candidate = lab.release_for(lab.CANDIDATE, "add", context)

    def rows_with_context(rows, release):
        return tuple(replace(row, lineage=lab.Lineage(
            context, release.release_id, release.code_digest)) for row in rows)

    changed = replace(packet, trace=trace, context=context, baseline=baseline,
                      candidate=candidate, recovery_target=baseline,
                      observed=rows_with_context(packet.observed, candidate),
                      baseline_replay=rows_with_context(packet.baseline_replay, baseline),
                      candidate_replay=rows_with_context(packet.candidate_replay, candidate))
    expected = lab.required_artifacts(changed)
    return replace(changed, inventory=tuple(
        replace(item, content_id=expected[item.artifact_id][1])
        for item in changed.inventory))


class PublicationProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.packet = lab.build_change_packet()

    def assert_no_credit(self, summary, *, excluded=4, unknown=0):
        self.assertEqual(summary["complete_comparable_requests"], 0)
        for name, metric in summary["metrics"].items():
            with self.subTest(metric=name):
                self.assertEqual(metric, {"numerator": 0, "denominator": 0,
                                          "excluded": excluded, "unknown": unknown,
                                          "rate": None})

    def assert_incompatible_packet(self, packet, reason):
        # A stale artifact fingerprint cannot be the reason this test passes.
        self.assertEqual(set(lab.inspect_inventory(packet).values()), {"AVAILABLE"})
        for release in (packet.baseline, packet.candidate):
            for kind in ("controlled_replay", "recovery_check"):
                with self.subTest(release=release.release_id, kind=kind):
                    with self.assertRaisesRegex(ValueError, reason):
                        lab.replay(packet.trace, packet.cohort, release, kind=kind)
        self.assert_no_credit(lab.summarize(
            packet.baseline_replay, packet.trace, packet.context,
            lab.BASELINE, packet.cohort))
        # decide/recovery must inspect supplied reports without trusting their
        # lineage labels or depending on an attempted invalid replay for safety.
        with patch.object(lab, "replay", side_effect=AssertionError("invalid replay")):
            decision = lab.decide(packet)
            recovery = lab.simulate_recovery(packet)
        self.assertEqual((decision["contract"], decision["action"]), ("UNKNOWN", "HOLD"))
        self.assertTrue(any(b.startswith("input_") for b in decision["blockers"]))
        for name in ("observation", "baseline_replay", "candidate_replay"):
            self.assert_no_credit(decision[name])
        self.assertEqual(recovery["outcome"], "HOLD")
        self.assertTrue(recovery["blockers"])
        self.assertNotIn("raw_values", recovery)

    def test_all_publication_keys_and_contracts_must_match_trace(self):
        trace = self.packet.trace
        for group, changes in (("key", KEY_CHANGES), ("contracts", CONTRACT_CHANGES)):
            for field, value in changes:
                # Includes all-wrong bundles and a bad older row followed by
                # two valid rows. Checking only the last publication is unsafe.
                for indices in ((0,), (1,), (2,), (0, 1, 2)):
                    with self.subTest(group=group, field=field, indices=indices):
                        publications = tuple(
                            replace(row, **{group: replace(getattr(row, group), **{field: value})})
                            if index in indices else row
                            for index, row in enumerate(trace.publications))
                        malformed = replace(trace, publications=publications)
                        packet = rebind_packet(self.packet, malformed)
                        self.assertEqual(packet.context, lab.context_for(malformed))
                        self.assert_incompatible_packet(packet, "mismatch:publication:")

    def test_trace_changes_cannot_relabel_existing_publications(self):
        trace = self.packet.trace
        for group, changes in (("key", KEY_CHANGES), ("contracts", CONTRACT_CHANGES)):
            for field, value in changes:
                with self.subTest(group=group, field=field):
                    malformed = replace(trace, **{
                        group: replace(getattr(trace, group), **{field: value})})
                    self.assert_incompatible_packet(
                        rebind_packet(self.packet, malformed), "mismatch:publication:")

    def test_release_and_report_context_cannot_relabel_compatible_trace(self):
        context = self.packet.context
        changes = [("key", replace(context.key, **{field: value}))
                   for field, value in KEY_CHANGES] + list(CONTRACT_CHANGES)
        for field, value in changes:
            with self.subTest(field=field, value=value):
                mismatched = replace(context, **{field: value})
                packet = rebind_packet(self.packet, self.packet.trace, mismatched)
                self.assert_incompatible_packet(packet, "release/input context mismatch")

    def test_future_publication_is_also_part_of_retained_bundle(self):
        trace = self.packet.trace
        future = replace(trace.publications[-1], revision=4, published_at=630,
                         key=replace(trace.key, entity="C999"))
        packet = rebind_packet(self.packet, replace(
            trace, publications=trace.publications + (future,)))
        self.assert_incompatible_packet(packet, "mismatch:publication:4:key")

    def test_missing_declared_context_stays_unknown(self):
        for field in fields(self.packet.context):
            with self.subTest(field=field.name):
                context = replace(self.packet.context, **{field.name: None})
                packet = rebind_packet(self.packet, self.packet.trace, context)
                with self.assertRaisesRegex(ValueError, "release/input context mismatch"):
                    lab.replay(packet.trace, packet.cohort, packet.baseline)
                decision = lab.decide(packet)
                self.assertEqual(decision["action"], "HOLD")
                self.assert_no_credit(decision["baseline_replay"], excluded=0, unknown=4)
                self.assertEqual(lab.simulate_recovery(packet)["outcome"], "HOLD")

    def test_missing_rows_remain_unknown_inside_incompatible_input(self):
        trace = self.packet.trace
        first = replace(trace.publications[0], contracts=replace(
            trace.contracts, preprocessing_id="double-v1"))
        packet = rebind_packet(self.packet, replace(
            trace, publications=(first,) + trace.publications[1:]))
        rows = packet.baseline_replay[1:]
        summary = lab.summarize(rows, packet.trace, packet.context,
                                lab.BASELINE, packet.cohort)
        self.assert_no_credit(summary, excluded=3, unknown=1)

    def test_valid_zero_from_known_empty_history_is_not_missing(self):
        trace = self.packet.trace
        source = SourceHistory()
        publications = build_publications(source, trace.key,
                                          initial_at=trace.initial_at,
                                          deadline=trace.deadline)
        empty_trace = replace(trace, source=source, publications=publications)
        context = lab.context_for(empty_trace)
        for release_id, mode in ((lab.BASELINE, "replace"), (lab.CANDIDATE, "add")):
            with self.subTest(release=release_id):
                release = lab.release_for(release_id, mode, context)
                rows = lab.replay(empty_trace, lab.COHORT, release)
                self.assertEqual([row.raw_value for row in rows], [0] * 4)
                self.assertTrue(all(row.source_versions == () for row in rows))
                summary = lab.summarize(rows, empty_trace, context, release_id, lab.COHORT)
                self.assertEqual(summary["complete_comparable_requests"], 4)
                for name in ("raw_parity", "model_parity", "full_model_parity", "lineage"):
                    self.assertEqual(summary["metrics"][name]["numerator"], 4)
                self.assertEqual(summary["metrics"]["missing"]["numerator"], 0)

    def test_absent_publications_cannot_supply_a_policy_or_recovery(self):
        packet = rebind_packet(self.packet, replace(self.packet.trace, publications=()))
        with self.assertRaisesRegex(ValueError, "require snapshots"):
            lab.replay(packet.trace, packet.cohort, packet.baseline)
        decision = lab.decide(packet)
        self.assertEqual(decision["action"], "HOLD")
        self.assert_no_credit(decision["baseline_replay"], excluded=0, unknown=4)
        self.assertEqual(lab.simulate_recovery(packet)["outcome"], "HOLD")


class OperationMetadataTests(unittest.TestCase):
    def setUp(self):
        self.packet = lab.build_change_packet()
        self.row = self.packet.baseline_replay[0]

    def assert_invalid(self, record, **change):
        with self.assertRaises((TypeError, ValueError)):
            replace(record, **change)

    def test_present_source_revision_aliases_cannot_enter_any_cohort(self):
        for rows in (self.packet.observed, self.packet.baseline_replay,
                     self.packet.candidate_replay):
            for alias in (True, False, 1.0, 2.0, "1", 0, -1):
                with self.subTest(kind=rows[0].kind, alias=alias):
                    self.assert_invalid(rows[0], source_versions=(("A", alias),))
            # The reviewer's exact equality-alias attack must fail at ingestion.
            self.assert_invalid(rows[0], source_versions=(
                ("A", True), ("B", True), ("C", 2.0)))

    def test_source_version_pairs_and_event_identities_are_explicit(self):
        for versions in ((("A",),), (("A", 1, 2),), ("A1",), (None,),
                         ((True, 1),), ((1, 1),), (("", 1),),
                         (("A", 1), ("A", 2)), (("A", 1), ("A", 1))):
            with self.subTest(versions=versions):
                self.assert_invalid(self.row, source_versions=versions)

    def test_present_clock_and_value_revision_aliases_are_rejected(self):
        for name in ("requested_at", "source_cutoff", "value_revision"):
            for alias in (True, False, float(getattr(self.row, name)), "1"):
                with self.subTest(field=name, alias=alias):
                    self.assert_invalid(self.row, **{name: alias})
        for invalid in (0, -1):
            self.assert_invalid(self.row, value_revision=invalid)
        for name in ("policy_initial_at", "policy_deadline"):
            for alias in (True, False, float(getattr(self.packet.context, name))):
                with self.subTest(field=name, alias=alias):
                    self.assert_invalid(self.packet.context, **{name: alias})

    def test_related_provenance_records_reject_untyped_identities(self):
        for field in fields(self.packet.context):
            if field.name not in {"key", "policy_initial_at", "policy_deadline"}:
                with self.subTest(field=field.name):
                    self.assert_invalid(self.packet.context, **{field.name: True})
        self.assert_invalid(self.packet.context, key=lab._plain(self.packet.context.key))
        self.assert_invalid(self.row, lineage=None)
        self.assert_invalid(self.row, request_id=True)
        self.assert_invalid(self.row.lineage, context={})
        self.assert_invalid(self.row.lineage, release_id=True)
        self.assert_invalid(self.row.lineage, implementation_digest=True)
        for name in ("release_id", "consumer_mode", "code_digest", "context"):
            with self.subTest(field=name):
                self.assert_invalid(self.packet.baseline, **{name: True})

    def test_declared_cohort_cannot_use_equal_valued_clock_aliases(self):
        for alias in (621.0, True, None):
            with self.subTest(alias=alias):
                cohort = (("C0", alias),) + lab.COHORT[1:]
                self.assert_invalid(self.packet, cohort=cohort)
                with self.assertRaises(TypeError):
                    lab.replay(self.packet.trace, cohort, self.packet.baseline)
                with self.assertRaises(TypeError):
                    lab.summarize(self.packet.baseline_replay, self.packet.trace,
                                  self.packet.context, lab.BASELINE, cohort)

    def test_valid_list_or_generator_source_versions_are_frozen(self):
        versions = self.row.source_versions
        for supplied in ([list(pair) for pair in reversed(versions)],
                         (list(pair) for pair in reversed(versions))):
            row = replace(self.row, source_versions=supplied)
            self.assertEqual(row.source_versions, versions)
            summary = lab.summarize((row,), self.packet.trace, self.packet.context,
                                    lab.BASELINE, self.packet.cohort[:1])
            self.assertEqual(summary["metrics"]["full_model_parity"]["numerator"], 1)

    def test_none_or_absent_value_evidence_remains_unknown(self):
        for name in ("value_revision", "source_cutoff", "source_versions"):
            for row in (replace(self.row, **{name: None}),
                        replace(self.row, **{name: True},
                                present_fields=lab.VALUE_FIELDS - {name})):
                with self.subTest(field=name, present=name in row.present_fields):
                    summary = lab.summarize((row,), self.packet.trace, self.packet.context,
                                            lab.BASELINE, self.packet.cohort[:1])
                    metric = summary["metrics"]["full_model_parity"]
                    self.assertEqual((metric["numerator"], metric["denominator"],
                                      metric["unknown"], metric["rate"]), (0, 0, 1, None))


if __name__ == "__main__":
    unittest.main()
