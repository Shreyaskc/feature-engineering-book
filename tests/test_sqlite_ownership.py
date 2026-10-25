"""Retained real SQLite connections prove ownership without garbage collection."""
from contextlib import redirect_stdout
import importlib.util
from io import StringIO
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
REAL_CONNECT = sqlite3.connect


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


readiness = load_module('ownership_readiness', ROOT/'prerequisites/readiness_lab.py')
chapter4 = load_module('ownership_chapter4', ROOT/'chapter04/chapter4.py')
verification = load_module('ownership_verifier', ROOT/'verify_all.py')
sys.path.insert(0, str(ROOT/'chapter03'))
try:
    exports = load_module('ownership_export_tests', ROOT/'chapter03/test_export_sql.py')
finally:
    sys.path.pop(0)


class RetainedConnection(sqlite3.Connection):
    """Only SQL-error injection is changed; storage and transaction exit are real."""
    fail_prefix = None
    close_error = False

    def execute(self, sql, *args, **kwargs):
        if self.fail_prefix and sql.lstrip().startswith(self.fail_prefix):
            return super().execute('SELECT * FROM ownership_missing_table')
        return super().execute(sql, *args, **kwargs)

    def close(self):
        super().close()
        if self.close_error:
            raise RuntimeError('deliberate close error after real SQLite closure')


class SQLiteOwnershipTests(unittest.TestCase):
    def assertClosed(self, connection):
        # The strong reference remains alive; failure cannot be hidden by GC.
        with self.assertRaisesRegex(sqlite3.ProgrammingError, 'closed database'):
            sqlite3.Connection.execute(connection, 'SELECT 1')

    def owned_call(self, module, invoke, *, fail_prefix=None, expected_output=None,
                   rollback_expected=True):
        with tempfile.TemporaryDirectory(prefix='sqlite-ownership-') as folder:
            file = Path(folder)/'retained.sqlite'
            db = REAL_CONNECT(file, factory=RetainedConnection)
            db.execute('CREATE TABLE ownership_probe(value INT)')
            db.execute('INSERT INTO ownership_probe VALUES (1)')
            db.fail_prefix = fail_prefix
            try:
                with patch.object(module.sqlite3, 'connect', return_value=db):
                    if fail_prefix:
                        with self.assertRaises(sqlite3.OperationalError):
                            invoke()
                    else:
                        output = invoke()
                        if expected_output is not None:
                            self.assertEqual(output, expected_output)
                self.assertClosed(db)
                # Use another real connection to observe committed storage.
                check = REAL_CONNECT(file)
                try:
                    count = check.execute('SELECT COUNT(*) FROM ownership_probe').fetchone()[0]
                    self.assertEqual(count, 0 if fail_prefix and rollback_expected else 1)
                finally:
                    check.close()
            finally:
                # Even a failing baseline regression cleans up explicitly.
                sqlite3.Connection.close(db)

    def test_readiness_success_closes_and_commits(self):
        expected = json.loads((ROOT/'prerequisites/expected_output.json').read_text())['sql_previews']
        self.owned_call(readiness, lambda: readiness.sql_example(readiness.fixture()), expected_output=expected)

    def test_readiness_sql_error_closes_and_rolls_back(self):
        self.owned_call(readiness, lambda: readiness.sql_example(readiness.fixture()), fail_prefix='CREATE TABLE revisions')

    def test_environment_success_closes_and_commits(self):
        self.owned_call(verification, verification.environment_check)

    def test_environment_sql_error_closes_and_rolls_back(self):
        self.owned_call(verification, verification.environment_check, fail_prefix='SELECT row_number()')

    def test_join_success_closes_and_preserves_results(self):
        self.owned_call(chapter4, chapter4.join_demo,
                        expected_output=([('D1', 50), ('D1', 95), ('D2', 50), ('D2', 95)], [('D1', 50), ('D2', 95)]))

    def test_join_sql_error_closes_and_preserves_script_transaction_behavior(self):
        # executescript commits any pending legacy transaction before its script.
        self.owned_call(chapter4, chapter4.join_demo, fail_prefix='SELECT d.decision_id', rollback_expected=False)

    def refresher_call(self, fail_prefix=None):
        item = next(x for x in json.loads((ROOT/'prerequisites/book_refresher_examples.json').read_text())
                    if x['id']=='refresher_sql_filtering')
        def invoke():
            output = StringIO()
            with redirect_stdout(output):
                exec(compile(item['code'], item['id'], 'exec'), {})
            return output.getvalue()
        self.owned_call(readiness, invoke, fail_prefix=fail_prefix, expected_output=item['expected_stdout'])

    def test_actual_sql_refresher_success_closes_and_commits(self):
        self.refresher_call()

    def test_actual_sql_refresher_sql_error_closes_and_rolls_back(self):
        self.refresher_call('SELECT SUM(amount)')

    def export_fixture_failure(self, close_failure):
        data = exports.ledger(exports.Revision('A', 1, 'C1', 550, 551, 20),
                              exports.Revision('C', 1, 'C1', 585, 586, 30))
        query = exports.Query('C1', 540, 600, 600)
        bound = exports.connect(data, query)
        owned = []
        acquired_bound = False
        def get_bound(*args):
            nonlocal acquired_bound
            acquired_bound = True
            return bound
        def get_exported(*args, **kwargs):
            if not acquired_bound:
                return REAL_CONNECT(*args, **kwargs)
            if not close_failure:
                raise sqlite3.OperationalError('deliberate second acquisition error')
            db = REAL_CONNECT(':memory:', factory=RetainedConnection)
            db.close_error = True
            owned.append(db)
            return db
        try:
            with patch.object(exports, 'connect', side_effect=get_bound), patch.object(exports.sqlite3, 'connect', side_effect=get_exported):
                with self.assertRaisesRegex(RuntimeError if close_failure else sqlite3.OperationalError,
                                            'deliberate close error' if close_failure else 'second acquisition error'):
                    exports.ExportTests().assertExportMatches(data, query, 50)
            self.assertClosed(bound)
            for db in owned:
                self.assertClosed(db)
        finally:
            sqlite3.Connection.close(bound)
            for db in owned:
                sqlite3.Connection.close(db)

    def test_export_fixture_second_acquisition_failure_closes_first(self):
        self.export_fixture_failure(False)

    def test_export_fixture_close_error_does_not_strand_first(self):
        self.export_fixture_failure(True)


if __name__ == '__main__':
    unittest.main()
