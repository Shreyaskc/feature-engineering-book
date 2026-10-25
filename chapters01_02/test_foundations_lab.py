"""Executable examples and meaningful contract/identity boundary tests."""

from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from io import StringIO
import json
from pathlib import Path
import unittest

from foundations_lab import (
    ContractError, Delivery, Ledger, Revision, ingest, ledger_from_dict,
    load_fixture, selected_revisions, spend, spend_in_window,
)

ROOT = Path(__file__).parent


class FeatureContractTests(unittest.TestCase):
    def setUp(self):
        self.history = load_fixture().history

    def test_five_chapter_one_examples(self):
        cases = [
            (self.history, "C1", True, 50),
            (self.history + (Revision("K", 1, "C1", 540, 541, 5),),
             "C1", True, 55),
            (self.history + (Revision("L", 1, "C1", 600, 600, 7),),
             "C1", True, 50),
            (self.history, "C9", True, 0),
            (self.history, "C1", False, None),
        ]
        for history, customer, known, expected in cases:
            with self.subTest(customer=customer, known=known, expected=expected):
                self.assertEqual(spend(history, customer, 600,
                                       history_known=known), expected)

    def test_original_uses_only_a1_and_c1(self):
        selected = selected_revisions(self.history, known_at=600)
        self.assertEqual([(row.event_id, row.revision) for row in selected],
                         [("A", 1), ("C", 1)])

    def test_late_b_does_not_rewrite_original_query(self):
        self.assertEqual(spend(self.history, "C1", 600), 50)
        self.assertEqual(spend(self.history, "C1", 610), 95)
        self.assertEqual(spend(self.history, "C1", 600), 50)

    def test_fixed_and_rolling_window_are_different(self):
        fixed = spend_in_window(self.history, "C1", window_start=540,
                                window_end=600, known_at=610)
        self.assertEqual(fixed, 85)
        self.assertEqual(spend(self.history, "C1", 610), 95)
        self.assertEqual(spend(self.history, "C1", 611), 75)

    def test_chapter_one_exercise_variants(self):
        before_lower = Revision("K", 1, "C1", 539, 541, 5)
        inside_upper = Revision("L", 1, "C1", 599, 600, 7)
        self.assertEqual(spend(self.history + (before_lower,), "C1", 600), 50)
        self.assertEqual(spend(self.history + (inside_upper,), "C1", 600), 57)
        self.assertEqual(spend(self.history, "C1", 600, window_minutes=30), 30)

    def test_inclusive_availability_changes_revision(self):
        before = selected_revisions(self.history, known_at=604)
        exact = selected_revisions(self.history, known_at=605)
        self.assertEqual([r.amount for r in before if r.event_id == "C"], [30])
        self.assertEqual([r.amount for r in exact if r.event_id == "C"], [25])

    def test_known_empty_and_unknown_empty_are_different(self):
        self.assertEqual(spend((), "C1", 600), 0)
        self.assertIsNone(spend((), "C1", 600, history_known=False))

    def test_zero_amount_is_valid_known_spend(self):
        zero = Revision("Z", 1, "C1", 590, 591, 0)
        self.assertEqual(spend((zero,), "C1", 600), 0)
        self.assertEqual(selected_revisions((zero,), known_at=600), (zero,))

    def test_other_customers_do_not_contribute(self):
        other = Revision("Q", 1, "C2", 590, 591, 500)
        self.assertEqual(spend(self.history + (other,), "C1", 600), 50)

    def test_half_open_window_exact_edges(self):
        rows = tuple(Revision(f"X{i}", 1, "C1", time, time, 1)
                     for i, time in enumerate((539, 540, 599, 600)))
        self.assertEqual(spend(rows, "C1", 600), 2)

    def test_future_revision_does_not_hide_eligible_older_revision(self):
        rows = (Revision("X", 1, "C1", 590, 591, 3),
                Revision("X", 2, "C1", 590, 601, 9))
        self.assertEqual(spend(rows, "C1", 600), 3)

    def test_query_rejects_duplicate_canonical_rows(self):
        with self.assertRaises(ContractError):
            spend(self.history + self.history[:1], "C1", 600)

    def test_query_rejects_invalid_history_even_when_unknown(self):
        with self.assertRaises(ContractError):
            spend([None], "C1", 600, history_known=False)

    def test_query_parameter_validation(self):
        for changes in ({"decision_at": True}, {"decision_at": -1},
                        {"decision_at": 59}, {"window_minutes": 0},
                        {"window_minutes": 60.0}, {"history_known": 1},
                        {"customer_id": ""}):
            args = dict(history=self.history, customer_id="C1", decision_at=600)
            args.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                spend(**args)

    def test_fixed_window_parameter_validation(self):
        for changes in ({"window_start": 600}, {"window_end": 601},
                        {"window_start": -1}, {"known_at": False}):
            args = dict(window_start=540, window_end=600, known_at=600)
            args.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                spend_in_window(self.history, "C1", **args)


