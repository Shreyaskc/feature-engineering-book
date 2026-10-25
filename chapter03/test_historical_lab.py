"""Behavioral regression tests for historical reconstruction, not just totals."""
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from foundations_lab import (ContractError, Delivery, Ledger, Revision, ingest,
                            ledger_from_dict)
from historical_lab import (SQLITE_MAX, Query, explain, load_fixture,
                            reference_selection, reference_value, sqlite_value,
                            wrong_ignore_availability, wrong_latest_then_availability)
from sqlite_lab import selected

ROOT = Path(__file__).resolve().parent


def ledger(*rows, restore=False):
    return Ledger(tuple(Delivery(f"d-{i}", r, r.available_at)
                        for i, r in enumerate(rows)), allow_restore=restore)


class HistoricalTests(unittest.TestCase):
    def setUp(self):
        self.base = load_fixture()
        self.q = Query("C1", 540, 600, 600)

    def assertBoth(self, data, query, expected):
        self.assertEqual(reference_value(data, query), expected)
        self.assertEqual(sqlite_value(data, query), expected)

    def test_decisions_are_distinct_queries(self):
        self.assertBoth(self.base, self.q, 50)
        self.assertBoth(self.base, Query("C1", 550, 610, 610), 95)
        self.assertBoth(self.base, Query("C1", 540, 600, 610), 85)

    def test_filter_availability_before_revision_selection(self):
        self.assertEqual(wrong_latest_then_availability(self.base, self.q), 20)
        self.assertEqual(wrong_ignore_availability(self.base, self.q), 85)
        self.assertEqual([(r.event_id, r.revision) for r in reference_selection(self.base, self.q)], [("A", 1), ("C", 1)])
        self.assertEqual(selected(self.base, self.q), [("A", 1, 20, "upsert"), ("C", 1, 30, "upsert")])

    def test_correction_can_lower_a_fixed_window(self):
        for t, total in [(604, 50), (605, 45), (606, 45), (607, 85)]:
            with self.subTest(cutoff=t):
                self.assertBoth(self.base, replace(self.q, known_at=t), total)

    def test_equal_availability_uses_revision_not_input_order(self):
        rows = (Revision("X", 1, "C1", 580, 590, 30),
                Revision("X", 3, "C1", 580, 600, 25),
                Revision("X", 8, "C1", 580, 600, 22))
        for ordered in (rows, tuple(reversed(rows))):
            self.assertBoth(ledger(*ordered), self.q, 22)
            self.assertEqual(selected(ledger(*ordered), self.q), [("X", 8, 22, "upsert")])

    def test_boundaries_are_half_open_and_availability_inclusive(self):
        probes = [(539, 541, 0), (540, 541, 5), (599, 600, 5),
                  (600, 600, 0), (590, 601, 0)]
        for event, available, expected in probes:
            with self.subTest(event=event, available=available):
                self.assertBoth(ledger(Revision("X", 1, "C1", event, available, 5)), self.q, expected)

    def test_tombstone_wins_and_preserves_old_cutoffs(self):
        data = load_fixture("deletion_extension")
        self.assertBoth(data, self.q, 50)
        self.assertBoth(data, replace(self.q, known_at=614), 85)
        self.assertBoth(data, replace(self.q, known_at=615), 60)
        chosen = selected(data, replace(self.q, known_at=620))
        self.assertIn(("C", 3, None, "delete"), chosen)
        trace = explain(data, replace(self.q, known_at=620))
        self.assertEqual(next(r for r in trace["selected"] if r["event_id"] == "C")["reason"], "deleted")

    def test_restoration_is_explicit_and_cutoff_specific(self):
        restored = load_fixture("restoration_extension")
        with self.assertRaises(ContractError):
            Ledger(restored.deliveries, allow_restore=False)
        self.assertBoth(restored, replace(self.q, known_at=619), 60)
        self.assertBoth(restored, replace(self.q, known_at=620), 88)
        self.assertBoth(restored, self.q, 50)

    def test_deletion_at_same_availability_tie(self):
        data = ledger(Revision("X", 1, "C1", 590, 600, 5),
                      Revision("X", 2, "C1", 590, 600, None, "delete"))
        self.assertBoth(data, self.q, 0)
        self.assertEqual(selected(data, self.q), [("X", 2, None, "delete")])

    def test_retry_time_never_rewrites_source_availability(self):
        a = self.base.history[0]
        retry = Delivery("retry-A", a, 609)
        data = ingest(self.base, [retry, retry])
        self.assertEqual((len(data.deliveries), len(data.history)), (6, 5))
        self.assertEqual(data.history[0].available_at, 551)
        self.assertBoth(data, self.q, 50)
        self.assertEqual(Ledger(tuple(reversed(data.deliveries))), data)
        self.assertEqual(ingest(data, data.deliveries), data)

    def test_future_versions_do_not_change_original_decision(self):
        past = Ledger(tuple(d for d in self.base.deliveries if d.record.available_at <= 600))
        self.assertEqual(reference_selection(past, self.q), reference_selection(self.base, self.q))
        self.assertBoth(past, self.q, 50)

    def test_zero_known_empty_and_unknown_are_distinct(self):
        self.assertBoth(self.base, replace(self.q, customer_id="C9"), 0)
        self.assertBoth(self.base, replace(self.q, customer_id="C9", history_known=False), None)
        self.assertBoth(self.base, replace(self.q, history_known=False), None)
        self.assertBoth(Ledger(), self.q, 0)
        self.assertBoth(Ledger(), replace(self.q, history_known=False), None)
        zero = ledger(Revision("Z", 1, "C1", 590, 590, 0))
        self.assertBoth(zero, self.q, 0)
        self.assertEqual(selected(zero, self.q), [("Z", 1, 0, "upsert")])

    def test_other_customers_and_outside_windows_are_explained(self):
        data = ledger(Revision("X", 1, "C2", 590, 591, 100),
                      Revision("Y", 1, "C1", 602, 603, 10))
        q = replace(self.q, known_at=610)
        self.assertBoth(data, q, 0)
        self.assertEqual([r["reason"] for r in explain(data, q)["selected"]],
                         ["different customer", "outside event window"])

    def test_query_rejects_invalid_types_and_windows(self):
        for name in ("window_start", "window_end", "known_at"):
            for bad in (True, False, -1, 1.5, "600", None, SQLITE_MAX + 1):
                with self.subTest(name=name, value=bad), self.assertRaises(ContractError):
                    replace(self.q, **{name: bad})
        for bad in ("", " C1", "C1 ", None, 2):
            with self.subTest(customer=bad), self.assertRaises(ContractError):
                replace(self.q, customer_id=bad)
        for bad in (0, 1, "true", None):
            with self.subTest(known=bad), self.assertRaises(ContractError):
                replace(self.q, history_known=bad)
        for start, end, cutoff in ((600, 600, 600), (601, 600, 610), (540, 601, 600)):
            with self.assertRaises(ContractError):
                Query("C1", start, end, cutoff)

    def test_query_is_immutable_and_arguments_are_checked(self):
        with self.assertRaises(FrozenInstanceError):
            self.q.known_at = 610
        for evaluator in (reference_value, sqlite_value):
            with self.assertRaises(ContractError):
                evaluator(self.base.history, self.q)
            with self.assertRaises(ContractError):
                evaluator(self.base, {})

    def test_conflicting_source_and_delivery_fail_atomically(self):
        before = self.base
        valid = Delivery("new", Revision("N", 1, "C1", 590, 591, 2), 591)
        conflicts = [Delivery("bad", replace(self.base.history[0], amount=21), 610),
                     Delivery("bad", replace(self.base.history[0], available_at=590), 610),
                     replace(self.base.deliveries[0], delivered_at=610)]
        for conflict in conflicts:
            with self.assertRaises(ContractError):
                ingest(self.base, [valid, conflict])
            self.assertIs(self.base, before)
            self.assertEqual(len(self.base.history), 5)
            self.assertBoth(self.base, self.q, 50)

    def test_source_mutations_and_decreasing_availability_reject(self):
        a = Revision("A", 1, "C1", 550, 560, 20)
        for changed in (Revision("A", 2, "C2", 550, 561, 20),
                        Revision("A", 2, "C1", 551, 561, 20),
                        Revision("A", 2, "C1", 550, 559, 20)):
            with self.assertRaises(ContractError):
                ledger(a, changed)

    def test_json_shape_and_conflicts_cannot_bypass_canonicalization(self):
        raw = json.loads((ROOT / "fixtures/base.json").read_text())
        raw["deliveries"].append(dict(raw["deliveries"][0], delivery_id="retry"))
        self.assertEqual(len(ledger_from_dict(raw).history), 5)
        raw["deliveries"][-1] = json.loads(json.dumps(raw["deliveries"][-1]))
        raw["deliveries"][-1]["record"]["amount"] = 21
        with self.assertRaises(ContractError):
            ledger_from_dict(raw)
        with self.assertRaises(ContractError):
            ledger_from_dict({"schema_version": 1, "allow_restore": False, "deliveries": [], "extra": 1})

    def test_sql_does_not_call_reference_selection_or_evaluation(self):
        with patch("historical_lab.reference_value", side_effect=AssertionError("not independent")), \
             patch("historical_lab.reference_selection", side_effect=AssertionError("not independent")):
            self.assertEqual(sqlite_value(self.base, self.q), 50)

    def test_numeric_domain_and_aggregate_overflow_match(self):
        huge = ledger(Revision("X", 1, "C1", 590, 590, SQLITE_MAX + 1))
        overflow = ledger(Revision("X", 1, "C1", 590, 590, SQLITE_MAX),
                          Revision("Y", 1, "C1", 591, 591, 1))
        exact = ledger(Revision("X", 1, "C1", 590, 590, SQLITE_MAX))
        self.assertBoth(exact, self.q, SQLITE_MAX)
        for evaluator in (reference_value, sqlite_value):
            for data in (huge, overflow):
                with self.assertRaises(ContractError):
                    evaluator(data, self.q)
        self.assertBoth(overflow, replace(self.q, history_known=False), None)

    def test_cli_runs_sql_and_reports_unknown_and_validation(self):
        def run(*args):
            return subprocess.run([sys.executable, str(ROOT / "sqlite_lab.py"), *args],
                                  cwd=ROOT.parent, capture_output=True, text=True)
        self.assertEqual(run().stdout, "50\n")
        self.assertEqual(run("--known-at", "610").stdout, "85\n")
        self.assertEqual(run("--unknown-history").stdout, "null\n")
        bad = run("--known-at", "599")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("contract error", bad.stderr)
        report = subprocess.run([sys.executable, str(ROOT / "historical_lab.py")],
                                cwd=ROOT.parent, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(report.stdout)["queries"]["D1"]["sqlite"], 50)


if __name__ == "__main__":
    unittest.main()
