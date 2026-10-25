"""Fixed discriminating expectations for the independent generated oracle."""

from copy import deepcopy
import unittest

from randomized_checks import raw_oracle, run_checks


def delivery(event: str, revision: int, event_time: int, available: int,
             amount: int | None, *, customer: str = "C1",
             delivery_id: str | None = None, delivered_at: int | None = None
             ) -> dict:
    return {"delivery_id": delivery_id or f"{event}-r{revision}",
            "delivered_at": available if delivered_at is None else delivered_at,
            "record": {"event_id": event, "revision": revision,
                       "customer_id": customer, "event_time": event_time,
                       "available_at": available, "amount": amount,
                       "op": "delete" if amount is None else "upsert"}}


def fixture(*deliveries: dict) -> dict:
    return {"schema_version": 1, "allow_restore": False,
            "deliveries": list(deliveries)}


class IndependentOracleTests(unittest.TestCase):
    def query(self, data: dict, **overrides) -> int | None:
        arguments = {"customer_id": "C1", "decision_at": 600,
                     "window_minutes": 60, "history_known": True}
        arguments.update(overrides)
        return raw_oracle(data, **arguments)

    def test_original_example_is_fifty(self):
        data = fixture(delivery("A", 1, 550, 551, 20),
                       delivery("B", 1, 575, 607, 40),
                       delivery("C", 1, 585, 586, 30),
                       delivery("C", 2, 585, 605, 25),
                       delivery("D", 1, 602, 603, 10))
        self.assertEqual(self.query(data), 50)
        self.assertEqual(self.query(data, decision_at=610), 95)

    def test_half_open_boundaries_have_fixed_expectation(self):
        data = fixture(delivery("before", 1, 539, 539, 2),
                       delivery("lower", 1, 540, 540, 3),
                       delivery("inside", 1, 599, 600, 5),
                       delivery("upper", 1, 600, 600, 7))
        self.assertEqual(self.query(data), 8)

    def test_filter_availability_before_maximum_revision(self):
        data = fixture(delivery("A", 1, 550, 550, 11),
                       delivery("A", 8, 550, 601, 97))
        self.assertEqual(self.query(data), 11)

    def test_availability_equality_is_eligible(self):
        data = fixture(delivery("at", 1, 550, 600, 13),
                       delivery("after", 1, 550, 601, 17))
        self.assertEqual(self.query(data), 13)

    def test_equal_availability_uses_revision_not_input_order(self):
        data = fixture(delivery("A", 9, 550, 590, 23),
                       delivery("A", 2, 550, 590, 19))
        self.assertEqual(self.query(data), 23)
        data["deliveries"].reverse()
        self.assertEqual(self.query(data), 23)

    def test_tombstones_participate_in_selection(self):
        data = fixture(delivery("A", 1, 550, 560, 31),
                       delivery("A", 2, 550, 600, None),
                       delivery("B", 1, 551, 560, 7))
        self.assertEqual(self.query(data), 7)

    def test_later_tombstone_does_not_erase_historical_value(self):
        data = fixture(delivery("A", 1, 550, 560, 31),
                       delivery("A", 2, 550, 601, None))
        self.assertEqual(self.query(data), 31)

    def test_delivery_multiplicity_and_time_do_not_change_source_value(self):
        first = delivery("A", 1, 550, 551, 37, delivered_at=700)
        retry = deepcopy(first)
        retry["delivery_id"] = "A-distinct-retry"
        retry["delivered_at"] = 900
        data = fixture(first, deepcopy(first), retry)
        self.assertEqual(self.query(data), 37)

    def test_multiple_events_sum_but_other_customers_do_not(self):
        data = fixture(delivery("A", 1, 550, 551, 41),
                       delivery("B", 1, 550, 551, 43),
                       delivery("C", 1, 550, 551, 47, customer="C2"))
        self.assertEqual(self.query(data), 84)
        self.assertEqual(self.query(data, customer_id="C2"), 47)

    def test_known_empty_zero_unknown_empty_and_unknown_partial(self):
        self.assertEqual(self.query(fixture()), 0)
        self.assertIsNone(self.query(fixture(), history_known=False))
        partial = fixture(delivery("A", 1, 550, 551, 53))
        self.assertIsNone(self.query(partial, history_known=False))
        self.assertEqual(self.query(partial, customer_id="absent"), 0)

    def test_zero_and_deleted_amounts_are_known_zero(self):
        data = fixture(delivery("A", 1, 550, 551, 0),
                       delivery("B", 1, 550, 551, 59),
                       delivery("B", 2, 550, 590, None))
        self.assertEqual(self.query(data), 0)
        self.assertIs(type(self.query(data)), int)

    def test_clock_origin_window_and_unit_window(self):
        data = fixture(delivery("A", 1, 0, 0, 61),
                       delivery("B", 1, 1, 1, 67))
        self.assertEqual(self.query(data, decision_at=1, window_minutes=1), 61)

    def test_oracle_does_not_mutate_input(self):
        data = fixture(delivery("A", 1, 550, 551, 71))
        before = deepcopy(data)
        self.assertEqual(self.query(data), 71)
        self.assertEqual(data, before)


class GeneratedHarnessTests(unittest.TestCase):
    def test_seeded_report_is_repeatable(self):
        first = run_checks(seed=29, cases=24)
        self.assertEqual(first, run_checks(seed=29, cases=24))
        self.assertEqual(first["generated_cases"], 24)
        self.assertEqual(first["original_query_comparisons"], 192)
        self.assertEqual(first["reference_oracle_comparisons"], 960)
        self.assertEqual(first["status"], "passed")
        self.assertEqual(first["metamorphic_comparisons"], {
            "shuffle": 192, "exact_delivery_replay": 192,
            "distinct_delivery_retry": 192, "later_information": 192})

    def test_invalid_generator_configuration_rejects(self):
        for cases in (0, -1, True, 1.5):
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                run_checks(cases=cases)
        with self.assertRaises(ValueError):
            run_checks(seed=True)


if __name__ == "__main__":
    unittest.main()