class RecordValidationTests(unittest.TestCase):
    def setUp(self):
        self.row = Revision("A", 1, "C1", 550, 551, 20)

    def test_revision_rejects_bad_identifiers(self):
        for field in ("event_id", "customer_id"):
            for value in ("", " ", " A", "A ", None, 1):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ContractError):
                        replace(self.row, **{field: value})

    def test_revision_rejects_bad_numbers(self):
        for field in ("revision", "event_time", "available_at", "amount"):
            for value in (True, 1.5, "20", None, -1):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ContractError):
                        replace(self.row, **{field: value})
        with self.assertRaises(ContractError):
            replace(self.row, revision=0)

    def test_availability_cannot_precede_event(self):
        with self.assertRaises(ContractError):
            replace(self.row, available_at=549)

    def test_operation_and_amount_contract(self):
        for changes in ({"op": "remove"}, {"op": "delete"},
                        {"op": "upsert", "amount": None}):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                replace(self.row, **changes)
        self.assertIsNone(replace(self.row, op="delete", amount=None).amount)

    def test_delivery_validation(self):
        for args in (("", self.row, 551), ("a1", None, 551),
                     ("a1", self.row, True), ("a1", self.row, 550)):
            with self.subTest(args=args), self.assertRaises(ContractError):
                Delivery(*args)

    def test_records_and_ledgers_are_frozen(self):
        for obj, field, value in ((self.row, "amount", 99),
                                  (Delivery("a1", self.row, 551),
                                   "delivered_at", 999),
                                  (Ledger(), "allow_restore", True)):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(obj, field, value)


