"""Contract, disk lifecycle, corruption and release-registry tests."""
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

import backfill_lab as lab
from foundations_lab import ContractError, Delivery, Ledger, Revision


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.specs = lab.fixture_specs()

    def test_hand_checked_vectors(self):
        self.assertEqual({name: lab.values(spec) for name, spec in self.specs.items()}, {
            "baseline": [50, 95, 0], "extended_historical": [50, 95, 0],
            "corrected": [102, 112, 0], "new_definition": [30, 35, 0]})

    def test_baseline_not_rewritten(self):
        base = lab.source_from_fixture()
        extended = lab.source_from_fixture("chapter7_extension")
        self.assertEqual(len(base.history), 5)
        self.assertEqual(len(extended.history), 7)
        self.assertTrue(set(base.history).issubset(set(extended.history)))
        self.assertEqual([(r.event_id, r.revision, r.event_time, r.available_at, r.amount)
                          for r in extended.history if r not in base.history],
                         [("B", 2, 575, 630, 42), ("E", 1, 595, 612, 15)])

    def test_chapter6_late_E_continuity_and_B_correction(self):
        source = self.specs["corrected"].source
        at620 = lab.make_spec(source, definition=lab.Definition(mode="corrected", corrected_cutoff=620))
        at640 = self.specs["corrected"]
        self.assertEqual(lab.values(at620), [100, 110, 0])
        self.assertEqual(lab.values(at640), [102, 112, 0])
        self.assertEqual([(r.window_start, r.window_end) for r in lab.materialize(at640)],
                         [(540, 600), (550, 610), (550, 610)])

    def test_equal_values_do_not_imply_equal_identity(self):
        a, b = self.specs["baseline"], self.specs["extended_historical"]
        self.assertEqual(lab.values(a), lab.values(b))
        self.assertNotEqual(a.dataset_id, b.dataset_id)

    def test_input_permutations_canonicalize(self):
        spec = self.specs["baseline"]
        shuffled = lab.make_spec(lab.SourceSnapshot(tuple(reversed(spec.source.history))),
                                 decisions=tuple(reversed(spec.decisions)),
                                 coverage=tuple(reversed(spec.coverage)))
        self.assertEqual(spec.to_dict(), shuffled.to_dict())
        self.assertEqual(spec.dataset_id, shuffled.dataset_id)

    def test_duplicate_decision_ids_reject_even_equal(self):
        spec = self.specs["baseline"]
        for duplicate in (spec.decisions[0], replace(spec.decisions[0], decision_at=601)):
            with self.assertRaises(ContractError):
                replace(spec, decisions=spec.decisions + (duplicate,))

    def test_duplicate_source_versions_reject_even_equal(self):
        source = self.specs["baseline"].source
        for duplicate in (source.history[0], replace(source.history[0], amount=999)):
            with self.assertRaises(ContractError):
                lab.SourceSnapshot(source.history + (duplicate,))

    def test_source_identity_conflicts_reject(self):
        row = self.specs["baseline"].source.history[0]
        for changed in (replace(row, revision=2, customer_id="OTHER"),
                        replace(row, revision=2, event_time=549),
                        replace(row, revision=2, available_at=550)):
            with self.assertRaises(ContractError):
                lab.SourceSnapshot((row, changed))

    def test_canonical_transport_retries_and_conflicts(self):
        row = self.specs["baseline"].source.history[0]
        first = Delivery("transport", row, 551)
        self.assertEqual(len(Ledger((first, first)).history), 1)
        with self.assertRaises(ContractError):
            Ledger((first, Delivery("transport", row, 552)))
        with self.assertRaises(ContractError):
            Ledger((first, Delivery("retry", replace(row, amount=21), 552)))

    def test_known_empty_and_unknown_are_distinct(self):
        spec = self.specs["baseline"]
        unknown = replace(spec, coverage=(spec.coverage[0],
                          replace(spec.coverage[1], history_known=False)))
        self.assertEqual(lab.values(spec), [50, 95, 0])
        self.assertEqual(lab.values(unknown), [50, 95, None])
        self.assertNotEqual(spec.dataset_id, unknown.dataset_id)

    def test_unknown_nonempty_history_keeps_observed_contributors(self):
        spec = self.specs["baseline"]
        unknown = replace(spec, coverage=(replace(spec.coverage[0], history_known=False),
                                          spec.coverage[1]))
        self.assertEqual(lab.values(unknown), [None, None, 0])
        original = lab.materialize(spec)
        revised = lab.materialize(unknown)
        self.assertTrue(revised[0].contributors)
        self.assertEqual([row.contributors for row in original],
                         [row.contributors for row in revised])

    def test_missing_insufficient_and_duplicate_coverage_reject(self):
        spec = self.specs["baseline"]
        bad = [spec.coverage[:1], spec.coverage + (spec.coverage[0],),
               (replace(spec.coverage[0], event_start=541), spec.coverage[1]),
               (replace(spec.coverage[0], available_through=609), spec.coverage[1])]
        for coverage in bad:
            with self.subTest(coverage=coverage), self.assertRaises(ContractError):
                replace(spec, coverage=coverage)

    def test_boolean_is_not_integer(self):
        for build in (lambda: lab.Decision("D", "C", True),
                      lambda: lab.Definition(window_minutes=True),
                      lambda: lab.Coverage("C", 0, 10, 10, history_known=1)):
            with self.assertRaises(ContractError):
                build()

    def test_invalid_definition_rejects(self):
        for kwargs in ({"mode": "future"}, {"corrected_cutoff": 640},
                       {"mode": "corrected"}, {"window_minutes": 0}):
            with self.assertRaises(ContractError):
                lab.Definition(**kwargs)
        with self.assertRaises(ContractError):
            lab.make_spec(definition=lab.Definition(mode="corrected", corrected_cutoff=600))

    def test_all_required_identity_inputs_participate(self):
        spec = self.specs["baseline"]
        variants = [self.specs["extended_historical"], self.specs["new_definition"],
                    replace(spec, decisions=(replace(spec.decisions[0], decision_at=601),) + spec.decisions[1:]),
                    replace(spec, coverage=(replace(spec.coverage[0], event_end=650), spec.coverage[1])),
                    replace(spec, code=(("backfill_lab.py", "0" * 64), spec.code[1])),
                    replace(spec, runtime="CPython 3.12.other")]
        self.assertEqual(len({spec.dataset_id, *(x.dataset_id for x in variants)}), 7)

    def test_frozen_records_and_defensive_manifest(self):
        spec = self.specs["baseline"]
        dataset = lab.Dataset(spec, list(lab.materialize(spec)))
        with self.assertRaises(FrozenInstanceError):
            dataset.records[0].value = 1
        self.assertIsInstance(dataset.records, tuple)
        manifest = dataset.manifest
        manifest["spec"]["decisions"].clear()
        self.assertEqual(len(dataset.manifest["spec"]["decisions"]), 3)

    def test_duplicate_json_fields_reject(self):
        with self.assertRaises(ContractError):
            lab.decode(b'{"source": [], "source": []}')

    def test_spec_json_roundtrip_and_extra_field_rejection(self):
        spec = self.specs["baseline"]
        self.assertEqual(lab.spec_from_dict(lab.decode(lab.canonical(spec.to_dict()))), spec)
        bad = spec.to_dict()
        bad["unexpected"] = 1
        with self.assertRaises(ContractError):
            lab.spec_from_dict(bad)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.store = Path(self.temporary.name)
        self.specs = lab.fixture_specs()
        self.spec = self.specs["baseline"]

    def tearDown(self):
        self.temporary.cleanup()

    def publish(self, name="baseline", attempt=None):
        spec = self.specs[name]
        lab.stage_build(self.store, attempt or name, spec)
        return lab.publish_dataset(self.store, attempt or name, spec)

    def test_stop_resume_and_idempotent_replay(self):
        stopped = lab.stage_build(self.store, "attempt", self.spec, stop_after_chunks=1)
        self.assertEqual((stopped.next_index, stopped.complete), (1, False))
        self.assertFalse((self.store / "datasets").exists())
        with self.assertRaises(ContractError):
            lab.publish_dataset(self.store, "attempt", self.spec)
        resumed = lab.stage_build(self.store, "attempt", self.spec)
        self.assertEqual((resumed.next_index, resumed.complete), (3, True))
        before = {p.name: p.read_bytes() for p in (self.store / "staging" / "attempt").iterdir()}
        lab.stage_build(self.store, "attempt", self.spec)
        after = {p.name: p.read_bytes() for p in (self.store / "staging" / "attempt").iterdir()}
        self.assertEqual(before, after)
        self.assertEqual(len(lab.publish_dataset(self.store, "attempt", self.spec).records), 3)

    def test_resume_from_a_fresh_python_process(self):
        code = ("from pathlib import Path; import sys; from backfill_lab import *; "
                "store=Path(sys.argv[1]); spec=make_spec(); "
                "stage_build(store,'restart',spec,stop_after_chunks=int(sys.argv[2]))")
        for count in (1, 10):
            subprocess.run([sys.executable, "-c", code, str(self.store), str(count)],
                           cwd=lab.ROOT, check=True, capture_output=True, text=True)
        dataset = lab.publish_dataset(self.store, "restart", self.spec)
        self.assertEqual([r.value for r in dataset.records], [50, 95, 0])

    def test_chunk_size_and_attempt_do_not_change_semantic_identity(self):
        paths = []
        for size in (1, 2, 10):
            other = self.store / str(size)
            lab.stage_build(other, f"attempt{size}", self.spec, chunk_size=size)
            dataset = lab.publish_dataset(other, f"attempt{size}", self.spec, chunk_size=size)
            paths.append(lab.dataset_path(other, dataset.dataset_id).read_bytes())
        self.assertEqual(paths, [paths[0]] * 3)

    def test_changed_resume_inputs_reject(self):
        lab.stage_build(self.store, "same", self.spec, stop_after_chunks=1)
        variants = [self.specs["extended_historical"], self.specs["new_definition"],
                    replace(self.spec, decisions=(replace(self.spec.decisions[0], decision_at=601),) + self.spec.decisions[1:]),
                    replace(self.spec, coverage=(replace(self.spec.coverage[0], event_end=650), self.spec.coverage[1])),
                    replace(self.spec, code=(("backfill_lab.py", "0" * 64), self.spec.code[1])),
                    replace(self.spec, runtime="CPython 3.12.other")]
        for variant in variants:
            with self.subTest(identity=variant.dataset_id), self.assertRaises(ContractError):
                lab.stage_build(self.store, "same", variant)
        with self.assertRaises(ContractError):
            lab.stage_build(self.store, "same", self.spec, chunk_size=2)

    def test_chunk_corruption_and_resealed_corruption_reject(self):
        lab.stage_build(self.store, "same", self.spec, stop_after_chunks=1)
        folder = self.store / "staging" / "same"
        path = folder / "chunk_000000.json"
        rows = lab.decode(path.read_bytes())
        rows[0]["value"] = 999
        path.write_bytes(lab.canonical(rows))
        with self.assertRaises(ContractError):
            lab.stage_build(self.store, "same", self.spec)
        checkpoint = lab.decode((folder / "checkpoint.json").read_bytes())
        checkpoint["chunks"][0]["sha256"] = lab.digest(path.read_bytes())
        lab._save_checkpoint(folder, checkpoint)
        with self.assertRaises(ContractError):
            lab.stage_build(self.store, "same", self.spec)

    def test_checkpoint_digest_and_counter_corruption_reject(self):
        lab.stage_build(self.store, "same", self.spec, stop_after_chunks=1)
        folder = self.store / "staging" / "same"
        checkpoint = lab.decode((folder / "checkpoint.json").read_bytes())
        checkpoint["next_index"] = 2
        (folder / "checkpoint.json").write_bytes(lab.canonical(checkpoint))
        with self.assertRaises(ContractError):
            lab.stage_build(self.store, "same", self.spec)
        lab._save_checkpoint(folder, checkpoint)
        with self.assertRaises(ContractError):
            lab.stage_build(self.store, "same", self.spec)

    def test_missing_digest_and_orphan_chunk_reject(self):
        lab.stage_build(self.store, "same", self.spec, stop_after_chunks=1)
        folder = self.store / "staging" / "same"
        original = (folder / "checkpoint.sha256").read_bytes()
        (folder / "checkpoint.sha256").unlink()
        with self.assertRaises(ContractError):
            lab.stage_build(self.store, "same", self.spec)
        (folder / "checkpoint.sha256").write_bytes(original)
        (folder / "chunk_000001.json").write_bytes(b"[]\n")
        with self.assertRaises(ContractError):
            lab.stage_build(self.store, "same", self.spec)

    def test_noncanonical_staged_bytes_reject(self):
        lab.stage_build(self.store, "same", self.spec, stop_after_chunks=1)
        path = self.store / "staging" / "same" / "spec.json"
        path.write_bytes(b" " + path.read_bytes())
        with self.assertRaises(ContractError):
            lab.stage_build(self.store, "same", self.spec)

    def test_checkpoint_boolean_substitution_reject(self):
        lab.stage_build(self.store, "same", self.spec, stop_after_chunks=1)
        folder = self.store / "staging" / "same"
        checkpoint = lab.decode((folder / "checkpoint.json").read_bytes())
        checkpoint["next_index"] = True
        lab._save_checkpoint(folder, checkpoint)
        with self.assertRaises(ContractError):
            lab.stage_build(self.store, "same", self.spec)

    def test_dataset_validation_recomputes_after_hashes_are_resealed(self):
        dataset = self.publish()
        for field, replacement in (("value", 999), ("decision_id", "other"),
                                   ("contributors", [["B", 1]]),
                                   ("source_sha256", "0" * 64)):
            value = dataset.to_dict()
            value["records"][0][field] = replacement
            value["manifest"]["records_sha256"] = lab.digest(lab.canonical(value["records"]))
            value["manifest_sha256"] = lab.digest(lab.canonical(value["manifest"]))
            with self.subTest(field=field), self.assertRaises(ContractError):
                lab.validate_dataset(value)

    def test_duplicate_missing_and_reordered_dataset_rows_reject(self):
        dataset = self.publish()
        records = dataset.to_dict()["records"]
        for changed in (records[:-1], records + [records[0]], list(reversed(records))):
            value = dataset.to_dict()
            value["records"] = changed
            with self.assertRaises(ContractError):
                lab.validate_dataset(value)

    def test_immutable_dataset_publication(self):
        dataset = self.publish()
        path = lab.dataset_path(self.store, dataset.dataset_id)
        original = path.read_bytes()
        self.publish()
        self.assertEqual(path.read_bytes(), original)
        path.write_bytes(b"corrupt\n")
        with self.assertRaises(ContractError):
            self.publish()
        self.assertEqual(path.read_bytes(), b"corrupt\n")

    def test_corruption_rejects_before_pointer_change(self):
        baseline = self.publish()
        candidate = self.publish("extended_historical")
        registry = lab.ReleaseRegistry(self.store)
        token = registry.promote("historical", baseline.dataset_id, expected_current=lab.ReleaseToken())
        previous = registry.path.read_bytes()
        value = candidate.to_dict()
        value["records"][0]["value"] = 999
        lab.dataset_path(self.store, candidate.dataset_id).write_bytes(lab.canonical(value))
        with self.assertRaises(ContractError):
            registry.promote("historical", candidate.dataset_id, expected_current=token)
        self.assertEqual(registry.path.read_bytes(), previous)

    def test_corrected_and_wrong_window_cannot_enter_historical_channel(self):
        registry = lab.ReleaseRegistry(self.store)
        for name in ("corrected", "new_definition"):
            candidate = self.publish(name)
            with self.assertRaises(ContractError):
                registry.promote("historical", candidate.dataset_id, expected_current=lab.ReleaseToken())
        self.assertFalse(registry.path.exists())
        token = registry.promote("historical_30m", self.specs["new_definition"].dataset_id,
                                 expected_current=lab.ReleaseToken())
        self.assertEqual(token.generation, 1)

    def test_rollback_retains_experiment_and_blocks_stale_aba_token(self):
        a = self.publish()
        b = self.publish("extended_historical")
        pinned = lab.Experiment("old_experiment", a.dataset_id)
        original = lab.dataset_path(self.store, a.dataset_id).read_bytes()
        registry = lab.ReleaseRegistry(self.store)
        one = registry.promote("historical", a.dataset_id, expected_current=lab.ReleaseToken())
        two = registry.promote("historical", b.dataset_id, expected_current=one)
        three = registry.rollback("historical", a.dataset_id, expected_current=two)
        self.assertEqual((one.generation, two.generation, three.generation), (1, 2, 3))
        self.assertEqual(one.dataset_id, three.dataset_id)
        before = registry.path.read_bytes()
        with self.assertRaises(ContractError):
            registry.promote("historical", b.dataset_id, expected_current=one)
        self.assertEqual(registry.path.read_bytes(), before)
        self.assertEqual(pinned.read(self.store).dataset_id, a.dataset_id)
        self.assertEqual(lab.dataset_path(self.store, a.dataset_id).read_bytes(), original)
        self.assertEqual([e["action"] for e in registry.history()], ["promote", "promote", "rollback"])

    def test_rollback_missing_or_corrupt_target_rejects(self):
        a, b = self.publish(), self.publish("extended_historical")
        registry = lab.ReleaseRegistry(self.store)
        one = registry.promote("historical", a.dataset_id, expected_current=lab.ReleaseToken())
        two = registry.promote("historical", b.dataset_id, expected_current=one)
        previous = registry.path.read_bytes()
        path = lab.dataset_path(self.store, a.dataset_id)
        for remove in (False, True):
            if remove:
                path.unlink()
            else:
                path.write_bytes(b"broken\n")
            with self.assertRaises(ContractError):
                registry.rollback("historical", a.dataset_id, expected_current=two)
            self.assertEqual(registry.path.read_bytes(), previous)

    def test_rollback_unreleased_target_rejects(self):
        a, b = self.publish(), self.publish("extended_historical")
        registry = lab.ReleaseRegistry(self.store)
        token = registry.promote("historical", a.dataset_id, expected_current=lab.ReleaseToken())
        with self.assertRaises(ContractError):
            registry.rollback("historical", b.dataset_id, expected_current=token)

    def test_noop_replay_is_idempotent_but_still_validates(self):
        dataset = self.publish()
        registry = lab.ReleaseRegistry(self.store)
        token = registry.promote("historical", dataset.dataset_id, expected_current=lab.ReleaseToken())
        self.assertEqual(registry.promote("historical", dataset.dataset_id, expected_current=token), token)
        self.assertEqual(len(registry.history()), 1)
        lab.dataset_path(self.store, dataset.dataset_id).write_bytes(b"broken\n")
        with self.assertRaises(ContractError):
            registry.promote("historical", dataset.dataset_id, expected_current=token)

    def test_registry_audit_pointer_disagreement_rejects(self):
        dataset = self.publish()
        registry = lab.ReleaseRegistry(self.store)
        registry.promote("historical", dataset.dataset_id, expected_current=lab.ReleaseToken())
        data = lab.decode(registry.path.read_bytes())
        data["channels"]["historical"]["generation"] = 2
        registry.path.write_bytes(lab.canonical(data))
        with self.assertRaises(ContractError):
            registry.current("historical")

    def test_path_escape_rejects(self):
        with self.assertRaises(ContractError):
            lab.stage_build(self.store, "../escape", self.spec)
        with self.assertRaises(ContractError):
            lab.load_dataset(self.store, "../escape")


if __name__ == "__main__":
    unittest.main()
