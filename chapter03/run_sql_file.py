"""Execute a self-contained SQL script using Python's standard-library SQLite.

No reference evaluator, Query object, foundation module, or fixture is imported.
The bundled script was exported only after foundation ledger validation. This
runner is an execution aid, not a safe importer for unvalidated source records.
The same plain SQL file is also usable by a separately installed SQLite shell.
"""
import argparse
from pathlib import Path
import sqlite3


def run_file(path: Path) -> list[str]:
    connection = sqlite3.connect(":memory:")
    output = []
    pending = ""
    try:
        # Text-mode universal newlines would alter CR/CRLF inside SQL literals.
        for line in path.read_bytes().decode("utf-8").splitlines(keepends=True):
            pending += line
            if sqlite3.complete_statement(pending):
                cursor = connection.execute(pending)
                if cursor.description:
                    output.extend("|".join("NULL" if value is None else str(value)
                                           for value in row) for row in cursor)
                pending = ""
        if pending.strip():
            raise ValueError("incomplete SQL statement")
    finally:
        connection.close()
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", nargs="?", type=Path,
                        default=Path(__file__).with_name("standalone_example.sql"))
    args = parser.parse_args()
    for value in run_file(args.script):
        print(value)