class IdentityAndIngestionTests(unittest.TestCase):
    def setUp(self):
        self.ledger = load_fixture()
        self.a1 = self.ledger.history[0]

    def test_canonical_collections_are_tuples(self):
        self.assertIsInstance(self.ledger.history, tuple)
        self.assertIsInstance(self.ledger.deliveries, tuple)

    def test_identical_delivery_replay_is_idempotent(self):
        self.assertEqual(ingest(self.ledger, self.ledger.deliveries), self.ledger)

    def test_distinct_retry_is_retained_but_source_count_is_unchanged(self):
        replayed = ingest(self.ledger, [Delivery("a1-retry", self.a1, 609)])
        self.assertEqual(len(replayed.deliveries), 6)
        self.assertEqual(len(replayed.history), 5)
        self.assertEqual(replayed.history, self.ledger.history)
        self.assertEqual(replayed.history[0].available_at, 551)

    def test_delivery_time_does_not_redefine_source_availability(self):
        delayed = Ledger((Delivery("observed-later", self.a1, 700),))
        self.assertEqual(spend(delayed.history, "C1", 600), 20)

    def test_same_delivery_id_rejects_changed_observation_time(self):
        changed = replace(self.ledger.deliveries[0], delivered_at=609)
        with self.assertRaises(ContractError):
            ingest(self.ledger, [changed])

    def test_same_delivery_id_rejects_different_source(self):
        changed = Delivery("a1", self.ledger.history[1], 700)
        with self.assertRaises(ContractError):
            ingest(self.ledger, [changed])

    def test_source_revision_rejects_each_changed_payload_field(self):
        for changes in ({"amount": 21}, {"available_at": 552},
                        {"customer_id": "C9"}, {"event_time": 549},
                        {"op": "delete", "amount": None}):
            conflict = Delivery("a1-conflict", replace(self.a1, **changes), 700)
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                ingest(self.ledger, [conflict])

    def test_event_customer_and_time_are_immutable_between_revisions(self):
        for changes in ({"customer_id": "C9"}, {"event_time": 549}):
            changed = replace(self.a1, revision=2, available_at=610, **changes)
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                ingest(self.ledger, [Delivery("a2", changed, 610)])

    def test_availability_must_not_decrease_with_revision(self):
        older_availability = replace(self.a1, revision=2, available_at=550)
        with self.assertRaises(ContractError):
            ingest(self.ledger, [Delivery("a2", older_availability, 610)])

    def test_equal_availability_uses_highest_revision(self):
        newer = replace(self.a1, revision=7, amount=8)
        ledger = Ledger((Delivery("a7", newer, 552),
                         Delivery("a1-late-delivery", self.a1, 609)))
        self.assertEqual(spend(ledger.history, "C1", 600), 8)

    def test_gaps_do_not_require_synthetic_intermediate_revisions(self):
        newer = replace(self.a1, revision=5, available_at=555, amount=8)
        ledger = ingest(self.ledger, [Delivery("a5", newer, 555)])
        self.assertEqual(spend(ledger.history, "C1", 600), 38)
        self.assertEqual([r.revision for r in ledger.history if r.event_id == "A"],
                         [1, 5])

    def test_old_revision_can_arrive_after_new_revision(self):
        newer = replace(self.a1, revision=2, available_at=560, amount=8)
        ledger = Ledger((Delivery("a2", newer, 560),))
        ledger = ingest(ledger, [Delivery("a1-late", self.a1, 700)])
        self.assertEqual(spend(ledger.history, "C1", 600), 8)

    def test_whole_batch_rejection_leaves_inputs_unchanged(self):
        valid = Delivery("n1", Revision("N", 1, "C1", 590, 591, 2), 591)
        invalid = Delivery("a1-bad", replace(self.a1, amount=21), 610)
        batch = [valid, invalid]
        before_batch = batch.copy()
        before_history = self.ledger.history
        before_deliveries = self.ledger.deliveries
        with self.assertRaises(ContractError):
            ingest(self.ledger, batch)
        self.assertEqual(batch, before_batch)
        self.assertIs(self.ledger.history, before_history)
        self.assertIs(self.ledger.deliveries, before_deliveries)
        self.assertNotIn(valid, self.ledger.deliveries)

    def test_conflict_within_new_batch_rejects_without_returning_candidate(self):
        empty = Ledger()
        left = Delivery("x1", self.a1, 551)
        right = Delivery("x2", replace(self.a1, amount=21), 552)
        with self.assertRaises(ContractError):
            ingest(empty, [left, right])
        self.assertEqual(empty.history, ())

    def test_input_order_and_chunking_do_not_change_replay(self):
        items = list(reversed(self.ledger.deliveries))
        partial = ingest(Ledger(), items[:2])
        complete = ingest(partial, items[2:])
        self.assertEqual(complete, self.ledger)
        self.assertEqual(Ledger(tuple(items)), self.ledger)

    def test_success_does_not_mutate_supplied_list(self):
        items = list(self.ledger.deliveries)
        before = items.copy()
        created = Ledger(items)
        items.clear()
        self.assertEqual(created.deliveries, tuple(before))

    def test_ingest_and_policy_type_validation(self):
        for call in (lambda: Ledger(allow_restore=1),
                     lambda: Ledger(None), lambda: Ledger((None,)),
                     lambda: ingest(None, ()), lambda: ingest(self.ledger, None)):
            with self.assertRaises(ContractError):
                call()


