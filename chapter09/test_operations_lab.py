"""Regression evidence for contracts, unsafe promotion paths, and recovery."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from parity_lab import LOG_FIELDS, build_fixture, canonical_json
import operations_lab as lab
from printed_examples import run_snippets

ROOT = Path(__file__).resolve().parent


def resign(packet):
    """Rebind test inventory to deliberately changed evidence.

    Tests use this to ensure the gate rejects bad semantics, not merely stale
    fixture hashes. Retention, access, and artifact availability stay unchanged.
    """
    required = lab.required_artifacts(packet)
    return replace(packet, inventory=tuple(replace(a, content_id=required[a.artifact_id][1])
                                          for a in packet.inventory))


class BaseTests(unittest.TestCase):
    def setUp(self):
        self.trace, self.logs = build_fixture()

    def test_chapter6_module_is_unmodified(self):
        self.assertEqual(sha256((ROOT / "parity_lab.py").read_bytes()).hexdigest(),
                         "1bd7fa504b465f1005cef7715ff7cd71a706e593fb0fa5d3308c6b30ad9a251e")

    def test_preserved_trace_values_clocks_and_keys(self):
        self.assertEqual([r.requested_at for r in self.logs], [600, 602, 606, 608, 610, 620])
        self.assertEqual([r.request_id for r in self.logs], [f"R{i}" for i in range(6)])
        self.assertEqual([r.raw_value for r in self.logs], [None, 50, 50, 50, 85, 85])
        self.assertEqual([r.model_input for r in self.logs], [0, 50, 50, 50, 85, 85])
        self.assertEqual([self.trace.policy_at(r.requested_at).value for r in self.logs], [50, 50, 45, 85, 85, 85])
        self.assertEqual([self.trace.source.reference(self.trace.key, r.requested_at).value for r in self.logs], [50, 50, 45, 85, 85, 100])
        self.assertEqual([(p.published_at, p.value) for p in self.trace.publications], [(600, 50), (605, 45), (607, 85)])
        self.assertEqual([t for t, _ in self.trace.store.accepted], [601, 606, 609])
        self.assertEqual([t for t, _ in self.trace.cache.captures], [601, 609])
        self.assertEqual((self.trace.key.window_start, self.trace.key.window_end, self.trace.deadline), (540, 600, 610))

    def test_explicit_denominators(self):
        metrics = lab.base_report()["metrics"]
        for name, numerator, denominator, excluded in (("missing", 1, 6, 0), ("fallback", 1, 6, 0),
                 ("raw_parity", 3, 5, 1), ("model_parity", 3, 6, 0), ("full_model_parity", 3, 6, 0)):
            with self.subTest(metric=name):
                self.assertEqual(metrics[name], {"numerator": numerator, "denominator": denominator,
                                                "excluded": excluded, "unknown": 0,
                                                "rate": numerator / denominator})

    def test_age_is_not_lag(self):
        rows = lab.base_report()["publication_timing"]
        self.assertEqual([r["publication_age"] for r in rows], [None, 2, 6, 8, 3, 13])
        self.assertEqual([r["publication_lag"] for r in rows], [None, 0, 5, 7, 0, 0])
        self.assertEqual(rows[0]["status"], "NO_VALUE")
        report = lab.base_report()["chapter6_report"]
        self.assertEqual(report["rows"][-1]["flags"], ["source_after_deadline"])

    def test_bad_provenance_cannot_supply_known_age(self):
        for change in ({"value_source_cutoff": 999}, {"contracts": replace(self.trace.contracts, source_schema_version="wrong")}):
            with self.subTest(change=change):
                rows = self.logs[:-1] + (replace(self.logs[-1], **change),)
                result = lab.base_report(self.trace, rows)
                self.assertEqual(result["publication_timing"][-1]["status"], "UNKNOWN")
                self.assertEqual(result["publication_timing_coverage"]["unknown"], 1)

    def test_missing_telemetry_is_not_missing_feature(self):
        logs = (replace(self.logs[0], present_fields=LOG_FIELDS - {"feature_missing", "fallback_used"}),) + self.logs[1:]
        metrics = lab.base_report(self.trace, logs)["metrics"]
        for name in ("missing", "fallback"):
            self.assertEqual(metrics[name]["numerator"], 0)
            self.assertEqual(metrics[name]["denominator"], 5)
            self.assertEqual(metrics[name]["unknown"], 1)
        self.assertEqual(metrics["full_model_parity"]["unknown"], 1)

    def test_empty_population_has_no_rate(self):
        metrics = lab.summarize((), self.trace, lab.context_for(self.trace), lab.BASELINE, ())["metrics"]
        self.assertTrue(all(m["rate"] is None and m["denominator"] == 0 for m in metrics.values()))

    def test_base_cohort_cannot_silently_shrink(self):
        for rows in ((), self.logs[1:], (replace(self.logs[0], request_id="other"),) + self.logs[1:]):
            with self.subTest(rows=len(rows)), self.assertRaisesRegex(ValueError, "all six declared"):
                lab.base_report(self.trace, rows)

    def test_reconstruction_does_not_overwrite_log(self):
        changed = (replace(self.logs[0], model_input=99),) + self.logs[1:]
        report = lab.base_report(self.trace, changed)["chapter6_report"]
        self.assertEqual(changed[0].model_input, 99)
        self.assertEqual(report["rows"][0]["logged_model_input"], 99)
        self.assertEqual(report["rows"][0]["expected_logged_model_input_from_cache"], 0)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.p = lab.build_change_packet()

    def summary(self, rows):
        return lab.summarize(rows, self.p.trace, self.p.context, lab.CANDIDATE, self.p.cohort)

    def test_same_inputs_different_consumer_contract(self):
        snapshots = self.p.trace.publications
        self.assertEqual([r.value for r in snapshots], [50, 45, 85])
        self.assertEqual(lab.consume_snapshots(snapshots, "replace"), 85)
        self.assertEqual(lab.consume_snapshots(snapshots, "add"), 180)
        self.assertEqual([r.raw_value for r in self.p.baseline_replay], [85] * 4)
        self.assertEqual([r.model_input for r in self.p.candidate_replay], [180] * 4)

    def test_snapshot_input_scope_rejects_unsupported_order_duplicates_and_mode(self):
        snaps = self.p.trace.publications
        for value, mode in (((), "replace"), (tuple(reversed(snaps)), "replace"), (snaps + (snaps[-1],), "replace"), (snaps, "mystery")):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                lab.consume_snapshots(value, mode)

    def test_implementation_digest_binds_source_payload(self):
        payload = lab.release_payload(lab.BASELINE, "replace")
        self.assertIn("def consume_snapshots", payload["consumer_python_source"])
        self.assertEqual(lab.digest(payload), self.p.baseline.code_digest)
        self.assertNotEqual(self.p.baseline.code_digest, self.p.candidate.code_digest)

    def test_candidate_mismatch_is_comparable_not_unknown(self):
        summary = self.summary(self.p.observed)
        self.assertEqual(summary["complete_comparable_requests"], 4)
        self.assertEqual(summary["metrics"]["full_model_parity"], {"numerator": 0, "denominator": 4, "excluded": 0, "unknown": 0, "rate": 0.0})
        self.assertEqual(summary["metrics"]["lineage"]["numerator"], 4)

    def test_equal_number_wrong_context_cannot_get_parity_credit(self):
        changes = {"key": replace(self.p.context.key, entity="C2"), "policy_contract_version": "v99",
                   "preprocessing_id": "double", "source_snapshot_id": "different-source", "input_snapshot_id": "different-input",
                   "source_schema_version": "source-v99", "publication_schema_version": "pub-v99",
                   "serving_log_schema_version": "log-v99", "policy_initial_at": 599, "policy_deadline": 611}
        for name, value in changes.items():
            with self.subTest(field=name):
                row = replace(self.p.observed[0], raw_value=85, model_input=85,
                              lineage=replace(self.p.observed[0].lineage, context=replace(self.p.context, **{name: value})))
                summary = self.summary((row,) + self.p.observed[1:])
                self.assertEqual(summary["metrics"]["raw_parity"]["numerator"], 0)
                self.assertEqual(summary["metrics"]["raw_parity"]["excluded"], 1)
                packet = resign(replace(self.p, observed=(row,) + self.p.observed[1:]))
                self.assertEqual(lab.decide(packet)["action"], "HOLD")

    def test_every_key_dimension_participates(self):
        for name, value in (("feature_definition_id", "other"), ("policy_id", "freeze"), ("entity", "C2"), ("window_start", 539), ("window_end", 601)):
            with self.subTest(field=name):
                key = replace(self.p.context.key, **{name: value})
                lineage = replace(self.p.observed[0].lineage, context=replace(self.p.context, key=key))
                row = replace(self.p.observed[0], raw_value=85, model_input=85, lineage=lineage)
                self.assertEqual(self.summary((row,) + self.p.observed[1:])["metrics"]["full_model_parity"]["excluded"], 1)

    def test_missing_context_fields_are_unknown(self):
        for name in self.p.context.__dataclass_fields__:
            with self.subTest(field=name):
                lineage = replace(self.p.observed[0].lineage, context=replace(self.p.context, **{name: None}))
                row = replace(self.p.observed[0], lineage=lineage)
                metric = self.summary((row,) + self.p.observed[1:])["metrics"]["model_parity"]
                self.assertEqual((metric["denominator"], metric["unknown"]), (3, 1))

    def test_missing_or_wrong_release_and_code_digest(self):
        for name, value, bucket in (("release_id", None, "unknown"), ("release_id", lab.BASELINE, "excluded"),
                                    ("implementation_digest", None, "unknown"), ("implementation_digest", "wrong", "excluded")):
            with self.subTest(field=name, value=value):
                row = replace(self.p.observed[0], lineage=replace(self.p.observed[0].lineage, **{name: value}))
                self.assertEqual(self.summary((row,) + self.p.observed[1:])["metrics"]["raw_parity"][bucket], 1)
                self.assertEqual(lab.decide(resign(replace(self.p, observed=(row,) + self.p.observed[1:])))["action"], "HOLD")

    def test_missing_value_fields_and_absent_rows_hold(self):
        for name in lab.VALUE_FIELDS:
            with self.subTest(field=name):
                row = replace(self.p.observed[0], present_fields=lab.VALUE_FIELDS - {name})
                packet = resign(replace(self.p, observed=(row,) + self.p.observed[1:]))
                report = lab.decide(packet)
                self.assertEqual(report["action"], "HOLD")
                self.assertEqual(report["observation"]["metrics"]["missing"]["unknown"], 1)
        report = lab.decide(resign(replace(self.p, observed=self.p.observed[1:])))
        self.assertEqual(report["action"], "HOLD")
        self.assertEqual(report["observation"]["metrics"]["model_parity"]["unknown"], 1)

    def test_known_missing_feature_and_unknown_raw_are_distinct(self):
        row = replace(self.p.observed[0], raw_value=None, model_input=0, feature_missing=True,
                      fallback_used=True, value_revision=None, source_cutoff=None, source_versions=None)
        metric = self.summary((row,) + self.p.observed[1:])["metrics"]
        self.assertEqual((metric["missing"]["numerator"], metric["missing"]["denominator"]), (1, 4))
        self.assertEqual((metric["raw_parity"]["excluded"], metric["raw_parity"]["unknown"]), (1, 0))
        self.assertEqual(metric["full_model_parity"]["denominator"], 4)
        hidden = replace(row, present_fields=lab.VALUE_FIELDS - {"raw_value"})
        self.assertEqual(self.summary((hidden,) + self.p.observed[1:])["metrics"]["raw_parity"]["unknown"], 1)

    def test_provenance_wrong_cutoff_or_versions_holds(self):
        for change in ({"value_revision": 99}, {"source_cutoff": 608}, {"source_versions": (("wrong", 1),)}):
            with self.subTest(change=change):
                row = replace(self.p.observed[0], **change)
                report = lab.decide(resign(replace(self.p, observed=(row,) + self.p.observed[1:])))
                self.assertEqual(report["action"], "HOLD")
                self.assertEqual(report["observation"]["metrics"]["lineage"]["excluded"], 1)

    def test_duplicate_request_and_artifact_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate request_id"):
            self.summary(self.p.observed + (self.p.observed[0],))
        with self.assertRaisesRegex(ValueError, "duplicate artifact_id"):
            lab.inspect_inventory(replace(self.p, inventory=self.p.inventory + (self.p.inventory[0],)))

    def test_time_and_request_population_cannot_drift(self):
        for change in ({"requested_at": 622}, {"request_id": "unexpected"}):
            row = replace(self.p.observed[0], **change)
            self.assertEqual(lab.decide(resign(replace(self.p, observed=(row,) + self.p.observed[1:])))["action"], "HOLD")
        shortened = replace(self.p, cohort=self.p.cohort[:3], observed=self.p.observed[:3],
                            baseline_replay=self.p.baseline_replay[:3], candidate_replay=self.p.candidate_replay[:3])
        self.assertIn("cohort_contract_mismatch", lab.decide(resign(shortened))["blockers"])

    def test_integer_value_and_flag_validation(self):
        for change in ({"raw_value": float("nan")}, {"model_input": True}, {"feature_missing": 0}, {"requested_at": False}):
            with self.subTest(change=change), self.assertRaises(TypeError):
                replace(self.p.observed[0], **change)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.p = lab.build_change_packet()

    def test_rollback_requires_complete_matched_counterexample(self):
        report = lab.decide(self.p)
        self.assertEqual((report["contract"], report["action"], report["blockers"]), ("FAIL", "ROLLBACK", []))
        self.assertEqual(report["baseline_replay"]["metrics"]["full_model_parity"]["numerator"], 4)
        self.assertEqual(report["observation"]["metrics"]["full_model_parity"]["numerator"], 0)

    def test_future_evidence_cannot_authorize_earlier_decision(self):
        for minute in (600, 620, 623):
            with self.subTest(minute=minute):
                report = lab.decide(replace(self.p, now=minute))
                self.assertEqual(report["action"], "HOLD")
                self.assertIn("future_request_evidence", report["blockers"])
        self.assertEqual(lab.decide(replace(self.p, now=624))["action"], "ROLLBACK")

    def test_missing_denied_and_expired_diagnostics_hold(self):
        for target in self.p.inventory:
            for change, status in (({"exists": False}, "MISSING"), ({"authorized_readers": ()}, "DENIED"),
                                    ({"expires_at": 625}, "EXPIRED"), ({"content_id": None}, "UNKNOWN_IDENTITY"),
                                    ({"content_id": "wrong"}, "IDENTITY_MISMATCH"), ({"owner": ""}, "UNKNOWN_METADATA"),
                                    ({"purpose": "different"}, "METADATA_MISMATCH")):
                with self.subTest(artifact=target.artifact_id, status=status):
                    inventory = tuple(replace(a, **change) if a.artifact_id == target.artifact_id else a for a in self.p.inventory)
                    report = lab.decide(replace(self.p, inventory=inventory))
                    self.assertEqual(report["action"], "HOLD")
                    self.assertEqual(report["artifact_status"][target.artifact_id], status)

    def test_artifact_presence_expiry_and_reader_types_are_explicit(self):
        for change in ({"exists": "False"}, {"exists": 1}, {"expires_at": True},
                       {"expires_at": float("nan")}, {"authorized_readers": lab.READER}):
            with self.subTest(change=change), self.assertRaises(TypeError):
                replace(self.p.inventory[0], **change)

    def test_expiry_is_exclusive_and_rechecked_at_recovery(self):
        inventory = tuple(replace(a, expires_at=626) for a in self.p.inventory)
        packet = replace(self.p, inventory=inventory)
        self.assertEqual(lab.decide(packet)["action"], "ROLLBACK")
        self.assertEqual(lab.simulate_recovery(packet)["outcome"], "HOLD")

    def test_missing_or_incompatible_retained_target_holds(self):
        for target in (None, self.p.candidate, replace(self.p.baseline, code_digest=None),
                       replace(self.p.baseline, context=replace(self.p.context, preprocessing_id="other"))):
            with self.subTest(target=target):
                report = lab.decide(replace(self.p, recovery_target=target))
                self.assertEqual(report["action"], "HOLD")
                self.assertEqual(lab.simulate_recovery(replace(self.p, recovery_target=target))["outcome"], "HOLD")

    def test_temporal_association_without_reproduction_holds(self):
        observations = tuple(replace(r, raw_value=181, model_input=181) for r in self.p.observed)
        report = lab.decide(resign(replace(self.p, observed=observations)))
        self.assertEqual(report["contract"], "FAIL")
        self.assertEqual(report["action"], "HOLD")
        self.assertIn("candidate_failure_not_reproduced", report["blockers"])

    def test_healthy_observation_contradicting_replay_cannot_continue(self):
        observations = tuple(replace(r, raw_value=85, model_input=85) for r in self.p.observed)
        report = lab.decide(resign(replace(self.p, observed=observations)))
        self.assertEqual(report["contract"], "PASS")
        self.assertEqual(report["action"], "HOLD")
        self.assertIn("observation_replay_disagreement", report["blockers"])

    def test_report_labels_cannot_substitute_for_reexecuted_results(self):
        forged = tuple(replace(r, raw_value=181, model_input=181) for r in self.p.candidate_replay)
        observed = tuple(replace(r, raw_value=181, model_input=181) for r in self.p.observed)
        report = lab.decide(resign(replace(self.p, candidate_replay=forged, observed=observed)))
        self.assertEqual(report["action"], "HOLD")
        self.assertIn("candidate_replay_not_reproducible", report["blockers"])

    def test_bad_control_and_wrong_evidence_kind_hold(self):
        baseline = tuple(replace(r, raw_value=180, model_input=180) for r in self.p.baseline_replay)
        report = lab.decide(resign(replace(self.p, baseline_replay=baseline)))
        self.assertIn("baseline_contract_not_established", report["blockers"])
        mislabeled = tuple(replace(r, kind="synthetic_observation") for r in self.p.candidate_replay)
        report = lab.decide(resign(replace(self.p, candidate_replay=mislabeled)))
        self.assertEqual(report["action"], "HOLD")
        self.assertIn("candidate_replay_evidence_kind_mismatch", report["blockers"])

    def test_recovery_runs_fresh_identical_cohort_and_rechecks_contracts(self):
        with patch.object(lab, "replay", wraps=lab.replay) as replay_call:
            report = lab.simulate_recovery(self.p)
        recovery_calls = [call for call in replay_call.call_args_list if call.kwargs.get("kind") == "recovery_check"]
        self.assertEqual(len(recovery_calls), 1)
        self.assertEqual(recovery_calls[0].args[1], self.p.cohort)
        self.assertEqual(recovery_calls[0].args[2], self.p.recovery_target)
        self.assertEqual(report["outcome"], "RECOVERED")
        self.assertEqual(report["raw_values"], [85] * 4)
        self.assertEqual(report["phase"], "fresh_post_restore_replay")
        self.assertTrue(all(r["kind"] == "recovery_check" for r in report["rows"]))
        self.assertFalse(report["external_action"])
        for name in ("missing", "fallback"):
            self.assertEqual(report["checks"]["metrics"][name]["numerator"], 0)
        for name in ("full_model_parity", "lineage"):
            self.assertEqual(report["checks"]["metrics"][name]["numerator"], 4)

    def test_recovery_failure_does_not_report_recovered(self):
        original = lab.replay
        def defective(trace, cohort, release, *, kind="controlled_replay"):
            rows = original(trace, cohort, release, kind=kind)
            return tuple(replace(r, raw_value=84, model_input=84) for r in rows) if kind == "recovery_check" else rows
        with patch.object(lab, "replay", side_effect=defective):
            self.assertEqual(lab.simulate_recovery(self.p)["outcome"], "FAIL")

    def test_reusing_healthy_control_is_not_fresh_recovery(self):
        original = lab.replay
        def stale(trace, cohort, release, *, kind="controlled_replay"):
            return self.p.baseline_replay if kind == "recovery_check" else original(trace, cohort, release, kind=kind)
        with patch.object(lab, "replay", side_effect=stale):
            self.assertEqual(lab.simulate_recovery(self.p)["outcome"], "FAIL")

    def test_recovery_cannot_precede_decision(self):
        with self.assertRaises(ValueError):
            lab.simulate_recovery(self.p, checked_at=624)

    def test_decisions_do_not_mutate_packet(self):
        before = lab._plain(self.p)
        lab.decide(self.p)
        lab.simulate_recovery(self.p)
        self.assertEqual(lab._plain(self.p), before)


class DeliverableTests(unittest.TestCase):
    def test_eight_exercise_answers(self):
        from exercise_answers import answers
        result = answers()
        self.assertEqual(len(result), 8)
        self.assertEqual(result["exercise_3"]["action"], "HOLD")
        self.assertEqual(result["exercise_3"]["model_parity"]["unknown"], 1)
        self.assertEqual(result["exercise_3"]["model_parity"]["numerator"], 3)
        self.assertEqual(result["exercise_5"]["action"], "HOLD")
        self.assertEqual(result["exercise_6"], {"contract": "FAIL", "action": "HOLD", "recovery_artifact": "EXPIRED"})
        self.assertEqual(result["exercise_7"], {"decision_at625": "ROLLBACK", "recovery_at626": "HOLD"})
        self.assertEqual(result["exercise_8"]["distinct_feature_cells"], 1)
        self.assertEqual(result, json.loads((ROOT / "expected_outputs" / "exercise_answers.json").read_text()))

    def test_serialized_evidence_matches_executable_builders(self):
        packet = lab.build_change_packet()
        fixtures = {"base_trace.json": {"trace": lab._plain(packet.trace), "observations": lab._plain(build_fixture()[1]), "synthetic": True},
                    "change_packet.json": lab._plain(packet),
                    "recovery_source_artifact.json": lab.release_payload(lab.BASELINE, "replace")}
        for name, expected in fixtures.items():
            with self.subTest(fixture=name):
                self.assertEqual(json.loads((ROOT / "fixtures" / name).read_text()), expected)

    def test_metric_counts_partition_declared_cohort(self):
        packet = lab.build_change_packet()
        for summary in (lab.decide(packet)["observation"], lab.decide(packet)["baseline_replay"],
                        lab.decide(packet)["candidate_replay"], lab.simulate_recovery(packet)["checks"]):
            for metric in summary["metrics"].values():
                self.assertEqual(metric["denominator"] + metric["excluded"] + metric["unknown"], summary["declared_requests"])
        for metric in lab.base_report()["metrics"].values():
            self.assertEqual(metric["denominator"] + metric["excluded"] + metric["unknown"], 6)

    def test_report_snapshots(self):
        for filename, actual in (("base_report.json", lab.base_report()), ("evidence_packet.json", lab.evidence_report())):
            self.assertEqual(canonical_json(actual), (ROOT / "expected_outputs" / filename).read_text(encoding="utf-8"))

    def test_all_nine_printed_listings_execute_standalone(self):
        results = run_snippets()
        self.assertEqual(len(results), 9)
        self.assertEqual(len({r["id"] for r in results}), 9)
        snippets = json.loads((ROOT / "printed_snippets.json").read_text())
        self.assertLessEqual(max(len(line) for item in snippets for line in item["code"].splitlines()), 74)


if __name__ == "__main__":
    unittest.main()
