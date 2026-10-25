"""Executable regression evidence for the capstone's bounded contracts.

Run from this directory: python -m unittest -v test_capstone_lab.py
Only standard-library dependencies are used. Temporary artifact tampering
never edits the checked-in fixtures, implementations, or expected snapshots.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
import itertools
import json
from pathlib import Path
import random
import shutil
import tempfile
import unittest
from unittest.mock import patch

import capstone_lab as lab
import foundations_lab as foundation
import parity_lab as serving
import randomized_checks as generated


ROOT = Path(__file__).resolve().parent
PAYLOAD_NAMES = {
    "source_snapshot.json", "baseline_dataset.json", "improved_dataset.json",
    "publications.json", "lookups.json", "comparison.json", "audit.json",
    "continuity.json"}
VENDOR_HASHES = {
    "fixtures/base.json": "0a063cdfe48d7fe4ad4b7b17ee274be7d11b0b77d35a2a348b47c6971302b983",
    "fixtures/deletion_extension.json": "3819861ac5d46a935f0324d7d9e44f31e4da9aa8b0ac1e263da52d20782e848e",
    "fixtures/restoration_extension.json": "f1b3cee424852661f896c742d863ccf61597889162b8b65431b640b64ceb3230",
    "foundations_lab.py": "3bbf4b75f430456d9bd5ad2caafcf34f05d38a77a8f4c11c75075eae0aab628a",
    "parity_lab.py": "1bd7fa504b465f1005cef7715ff7cd71a706e593fb0fa5d3308c6b30ad9a251e"}


def case_from_rows(*rows, decisions=lab.DECISIONS):
    deliveries = tuple(foundation.Delivery(f"delivery-{i}", row, row.available_at)
                       for i, row in enumerate(rows))
    return lab.Case("base", foundation.Ledger(deliveries), decisions=decisions)


def add_row(case, row):
    return replace(case, ledger=foundation.ingest(case.ledger, (
        foundation.Delivery(f"extra-{row.event_id}-{row.revision}", row, row.available_at),)))


def write_json(path, value):
    path.write_text(lab.canonical(value), encoding="utf-8")


class FixtureTests(unittest.TestCase):
    def test_exact_base_and_challenge_sources(self):
        base, challenge = lab.load_case(), lab.load_case("challenge")
        self.assertEqual(len(base.ledger.history), 6)
        self.assertEqual(len(challenge.ledger.history), 8)
        for case in (base, challenge):
            late = next(row for row in case.ledger.history if row.event_id == "E")
            self.assertEqual((late.revision, late.event_time, late.available_at, late.amount),
                             (1, 595, 612, 15))
        extra = {(r.event_id, r.revision): (r.available_at, r.amount)
                 for r in challenge.ledger.history}
        self.assertEqual(extra[("A", 2)], (604, 18))
        self.assertEqual(extra[("F", 1)], (606, 7))

    def test_exact_historical_values_and_lineage(self):
        for name, improved, baseline in (
                ("base", [50, 95, 0, None], [100, 110, 0, None]),
                ("challenge", [50, 100, 0, None], [105, 115, 0, None])):
            case = lab.load_case(name)
            for mode, values in (("snapshot_baseline", baseline),
                                 ("contract_pipeline", improved)):
                with self.subTest(case=name, implementation=mode):
                    rows = lab.build_dataset(case, mode)
                    self.assertEqual([row["value"] for row in rows], values)
                    self.assertEqual([row["row_id"] for row in rows], ["D1", "D2", "Z1", "U1"])
                    self.assertEqual([row["missing"] for row in rows], [False, False, False, True])
                    self.assertEqual([row["window_start"] for row in rows], [540, 550, 540, 540])
                    self.assertEqual([row["window_end"] for row in rows], [600, 610, 600, 600])
                    self.assertEqual([row["source_cutoff"] for row in rows],
                                     [620] * 4 if mode == "snapshot_baseline" else [600, 610, 600, 600])
                    self.assertEqual(rows[2]["source_versions"], [])
                    self.assertEqual(rows[3]["source_versions"], [])
            self.assertEqual(lab.build_dataset(case)[0]["source_versions"], [["A", 1], ["C", 1]])
            expected_d2 = [["A", 1 if name == "base" else 2], ["B", 1], ["C", 2], ["D", 1]]
            if name == "challenge":
                expected_d2.append(["F", 1])
            self.assertEqual(lab.build_dataset(case)[1]["source_versions"], expected_d2)

    def test_publication_and_immediate_lookup_tables(self):
        for name, times, values, improved, baseline in (
                ("base", [600, 605, 607], [50, 45, 85],
                 [None, 50, 45, 45, 85, 85], [None, 50, 95, 95, 180, 180]),
                ("challenge", [600, 604, 605, 606, 607], [50, 48, 43, 50, 90],
                 [None, 50, 43, 50, 90, 90], [None, 50, 141, 191, 281, 281])):
            case = lab.load_case(name)
            records = lab.publications(case)
            self.assertEqual([p.published_at for p in records], times)
            self.assertEqual([p.source_cutoff for p in records], times)
            self.assertEqual([p.value for p in records], values)
            self.assertEqual([p.revision for p in records], list(range(1, len(records) + 1)))
            self.assertTrue(all(p.key == serving.KEY and p.contracts == serving.CONTRACTS for p in records))
            for mode, wanted in (("contract_pipeline", improved), ("snapshot_baseline", baseline)):
                rows = lab.online_lookups(case, mode)
                self.assertEqual([row["raw_value"] for row in rows], wanted)
                self.assertEqual([row["requested_at"] for row in rows], [599, 600, 605, 606, 610, 620])
                self.assertEqual([row["request_id"] for row in rows], [f"Q{i}" for i in range(6)])
                self.assertEqual([row["policy_value"] for row in rows], improved)
                self.assertEqual([row["fallback_used"] for row in rows], [True] + [False] * 5)
                self.assertEqual(rows[0]["lookup_input"], 0)
                self.assertIsNone(rows[0]["raw_value"])
                self.assertEqual(rows[0]["fallback_value"], 0)
                self.assertTrue(all(row["fallback_value"] is None for row in rows[1:]))

    def test_metrics_have_explicit_populations_and_exclusions(self):
        for name in ("base", "challenge"):
            report = lab.compare(lab.load_case(name))
            self.assertEqual(report["decision_ids"], ["D1", "D2", "Z1", "U1"])
            self.assertEqual(report["request_ids"], [f"Q{i}" for i in range(6)])
            for mode, historical, complete, online in (
                    ("snapshot_baseline", 1, 0, 1), ("contract_pipeline", 3, 4, 5)):
                data = report["implementations"][mode]
                for metric, numerator, denominator, excluded in (
                        (data["historical"]["numeric_parity"], historical, 3, 1),
                        (data["historical"]["complete_row_parity"], complete, 4, 0),
                        (data["historical"]["missing"], 1, 4, 0),
                        (data["historical"]["known_zero"], 1, 4, 0),
                        (data["online"]["raw_policy_parity"], online, 5, 1),
                        (data["online"]["missing"], 1, 6, 0),
                        (data["online"]["fallback"], 1, 6, 0)):
                    self.assertEqual(metric, {"numerator": numerator, "denominator": denominator,
                        "excluded": excluded, "population": denominator + excluded,
                        "rate": numerator / denominator})

    def test_lookup_metadata_distinguishes_publication_from_composed_sum(self):
        for name in ("base", "challenge"):
            case = lab.load_case(name)
            publications = lab.publications(case)
            for mode in lab.IMPLEMENTATIONS:
                for row in lab.online_lookups(case, mode):
                    self.assertEqual(row["key"], asdict(serving.KEY))
                    self.assertEqual(row["contracts"], asdict(serving.CONTRACTS))
                    self.assertEqual(row["implementation"], mode)
                    self.assertEqual(row["schedule"], "immediate_publication_visibility")
                    eligible = [p for p in publications if p.published_at <= row["requested_at"]]
                    last = eligible[-1] if eligible else None
                    self.assertEqual(row["latest_input_published_at"], None if last is None else last.published_at)
                    returned = last if mode == "contract_pipeline" else None
                    self.assertEqual(row["returned_publication_revision"], None if returned is None else returned.revision)
                    self.assertEqual(row["returned_published_at"], None if returned is None else returned.published_at)
                    input_revisions = ([p.revision for p in eligible] if mode == "snapshot_baseline"
                                       else [] if last is None else [last.revision])
                    self.assertEqual(row["consumer_inputs"]["publication_revisions"], input_revisions)

    def test_audit_retains_late_evidence_without_reopening(self):
        for name, closed, audit, d2 in (("base", 85, 100, 95), ("challenge", 90, 105, 100)):
            case = lab.load_case(name)
            result = lab.audit_report(case)
            self.assertEqual((result["closed_policy_value"], result["audit_source_value"]), (closed, audit))
            self.assertEqual(result["difference"], 15)
            self.assertEqual(result["deadline_inclusive"], 610)
            self.assertEqual(result["fixed_window"], [540, 600])
            self.assertEqual(result["after_deadline_source_versions"], [["E", 1]])
            self.assertNotIn(["E", 1], result["closed_policy_source_versions"])
            self.assertIn(["E", 1], result["audit_source_versions"])
            self.assertEqual(result["rolling_historical_rows"][1]["value"], d2)

    def test_chapter_six_continuity_keeps_delayed_store_cache_schedule(self):
        report = lab.continuity_report()
        self.assertEqual(report["request_ids"], [f"R{i}" for i in range(6)])
        self.assertEqual(report["request_times"], [600, 602, 606, 608, 610, 620])
        self.assertEqual(report["raw_values"], [None, 50, 50, 50, 85, 85])
        self.assertEqual(report["policy_values"], [50, 50, 45, 85, 85, 85])
        self.assertEqual(report["source_values"], [50, 50, 45, 85, 85, 100])
        self.assertEqual(report["metrics"]["raw_policy_numeric"],
                         {"matches": 3, "evaluable": 5, "excluded": 1})
        self.assertEqual(report["metrics"]["trace_logging"],
                         {"matches": 6, "evaluable": 6, "excluded": 0})


class TemporalAndReplayTests(unittest.TestCase):
    def test_half_open_window_and_revision_before_aggregation(self):
        case = case_from_rows(
            foundation.Revision("lower", 1, "C1", 540, 540, 3),
            foundation.Revision("lower", 3, "C1", 540, 600, 7),
            foundation.Revision("lower", 8, "C1", 540, 601, 97),
            foundation.Revision("before", 1, "C1", 539, 540, 11),
            foundation.Revision("upper", 1, "C1", 600, 600, 13),
            foundation.Revision("inside", 1, "C1", 599, 600, 17),
            foundation.Revision("other", 1, "C2", 599, 600, 19))
        row = lab.build_dataset(case)[0]
        self.assertEqual(row["value"], 24)
        self.assertEqual(row["source_versions"], [["inside", 1], ["lower", 3]])
        self.assertEqual(lab.build_dataset(case, "snapshot_baseline")[0]["value"], 114)

    def test_highest_revision_wins_at_equal_availability_not_input_order(self):
        rows = (foundation.Revision("A", 1, "C1", 550, 551, 20),
                foundation.Revision("A", 3, "C1", 550, 600, 7),
                foundation.Revision("A", 8, "C1", 550, 600, 11))
        for permutation in itertools.permutations(rows):
            case = case_from_rows(*permutation)
            self.assertEqual(lab.build_dataset(case)[0]["value"], 11)
            self.assertEqual(lab.build_dataset(case)[0]["source_versions"], [["A", 8]])
            self.assertEqual(lab.publications(case)[0].value, 11)

    def test_deadline_is_inclusive_610_but_611_is_audit_only(self):
        case = lab.load_case("challenge")
        for minute, closed, historical in ((610, 105, 115), (611, 90, 100)):
            deliveries = tuple(replace(d, record=replace(d.record, available_at=minute),
                                       delivered_at=minute) if d.record.event_id == "E" else d
                               for d in case.ledger.deliveries)
            changed = replace(case, ledger=foundation.Ledger(deliveries))
            result = lab.audit_report(changed)
            self.assertEqual(result["closed_policy_value"], closed)
            self.assertEqual(result["audit_source_value"], 105)
            self.assertEqual(lab.build_dataset(changed)[1]["value"], historical)
            self.assertEqual(lab.publications(changed)[-1].published_at, 610 if minute == 610 else 607)
            self.assertEqual(result["after_deadline_source_versions"], [] if minute == 610 else [["E", 1]])

    def test_same_number_with_new_provenance_still_publishes(self):
        case = add_row(lab.load_case(), foundation.Revision("C", 3, "C1", 585, 608, 25))
        records = lab.publications(case)
        self.assertEqual([p.value for p in records], [50, 45, 85, 85])
        self.assertEqual([p.published_at for p in records], [600, 605, 607, 608])
        self.assertIn(("C", 2), records[-2].source_versions)
        self.assertIn(("C", 3), records[-1].source_versions)

    def test_simultaneous_revisions_publish_one_complete_snapshot(self):
        case = add_row(lab.load_case(), foundation.Revision("A", 2, "C1", 550, 605, 18))
        records = lab.publications(case)
        self.assertEqual([(p.published_at, p.value) for p in records], [(600, 50), (605, 43), (607, 83)])
        self.assertEqual(records[1].source_versions, (("A", 2), ("C", 2)))

    def test_exact_and_distinct_source_delivery_retries_preserve_semantics(self):
        case = lab.load_case("challenge")
        original = case.ledger
        retries = tuple(replace(d, delivery_id=d.delivery_id + "-retry", delivered_at=d.delivered_at + 100)
                        for d in original.deliveries)
        variants = (original.deliveries * 3, original.deliveries + retries,
                    tuple(reversed(original.deliveries)))
        for deliveries in variants:
            altered = replace(case, ledger=foundation.Ledger(deliveries))
            self.assertEqual(altered.ledger.history, original.history)
            self.assertEqual(lab.source_identity(altered.ledger), lab.source_identity(original))
            for mode in lab.IMPLEMENTATIONS:
                self.assertEqual(lab.build_dataset(altered, mode), lab.build_dataset(case, mode))
                self.assertEqual(lab.online_lookups(altered, mode), lab.online_lookups(case, mode))
            self.assertEqual(lab.publications(altered), lab.publications(case))
        self.assertEqual(case.ledger, original)

    def test_unique_publications_are_order_independent_before_any_duplicate_replay(self):
        for name, final, total in (("base", 85, 180), ("challenge", 90, 281)):
            records = lab.publications(lab.load_case(name))
            # In particular, newest first and an older unique version last
            # tests stale delivery handling without conflating it with retries.
            for permutation in itertools.permutations(records):
                self.assertEqual(lab.consume_snapshots(permutation)["value"], final)
                self.assertEqual(lab.consume_snapshots(permutation, "snapshot_baseline")["value"], total)
                self.assertEqual(lab.consume_snapshots(permutation)["publication_revisions"], [len(records)])

    def test_sink_duplicate_replay_is_idempotent_for_both_consumers(self):
        records = lab.publications(lab.load_case("challenge"))
        replay = list(reversed(records)) + list(records) * 3
        random.Random(402).shuffle(replay)
        for mode in lab.IMPLEMENTATIONS:
            self.assertEqual(lab.consume_snapshots(replay, mode), lab.consume_snapshots(records, mode))

    def test_known_empty_is_zero_and_unknown_is_none(self):
        case = lab.Case("base", foundation.Ledger())
        dataset = lab.build_dataset(case)
        self.assertEqual([row["value"] for row in dataset], [0, 0, 0, None])
        self.assertEqual([row["missing"] for row in dataset], [False, False, False, True])
        records = lab.publications(case)
        self.assertEqual([(p.value, p.source_versions) for p in records], [(0, ())])
        for mode in lab.IMPLEMENTATIONS:
            self.assertEqual(lab.consume_snapshots(records, mode)["value"], 0)
            rows = lab.online_lookups(case, mode)
            self.assertEqual([row["raw_value"] for row in rows], [None, 0, 0, 0, 0, 0])
            self.assertEqual([row["fallback_used"] for row in rows], [True, False, False, False, False, False])
            self.assertEqual(rows[1]["lookup_input"], 0)
            self.assertIsNone(rows[1]["fallback_value"])
        self.assertEqual(lab.consume_snapshots(()), {"value": None, "publication_revisions": [],
            "source_versions": [], "source_cutoff": None})


class RejectionTests(unittest.TestCase):
    def test_unknown_modes_fail_before_computation_in_every_mode_api(self):
        case = lab.load_case()
        for action in (lambda: lab.build_dataset(case, "mystery"),
                       lambda: lab.online_lookups(case, "mystery"),
                       lambda: lab.consume_snapshots((), "mystery")):
            with self.assertRaisesRegex(lab.CapstoneError, "implementation must be snapshot_baseline or contract_pipeline"):
                action()
        for action in (lambda: lab.load_case("other"), lambda: lab.input_files("other")):
            with self.assertRaisesRegex(lab.CapstoneError, "case must be base or challenge"):
                action()

    def test_metric_empty_exclusion_and_strict_boolean_entries(self):
        self.assertEqual(lab.metric(()), {"numerator": 0, "denominator": 0,
                         "excluded": 0, "population": 0, "rate": None})
        self.assertEqual(lab.metric((None, None)), {"numerator": 0, "denominator": 0,
                         "excluded": 2, "population": 2, "rate": None})
        self.assertEqual(lab.metric((True, False, None)), {"numerator": 1, "denominator": 2,
                         "excluded": 1, "population": 3, "rate": 0.5})
        for invalid in (0, 1, "True", float("nan"), []):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(lab.CapstoneError, "metric entries must be booleans"):
                lab.metric((True, invalid))

    def test_decision_and_case_metadata(self):
        for changes, message in (({"row_id": ""}, "decision row_id is required"),
                ({"customer_id": " "}, "decision customer_id is required"),
                ({"decision_at": True}, "decision_at must be an integer >= 60"),
                ({"decision_at": 59}, "decision_at must be an integer >= 60"),
                ({"decision_at": 600.0}, "decision_at must be an integer >= 60"),
                ({"history_known": 1}, "history_known must be a boolean")):
            with self.subTest(changes=changes), self.assertRaisesRegex(lab.CapstoneError, message):
                replace(lab.DECISIONS[0], **changes)
        case = lab.load_case()
        for changes, message in (({"name": "other"}, "case must be base or challenge"),
                ({"ledger": ()}, "case ledger must be a Ledger"),
                ({"audit_at": 609}, "audit_at must be an integer >= 610"),
                ({"audit_at": True}, "audit_at must be an integer >= 610"),
                ({"decisions": []}, "decisions must be a nonempty tuple"),
                ({"decisions": ()}, "decisions must be a nonempty tuple"),
                ({"decisions": (None,)}, "decisions must contain Decision records"),
                ({"decisions": (lab.DECISIONS[0],) * 2}, "duplicate decision row_id"),
                ({"decisions": (lab.Decision("future", "C1", 621),)}, "audit must not precede a decision")):
            with self.subTest(changes=changes), self.assertRaisesRegex(lab.CapstoneError, message):
                replace(case, **changes)

    def test_strict_source_json_fields_and_conflicting_identities(self):
        payload = lab.source_payload(lab.load_case().ledger)
        mutations = []
        extra = deepcopy(payload); extra["extra"] = 1
        mutations.append((extra, "fixture must have exactly"))
        absent = deepcopy(payload); del absent["allow_restore"]
        mutations.append((absent, "fixture must have exactly"))
        bad_schema = deepcopy(payload); bad_schema["schema_version"] = True
        mutations.append((bad_schema, "schema_version must be integer 1"))
        bad_record = deepcopy(payload); bad_record["deliveries"][0]["record"]["extra"] = 1
        mutations.append((bad_record, "record must have exactly"))
        missing_cutoff = deepcopy(payload); del missing_cutoff["deliveries"][0]["record"]["available_at"]
        mutations.append((missing_cutoff, "record must have exactly"))
        boolean_amount = deepcopy(payload); boolean_amount["deliveries"][0]["record"]["amount"] = True
        mutations.append((boolean_amount, "amount must be an integer"))
        for raw, message in mutations:
            with self.assertRaisesRegex(foundation.ContractError, message):
                foundation.ledger_from_dict(raw)
        case = lab.load_case()
        delivery = case.ledger.deliveries[0]
        conflicting = replace(delivery, record=replace(delivery.record, amount=delivery.record.amount + 1))
        with self.assertRaisesRegex(foundation.ContractError, "delivery_id reused with conflicting payload"):
            foundation.ingest(case.ledger, (conflicting,))
        with self.assertRaisesRegex(foundation.ContractError, "source revision reused with conflicting payload"):
            foundation.ingest(case.ledger, (replace(conflicting, delivery_id="different"),))
        with self.assertRaisesRegex(foundation.ContractError, "event customer and time are immutable"):
            add_row(case, replace(delivery.record, revision=9, customer_id="C2", available_at=620))
        self.assertEqual(lab.build_dataset(case)[0]["value"], 50)

    def test_adapter_rejects_deletion_and_restoration_on_every_entry_path(self):
        with self.assertRaisesRegex(lab.CapstoneError, "adapter requires a Ledger"):
            lab.adapt_source(())
        for filename, message in (("deletion_extension", "does not support deletion"),
                                  ("restoration_extension", "does not support restoration")):
            ledger = foundation.ledger_from_dict(json.loads((ROOT / "fixtures" / f"{filename}.json").read_text()))
            for action in (lambda: lab.adapt_source(ledger), lambda: lab.Case("base", ledger)):
                with self.subTest(fixture=filename), self.assertRaisesRegex(lab.CapstoneError, message):
                    action()
            # Extension metadata must be checked before it is merged into
            # the base ledger, where allow_restore could otherwise be lost.
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "fixtures").mkdir()
                shutil.copyfile(ROOT / "fixtures/base.json", root / "fixtures/base.json")
                for extension in ("late_arrival", "challenge"):
                    write_json(root / "fixtures" / f"{extension}.json", lab.source_payload(ledger))
                with patch.object(lab, "ROOT", root):
                    for name in ("base", "challenge"):
                        with self.assertRaisesRegex(lab.CapstoneError, message):
                            lab.load_case(name)
        with self.assertRaisesRegex(lab.CapstoneError, "does not support restoration"):
            lab.adapt_source(foundation.Ledger(allow_restore=True))

    def test_consumer_requires_publications_and_matching_full_semantic_key(self):
        record = lab.publications(lab.load_case())[0]
        with self.assertRaisesRegex(lab.CapstoneError, "consumer requires PublishedRevision records"):
            lab.consume_snapshots((asdict(record),))
        for field, value in (("feature_definition_id", "wrong"), ("policy_id", "wrong"),
                             ("entity", "C2"), ("window_start", 539), ("window_end", 601)):
            with self.subTest(key=field), self.assertRaisesRegex(lab.CapstoneError, "semantic key or contract mismatch"):
                lab.consume_snapshots((replace(record, key=replace(record.key, **{field: value})),))
        for field in asdict(serving.CONTRACTS):
            with self.subTest(contract=field), self.assertRaisesRegex(lab.CapstoneError, "semantic key or contract mismatch"):
                lab.consume_snapshots((replace(record, contracts=replace(record.contracts, **{field: "wrong"})),))

    def test_conflicting_publication_revision_is_not_a_duplicate(self):
        record = lab.publications(lab.load_case())[0]
        for change in ({"value": 51}, {"source_versions": (("A", 2),)},
                       {"published_at": 601, "source_cutoff": 601}):
            with self.subTest(change=change), self.assertRaisesRegex(lab.CapstoneError, "conflicting publication revision"):
                lab.consume_snapshots((record, replace(record, **change)))

    def test_consumer_cutoff_deadline_metadata_and_source_versions(self):
        record = lab.publications(lab.load_case())[0]
        for change in ({"source_cutoff": 599}, {"published_at": 599, "source_cutoff": 599},
                       {"published_at": 611, "source_cutoff": 611}):
            with self.subTest(change=change), self.assertRaisesRegex(lab.CapstoneError, "cutoff/deadline contract"):
                lab.consume_snapshots((replace(record, **change),))
        with self.assertRaisesRegex(lab.CapstoneError, "source-version metadata is required"):
            lab.consume_snapshots((replace(record, source_versions=()),))
        # Corrected Chapter 6 now rejects malformed lineage at construction,
        # before the consumer receives the record; valid empty lineage above
        # still reaches the capstone's stricter nonempty-source contract.
        for versions, message in (((("", 1),), "nonempty"),
                                  ((("A", 0),), "positive integers"),
                                  ((("A", True),), "positive integers"),
                                  ((("A", 1.0),), "positive integers"),
                                  ((("A",),), "pairs"),
                                  ((("A", 1, "extra"),), "pairs")):
            with self.subTest(versions=versions), self.assertRaisesRegex(ValueError, message):
                replace(record, source_versions=versions)
        with self.assertRaisesRegex(ValueError, "one revision per event ID"):
            replace(record, source_versions=(("A", 1), ("A", 2)))
        newer = replace(record, revision=2, published_at=600, source_cutoff=600)
        older = replace(record, published_at=601, source_cutoff=601)
        with self.assertRaisesRegex(lab.CapstoneError, "publication time must not decrease by revision"):
            lab.consume_snapshots((newer, older))

    def test_publication_constructor_rejects_nonfinite_and_future_evidence(self):
        record = lab.publications(lab.load_case())[0]
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaisesRegex(ValueError, "NaN and infinity are not feature values"):
                replace(record, value=value)
        with self.assertRaisesRegex(TypeError, "feature value must be an int or float"):
            replace(record, value=True)
        with self.assertRaisesRegex(ValueError, "publication cannot use future source evidence"):
            replace(record, source_cutoff=601)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "artifacts"
        self.case = lab.load_case()

    def persist(self):
        return lab.persist_run(self.case, self.directory)

    def manifest(self):
        return json.loads((self.directory / "manifest.json").read_text())

    def test_payload_inventory_and_verified_readback_hashes(self):
        result = self.persist()
        self.assertEqual(set(lab.ARTIFACT_NAMES), PAYLOAD_NAMES)
        self.assertEqual(set(lab.artifact_payloads(self.case)), PAYLOAD_NAMES)
        self.assertEqual({p.name for p in self.directory.iterdir()}, PAYLOAD_NAMES | {"manifest.json"})
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["artifacts_verified"], 9)
        self.assertTrue(result["recomputed_from_retained_snapshot"])
        manifest = self.manifest()
        for name in PAYLOAD_NAMES:
            data = (self.directory / name).read_bytes()
            self.assertEqual(sha256(data).hexdigest(), manifest["artifact_sha256"][name])
            self.assertEqual(data.decode(), lab.canonical(json.loads(data)))
        self.assertEqual(manifest["training_boundary"]["artifact_kind"], "feature_dataset_only")
        self.assertFalse(manifest["training_boundary"]["labels_present"])
        self.assertFalse(manifest["training_boundary"]["model_fitted"])

    def test_two_clean_generations_are_byte_identical_for_both_cases(self):
        for name in ("base", "challenge"):
            case = lab.load_case(name)
            first, second = Path(self.temp.name) / f"{name}-first", Path(self.temp.name) / f"{name}-second"
            self.assertEqual(lab.persist_run(case, first), lab.persist_run(case, second))
            self.assertEqual({p.name: p.read_bytes() for p in first.iterdir()},
                             {p.name: p.read_bytes() for p in second.iterdir()})

    def test_expected_semantic_snapshots(self):
        for case_name in ("base", "challenge"):
            expected_dir = ROOT / "expected_outputs" / case_name
            self.assertTrue(expected_dir.is_dir(), f"missing expected case: {case_name}")
            actual = lab.artifact_payloads(lab.load_case(case_name))
            for name in sorted(PAYLOAD_NAMES):
                with self.subTest(case=case_name, artifact=name):
                    self.assertTrue((expected_dir / name).is_file(), f"missing expected snapshot: {name}")
                    self.assertEqual(lab.canonical(actual[name]), (expected_dir / name).read_text())

    def test_vendored_implementation_bytes_are_unchanged(self):
        for name, expected in VENDOR_HASHES.items():
            self.assertEqual(sha256((ROOT / name).read_bytes()).hexdigest(), expected)

    def test_vendor_manifest_binds_original_fixtures_and_modules(self):
        manifest = json.loads((ROOT / "vendor_manifest.json").read_text())
        self.assertEqual(set(manifest), {"schema_version", "files"})
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(set(manifest["files"]), set(VENDOR_HASHES))
        for name, metadata in manifest["files"].items():
            self.assertEqual(set(metadata), {"origin", "modified", "sha256"})
            self.assertIs(metadata["modified"], False)
            self.assertTrue(metadata["origin"])
            self.assertEqual(metadata["sha256"], VENDOR_HASHES[name])
            self.assertEqual(sha256((ROOT / name).read_bytes()).hexdigest(), metadata["sha256"])

    def test_nonempty_destination_is_rejected_without_overwriting(self):
        self.directory.mkdir()
        marker = self.directory / "retain-me.txt"
        marker.write_text("preserve these bytes")
        with self.assertRaisesRegex(lab.CapstoneError, "output directory must be empty"):
            self.persist()
        self.assertEqual(marker.read_text(), "preserve these bytes")

    def test_absent_extra_or_missing_artifacts_reject_exact_inventory(self):
        with self.assertRaisesRegex(lab.CapstoneError, "artifact inventory mismatch"):
            lab.verify_artifacts(self.directory)
        self.persist()
        unexpected = self.directory / "extra.json"
        unexpected.write_text("{}")
        with self.assertRaisesRegex(lab.CapstoneError, "artifact inventory mismatch"):
            lab.verify_artifacts(self.directory)
        unexpected.unlink()
        (self.directory / "audit.json").unlink()
        with self.assertRaisesRegex(lab.CapstoneError, "artifact inventory mismatch"):
            lab.verify_artifacts(self.directory)

    def test_content_tampering_fails_and_rehashing_does_not_make_it_valid(self):
        self.persist()
        path = self.directory / "improved_dataset.json"
        data = json.loads(path.read_text())
        data[0]["value"] += 1
        write_json(path, data)
        with self.assertRaisesRegex(lab.CapstoneError, "artifact content mismatch: improved_dataset.json"):
            lab.verify_artifacts(self.directory)
        manifest = self.manifest()
        manifest["artifact_sha256"][path.name] = sha256(path.read_bytes()).hexdigest()
        write_json(self.directory / "manifest.json", manifest)
        with self.assertRaisesRegex(lab.CapstoneError, "artifact digests disagree with recomputation"):
            lab.verify_artifacts(self.directory)

    def test_every_payload_is_checked_from_retained_bytes(self):
        self.persist()
        for name in sorted(PAYLOAD_NAMES):
            path = self.directory / name
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.subTest(artifact=name), self.assertRaisesRegex(lab.CapstoneError, "artifact content mismatch"):
                lab.verify_artifacts(self.directory)
            path.write_bytes(original)
        self.assertEqual(lab.verify_artifacts(self.directory)["status"], "PASS")

    def test_rehashed_changed_source_and_cohort_are_not_accepted_as_official(self):
        self.persist()
        path = self.directory / "source_snapshot.json"
        raw = json.loads(path.read_text())
        raw["deliveries"][0]["record"]["amount"] += 1
        write_json(path, raw)
        manifest = self.manifest()
        ledger = foundation.ledger_from_dict(raw)
        manifest["canonical_source_sha256"] = lab.source_identity(ledger)
        manifest["artifact_sha256"][path.name] = sha256(path.read_bytes()).hexdigest()
        write_json(self.directory / "manifest.json", manifest)
        with self.assertRaisesRegex(lab.CapstoneError, "retained source disagrees with named input fixtures"):
            lab.verify_artifacts(self.directory)
        with self.assertRaisesRegex(lab.CapstoneError, "retained source disagrees with named input fixtures"):
            lab.make_manifest(replace(self.case, ledger=ledger), lab.artifact_payloads(replace(self.case, ledger=ledger)))
        for changed in (replace(self.case, audit_at=621),
                        replace(self.case, decisions=self.case.decisions[:2])):
            with self.assertRaisesRegex(lab.CapstoneError, "retained cohort disagrees with capstone contract"):
                lab.make_manifest(changed, lab.artifact_payloads(changed))

    def test_manifest_metadata_drift_is_rejected(self):
        self.persist()
        original = self.manifest()
        for field in ("schema_version", "runtime", "code_sha256", "input_file_sha256",
                      "canonical_source_sha256", "contracts", "training_boundary"):
            altered = deepcopy(original)
            altered[field] = "tampered"
            write_json(self.directory / "manifest.json", altered)
            with self.subTest(field=field), self.assertRaisesRegex(lab.CapstoneError, f"manifest {field} mismatch"):
                lab.verify_artifacts(self.directory)
        write_json(self.directory / "manifest.json", original)
        (self.directory / "manifest.json").write_text(json.dumps(original))
        with self.assertRaisesRegex(lab.CapstoneError, "manifest serialization mismatch"):
            lab.verify_artifacts(self.directory)

    def test_retained_cohort_tampering_is_rejected_before_hash_credit(self):
        self.persist()
        original = self.manifest()
        for config in ({"audit_at": 621, "decisions": original["case_config"]["decisions"]},
                       {"audit_at": 620, "decisions": original["case_config"]["decisions"][:2]}):
            changed = deepcopy(original)
            changed["case_config"] = config
            write_json(self.directory / "manifest.json", changed)
            with self.assertRaisesRegex(lab.CapstoneError, "retained cohort disagrees with capstone contract"):
                lab.verify_artifacts(self.directory)

    def test_current_code_and_input_bytes_are_bound_by_manifest(self):
        self.persist()
        copied_root = Path(self.temp.name) / "copied-lab"
        copied_root.mkdir()
        for name in lab.CODE_FILES:
            shutil.copyfile(ROOT / name, copied_root / name)
        shutil.copytree(ROOT / "fixtures", copied_root / "fixtures")
        with patch.object(lab, "ROOT", copied_root):
            self.assertEqual(lab.verify_artifacts(self.directory)["status"], "PASS")
            for name, message in (("capstone_lab.py", "manifest code_sha256 mismatch"),
                                  ("fixtures/base.json", "manifest input_file_sha256 mismatch")):
                path = copied_root / name
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                with self.assertRaisesRegex(lab.CapstoneError, message):
                    lab.verify_artifacts(self.directory)
                path.write_bytes(original)

    def test_bad_retained_json_and_manifest_shapes_have_named_errors(self):
        self.persist()
        manifest_path = self.directory / "manifest.json"
        original = self.manifest()
        for malformed, message in (([], "manifest must be an object"),
                ({**original, "surprise": 1}, "manifest fields mismatch"),
                ({**original, "case_config": {}}, "manifest case_config fields mismatch"),
                ({**original, "case_config": {"audit_at": 620, "decisions": {}}}, "manifest decisions must be an array")):
            write_json(manifest_path, malformed)
            with self.assertRaisesRegex(lab.CapstoneError, message):
                lab.verify_artifacts(self.directory)
        manifest_path.write_text("{broken json")
        with self.assertRaisesRegex(lab.CapstoneError, "invalid retained evidence"):
            lab.verify_artifacts(self.directory)

    def test_adapter_rejection_also_applies_to_retained_snapshots(self):
        self.persist()
        for filename, message in (("deletion_extension", "does not support deletion"),
                                  ("restoration_extension", "does not support restoration")):
            shutil.copyfile(ROOT / "fixtures" / f"{filename}.json", self.directory / "source_snapshot.json")
            with self.assertRaisesRegex(lab.CapstoneError, message):
                lab.verify_artifacts(self.directory)

    def test_distinct_source_retries_can_persist_with_same_semantic_identity(self):
        self.persist()
        delivery = self.case.ledger.deliveries[0]
        replay = replace(self.case, ledger=foundation.ingest(self.case.ledger,
            (replace(delivery, delivery_id="a-distinct-retry", delivered_at=900),)))
        other = Path(self.temp.name) / "retry-artifacts"
        result = lab.persist_run(replay, other)
        self.assertEqual(result["canonical_source_sha256"], lab.source_identity(self.case.ledger))
        self.assertNotEqual((self.directory / "source_snapshot.json").read_bytes(),
                            (other / "source_snapshot.json").read_bytes())
        for name in PAYLOAD_NAMES - {"source_snapshot.json"}:
            self.assertEqual((self.directory / name).read_bytes(), (other / name).read_bytes())


class GeneratedTests(unittest.TestCase):
    def test_independent_raw_oracles_agree_with_hand_calculated_edge(self):
        raw = {"deliveries": [{"record": {"event_id": "A", "revision": revision,
                "customer_id": "C1", "event_time": 540, "available_at": available,
                "amount": amount, "op": "upsert"}}
                for revision, available, amount in ((1, 540, 3), (2, 600, 7), (3, 610, 11), (4, 611, 99))]}
        decision = {"row_id": "D", "customer_id": "C1", "decision_at": 600, "history_known": True}
        self.assertEqual(generated.historical_oracle(raw, decision)["value"], 7)
        self.assertEqual(generated.publication_oracle(raw), [
            {"revision": 1, "published_at": 600, "source_cutoff": 600, "value": 7, "source_versions": [["A", 2]]},
            {"revision": 2, "published_at": 610, "source_cutoff": 610, "value": 11, "source_versions": [["A", 3]]}])

    def test_seeded_checks_repeat_and_counts_are_explicit(self):
        first = generated.run_checks(cases=24)
        self.assertEqual(first, generated.run_checks(cases=24))
        self.assertEqual(first["status"], "passed")
        self.assertEqual(first["seed"], 20261005)
        self.assertEqual(first["generated_cases"], 24)
        self.assertEqual(first["checks"]["historical_oracle_rows"], 240)
        self.assertEqual(first["checks"]["metamorphic_historical_rows"], 720)
        self.assertEqual(first["checks"]["online_oracle_rows"], 288)
        self.assertEqual(first["checks"]["sink_unique_shuffle"], 48)
        self.assertEqual(first["checks"]["sink_stale_arrives_last"], 48)
        self.assertEqual(first["checks"]["sink_duplicate_replay"], 48)
        self.assertTrue(all(first["coverage"].values()))
        self.assertNotEqual(first["corpus_sha256"], generated.run_checks(seed=17, cases=24)["corpus_sha256"])

    def test_generator_arguments_reject_bool_and_nonpositive_case_counts(self):
        for cases in (0, -1, True, 1.0):
            with self.assertRaisesRegex(ValueError, "cases must be a positive integer"):
                generated.run_checks(cases=cases)
        for seed in (True, 1.0, "17"):
            with self.assertRaisesRegex(ValueError, "seed must be an integer"):
                generated.run_checks(seed=seed)

    def test_executable_exercise_answers_match_retained_snapshot(self):
        from exercise_answers import exercise_report
        report = exercise_report()
        self.assertEqual(len(report), 8)
        self.assertEqual(report["2_deadline"], {
            "610": {"closed": 105, "audit": 105, "D2": 115},
            "611": {"closed": 90, "audit": 105, "D2": 100}})
        self.assertEqual(lab.canonical(report), (ROOT / "expected_outputs/exercise_answers.json").read_text())


if __name__ == "__main__":
    unittest.main()