class TombstoneExtensionTests(unittest.TestCase):
    def test_deletion_preserves_original_and_rolling_queries(self):
        history = load_fixture("deletion_extension").history
        self.assertEqual(spend(history, "C1", 600), 50)
        self.assertEqual(spend(history, "C1", 610), 95)
        self.assertEqual(spend_in_window(history, "C1", window_start=540,
                                        window_end=600, known_at=620), 60)

    def test_tombstone_is_selected_before_contribution_is_decided(self):
        history = load_fixture("deletion_extension").history
        before = selected_revisions(history, known_at=614)
        after = selected_revisions(history, known_at=615)
        self.assertEqual([(r.revision, r.op) for r in before if r.event_id == "C"],
                         [(2, "upsert")])
        self.assertEqual([(r.revision, r.op) for r in after if r.event_id == "C"],
                         [(3, "delete")])

    def test_default_contract_rejects_restoration(self):
        ledger = load_fixture("deletion_extension")
        restored = Revision("C", 4, "C1", 585, 620, 28)
        with self.assertRaises(ContractError):
            ingest(ledger, [Delivery("c4", restored, 620)])

    def test_restored_history_queries_need_no_ingestion_policy_flag(self):
        ledger = load_fixture("restoration_extension")
        self.assertTrue(ledger.allow_restore)
        self.assertEqual(spend_in_window(ledger.history, "C1", window_start=540,
                                        window_end=600, known_at=620), 88)
        self.assertEqual(spend(ledger.history, "C1", 600), 50)
        self.assertEqual(spend(ledger.history, "C1", 610), 95)

    def test_restoration_exercise_fixed_window_cutoffs(self):
        history = load_fixture("restoration_extension").history
        for cutoff, expected in ((600, 50), (610, 85), (619, 60), (620, 88)):
            with self.subTest(cutoff=cutoff):
                self.assertEqual(spend_in_window(history, "C1", window_start=540,
                                                window_end=600, known_at=cutoff),
                                 expected)

    def test_tombstone_is_neither_zero_row_nor_unknown_history(self):
        tombstone = Revision("X", 2, "C1", 590, 595, None, "delete")
        self.assertEqual(selected_revisions((tombstone,), known_at=600),
                         (tombstone,))
        self.assertEqual(spend((tombstone,), "C1", 600), 0)
        self.assertIsNone(spend((tombstone,), "C1", 600, history_known=False))

    def test_extensions_do_not_contaminate_base_fixture(self):
        load_fixture("restoration_extension")
        base = load_fixture()
        self.assertFalse(base.allow_restore)
        self.assertEqual(len(base.history), 5)
        self.assertTrue(all(r.op == "upsert" for r in base.history))


class FixturesAndPrintedSnippetsTests(unittest.TestCase):
    def test_fixture_shape_rejects_missing_extra_and_bad_schema(self):
        original = json.loads((ROOT / "fixtures" / "base.json").read_text())
        corruptions = []
        missing = deepcopy(original)
        missing.pop("allow_restore")
        corruptions.append(missing)
        extra = deepcopy(original)
        extra["unexpected"] = 1
        corruptions.append(extra)
        bad_record = deepcopy(original)
        bad_record["deliveries"][0]["record"]["extra"] = 1
        corruptions.append(bad_record)
        for version in (True, 2, "1"):
            changed = deepcopy(original)
            changed["schema_version"] = version
            corruptions.append(changed)
        for data in corruptions:
            with self.subTest(data=data), self.assertRaises(ContractError):
                ledger_from_dict(data)

    def test_fixture_name_is_bounded(self):
        with self.assertRaises(ContractError):
            load_fixture("../../private")

    def test_exact_printed_snippets_execute_with_matching_stdout(self):
        snippets = json.loads((ROOT / "printed_snippets.json").read_text())
        self.assertEqual(len(snippets), 8)
        for snippet in snippets:
            with self.subTest(snippet=snippet["id"]):
                self.assertLessEqual(max(map(len, snippet["code"].splitlines())), 74)
                output = StringIO()
                with redirect_stdout(output):
                    exec(compile(snippet["code"], snippet["id"], "exec"), {})
                self.assertEqual(output.getvalue(), snippet["expected_stdout"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
