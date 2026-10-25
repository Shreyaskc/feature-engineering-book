"""Execute exported SQL and compare values and stored identities with binding."""
from contextlib import closing
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from export_sql import standalone_script
from foundations_lab import ContractError, Delivery, Ledger, Revision
from historical_lab import Query, reference_value
from run_sql_file import run_file
from sqlite_lab import SQL, connect, value


def ledger(*rows):
    return Ledger(tuple(Delivery(f"d-{i}", row, row.available_at)
                        for i, row in enumerate(rows)))


class ExportTests(unittest.TestCase):
    def assertExportMatches(self, data, query, expected):
        """Use the shipped plain-SQL runner, plus a lossless source-row check."""
        self.assertEqual(reference_value(data, query), expected)
        self.assertEqual(value(data, query), expected)
        script = standalone_script(data, query)
        with tempfile.TemporaryDirectory(prefix="chapter3-export-test-") as raw:
            path = Path(raw) / "export.sql"
            path.write_text(script, encoding="utf-8")
            self.assertEqual(run_file(path), ["NULL" if expected is None else str(expected)])
        # Equal totals alone could hide merged, truncated, or altered identities.
        with closing(connect(data, query)) as bound, closing(sqlite3.connect(":memory:")) as exported:
            exported.executescript(script)
            rows = "SELECT * FROM revisions ORDER BY event_id, revision"
            self.assertEqual(exported.execute(rows).fetchall(), bound.execute(rows).fetchall())
        return script

    def test_every_parameter_token_is_preserved_inside_customer_ids(self):
        for name in Query("C1", 540, 600, 600).parameters():
            token = ":" + name
            for customer in (token, "prefix" + token, token + "_suffix", token + "99",
                             token + ":tail", token + token, "O'Neil" + token,
                             "\"quoted\"" + token):
                with self.subTest(customer=customer):
                    data = ledger(Revision("event", 1, customer, 550, 551, 7))
                    self.assertExportMatches(data, Query(customer, 540, 600, 600), 7)

    def test_combined_tokens_and_sql_looking_strings_remain_data(self):
        tokens = ":customer_id:window_start:window_end:known_at:history_known"
        for customer in (tokens, tokens[::-1], "prefix" + tokens + "suffix",
                         "x'; DROP TABLE revisions; --" + tokens,
                         "x' OR 1=1 --" + tokens, "客户🧪" + tokens,
                         "x'\n;/* :known_at */" + tokens):
            with self.subTest(customer=customer):
                data = ledger(Revision("chosen", 1, customer, 550, 551, 7),
                              Revision("other", 1, "unrelated", 550, 551, 11))
                query = Query(customer, 540, 600, 600)
                self.assertExportMatches(data, query, 7)
                self.assertExportMatches(data, replace(query, history_known=False), None)

    def test_nul_customers_are_distinct_and_lossless(self):
        customers = ("C1", "C1\x00suffix", "\x00C1", "C1\x00",
                     "C1\x00\x00suffix", "客户\x00🧪':window_start")
        data = ledger(*(Revision(f"e-{i}", 1, customer, 550, 551, 7 + i)
                        for i, customer in enumerate(customers)))
        for i, customer in enumerate(customers):
            with self.subTest(customer=customer):
                script = self.assertExportMatches(data, Query(customer, 540, 600, 600), 7 + i)
                self.assertNotIn("\x00", script)
        self.assertExportMatches(data, Query("C1\x00missing", 540, 600, 600), 0)

    def test_nul_event_ids_preserve_distinct_versions_and_tombstones(self):
        data = ledger(Revision("event", 1, "C1", 550, 551, 7),
                      Revision("event\x00suffix", 1, "C1", 550, 551, 11),
                      Revision("event\x00suffix", 2, "C1", 550, 605, None, "delete"),
                      Revision("\x00客户🧪':known_at", 1, "C1", 550, 551, 13))
        self.assertExportMatches(data, Query("C1", 540, 600, 600), 31)
        self.assertExportMatches(data, Query("C1", 540, 600, 610), 20)

    def test_quoted_unicode_and_multiline_event_ids_round_trip(self):
        events = ("O'Neil", ':customer_id"', "客户🧪", "x'\n;--:window_end", "[:known_at]")
        data = ledger(*(Revision(event, 1, "C1", 550, 551, i + 1)
                        for i, event in enumerate(events)))
        self.assertExportMatches(data, Query("C1", 540, 600, 600), 15)

    def test_runner_preserves_distinct_carriage_return_and_newline_ids(self):
        customers = ("prefix\rvalue", "prefix\nvalue", "prefix\r\nvalue")
        data = ledger(*(Revision("event" + customer, 1, customer, 550, 551, 7 + i)
                        for i, customer in enumerate(customers)))
        for i, customer in enumerate(customers):
            with self.subTest(customer=customer):
                self.assertExportMatches(data, Query(customer, 540, 600, 600), 7 + i)

    def test_template_literals_identifiers_and_comments_are_not_parameters(self):
        query = Query(":window_start", 540, 600, 600)
        data = ledger(Revision("event", 1, query.customer_id, 550, 551, 7))
        protected = "'upsert' AND ':known_at' = ':known_at'"
        template = SQL.replace("'upsert'", protected).replace("AS spend", 'AS ":window_end"')
        template = "/* :customer_id :history_known */\n-- :window_start\n" + template
        with patch("export_sql.SQL", template):
            script = self.assertExportMatches(data, query, 7)
        self.assertIn(protected, script)
        self.assertIn('AS ":window_end"', script)
        self.assertIn("/* :customer_id :history_known */", script)
        self.assertIn("-- :window_start", script)

    def test_undeclared_template_parameters_fail_without_prefix_substitution(self):
        for parameter in (":known_at_suffix", ":customer_id99", ":window_start$tail", ":missing"):
            with self.subTest(parameter=parameter), patch("export_sql.SQL", SQL.replace(":known_at", parameter)):
                with self.assertRaisesRegex(ContractError, "standalone SQL template has undeclared parameter"):
                    standalone_script(Ledger(), Query("C1", 540, 600, 600))

    def test_invalid_operations_remain_rejected_by_foundation_validation(self):
        for operation in ("upsert\x00suffix", "delete\x00", ":known_at"):
            with self.subTest(operation=operation), self.assertRaisesRegex(ContractError, "op must be"):
                Revision("event", 1, "C1", 550, 551, 7, operation)


if __name__ == "__main__":
    unittest.main()
