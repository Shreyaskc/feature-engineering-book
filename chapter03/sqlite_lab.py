"""Independent SQL reconstruction; run directly without the reference evaluator.

The canonical ledger is the trust boundary. Never insert raw deliveries and
hope SQL DISTINCT will resolve conflicting identities. SQLite 3.25+ is needed
for ROW_NUMBER; the verified runtime version is recorded by verify_lab.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3

from foundations_lab import ContractError, Ledger, ledger_from_dict
from historical_lab import Query, _checked_ledger

ROOT = Path(__file__).resolve().parent
SQL = (ROOT / "selected_spend.sql").read_text(encoding="utf-8")
SCHEMA = """CREATE TABLE revisions (
    event_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    customer_id TEXT NOT NULL,
    event_time INTEGER NOT NULL,
    available_at INTEGER NOT NULL,
    amount INTEGER,
    op TEXT NOT NULL,
    PRIMARY KEY (event_id, revision)
);"""


def connect(ledger: Ledger, query: Query) -> sqlite3.Connection:
    _checked_ledger(ledger, query)
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(SCHEMA)
        connection.executemany("INSERT INTO revisions VALUES (?, ?, ?, ?, ?, ?, ?)",
                               [(r.event_id, r.revision, r.customer_id,
                                 r.event_time, r.available_at, r.amount, r.op)
                                for r in ledger.history])
    except BaseException:
        connection.close()
        raise
    return connection


def value(ledger: Ledger, query: Query) -> int | None:
    connection = connect(ledger, query)
    try:
        return connection.execute(SQL, query.parameters()).fetchone()[0]
    except sqlite3.OperationalError as error:
        if "integer overflow" in str(error):
            raise ContractError("aggregate exceeds SQLite signed 64-bit integer range") from error
        raise
    finally:
        connection.close()


def selected(ledger: Ledger, query: Query) -> list[tuple]:
    """A second result shape verifies identities as well as aggregate values."""
    connection = connect(ledger, query)
    try:
        return connection.execute("""
            WITH ranked AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY event_id ORDER BY revision DESC
                ) AS position
                FROM revisions WHERE available_at <= :known_at
            )
            SELECT event_id, revision, amount, op
            FROM ranked WHERE position = 1 ORDER BY event_id
        """, query.parameters()).fetchall()
    finally:
        connection.close()


def contributors(ledger: Ledger, query: Query) -> list[tuple]:
    """Eligible active rows inside this customer/window, even if coverage is unknown.

    With unknown coverage these are partial evidence, never proof of a total.
    This SQL is deliberately independent of Python's reference row filtering.
    """
    connection = connect(ledger, query)
    try:
        return connection.execute("""
            WITH ranked AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY event_id ORDER BY revision DESC
                ) AS position
                FROM revisions WHERE available_at <= :known_at
            )
            SELECT event_id, revision, amount, op FROM ranked
            WHERE position = 1 AND customer_id = :customer_id
              AND event_time >= :window_start AND event_time < :window_end
              AND op = 'upsert'
            ORDER BY event_id
        """, query.parameters()).fetchall()
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=ROOT / "fixtures/base.json")
    parser.add_argument("--customer", default="C1")
    parser.add_argument("--window-start", type=int, default=540)
    parser.add_argument("--window-end", type=int, default=600)
    parser.add_argument("--known-at", type=int, default=600)
    parser.add_argument("--unknown-history", action="store_true")
    parser.add_argument("--selected", action="store_true")
    args = parser.parse_args()
    try:
        # Input always passes through the unchanged source-identity ledger.
        ledger = ledger_from_dict(json.loads(args.fixture.read_text(encoding="utf-8")))
        query = Query(args.customer, args.window_start, args.window_end,
                      args.known_at, not args.unknown_history)
        result = selected(ledger, query) if args.selected else value(ledger, query)
    except (ContractError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, f"contract error: {error}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
