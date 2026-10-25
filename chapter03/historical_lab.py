"""Decision-specific reconstruction over the unchanged Chapter 2 ledger.

Synthetic integer minutes and spend units; Python standard library only.
Availability is established source usability, not this replay's arrival time.
"""
from __future__ import annotations

from dataclasses import dataclass
import json

from foundations_lab import ContractError, Ledger, Revision, load_fixture

SQLITE_MAX = 2**63 - 1


def _integer(value: object, name: str) -> None:
    if type(value) is not int or not 0 <= value <= SQLITE_MAX:
        raise ContractError(f"{name} must be an integer in [0, 2**63 - 1]")


@dataclass(frozen=True)
class Query:
    """An event window plus an independent source-knowledge cutoff.

    Known empty history is zero; explicitly unknown relevant history is None.
    The finite integer range keeps Python and SQLite's numeric domains equal.
    """
    customer_id: str
    window_start: int
    window_end: int
    known_at: int
    history_known: bool = True

    def __post_init__(self) -> None:
        if (not isinstance(self.customer_id, str) or not self.customer_id
                or self.customer_id.strip() != self.customer_id):
            raise ContractError("customer_id must be a nonempty, trimmed string")
        for name in ("window_start", "window_end", "known_at"):
            _integer(getattr(self, name), name)
        if type(self.history_known) is not bool:
            raise ContractError("history_known must be True or False")
        if not self.window_start < self.window_end <= self.known_at:
            raise ContractError("require window_start < window_end <= known_at")

    def parameters(self) -> dict:
        return {"customer_id": self.customer_id,
                "window_start": self.window_start,
                "window_end": self.window_end, "known_at": self.known_at,
                "history_known": int(self.history_known)}


def _checked_ledger(ledger: Ledger, query: Query) -> None:
    """Shared input contract, never shared selection or arithmetic."""
    if not isinstance(ledger, Ledger):
        raise ContractError("ledger must be a canonical Ledger")
    if not isinstance(query, Query):
        raise ContractError("query must be a Query")
    # Foundation validation handles source identity and revision invariants.
    # This extra domain check applies to both implementations identically.
    for row in ledger.history:
        for name in ("revision", "event_time", "available_at"):
            _integer(getattr(row, name), name)
        if row.amount is not None:
            _integer(row.amount, "amount")


def reference_selection(ledger: Ledger, query: Query) -> tuple[Revision, ...]:
    """First eligible versions; then greatest revision per business event."""
    _checked_ledger(ledger, query)
    chosen: dict[str, Revision] = {}
    for row in ledger.history:
        if row.available_at <= query.known_at:
            old = chosen.get(row.event_id)
            if old is None or row.revision > old.revision:
                chosen[row.event_id] = row
    return tuple(chosen[key] for key in sorted(chosen))


def reference_value(ledger: Ledger, query: Query) -> int | None:
    selected = reference_selection(ledger, query)
    if not query.history_known:
        return None
    total = sum(row.amount for row in selected
                if row.customer_id == query.customer_id
                and query.window_start <= row.event_time < query.window_end
                and row.op == "upsert")
    if total > SQLITE_MAX:
        raise ContractError("aggregate exceeds SQLite signed 64-bit integer range")
    return total


def explain(ledger: Ledger, query: Query) -> dict:
    """A selected tombstone stays visible in the trace and contributes nothing."""
    rows = []
    for row in reference_selection(ledger, query):
        if row.customer_id != query.customer_id:
            reason = "different customer"
        elif row.op == "delete":
            reason = "deleted"
        elif not query.window_start <= row.event_time < query.window_end:
            reason = "outside event window"
        else:
            reason = "included"
        rows.append({"event_id": row.event_id, "revision": row.revision,
                     "event_time": row.event_time,
                     "available_at": row.available_at, "op": row.op,
                     "amount": row.amount, "reason": reason})
    return {"value": reference_value(ledger, query),
            "history_known": query.history_known, "selected": rows,
            "coverage_note": ("known relevant history" if query.history_known
                              else "unknown relevant history; rows are partial evidence")}


def sqlite_value(ledger: Ledger, query: Query) -> int | None:
    # Lazy import keeps the SQL runner independently executable.
    from sqlite_lab import value
    return value(ledger, query)


def wrong_latest_then_availability(ledger: Ledger, query: Query) -> int | None:
    """INTENTIONALLY WRONG: latest overall erases an eligible older version."""
    _checked_ledger(ledger, query)
    latest: dict[str, Revision] = {}
    for row in ledger.history:
        if row.event_id not in latest or row.revision > latest[row.event_id].revision:
            latest[row.event_id] = row
    if not query.history_known:
        return None
    return sum(row.amount for row in latest.values()
               if row.available_at <= query.known_at and row.op == "upsert"
               and row.customer_id == query.customer_id
               and query.window_start <= row.event_time < query.window_end)


def wrong_ignore_availability(ledger: Ledger, query: Query) -> int | None:
    """INTENTIONALLY WRONG: later source knowledge leaks into an old decision."""
    _checked_ledger(ledger, query)
    latest: dict[str, Revision] = {}
    for row in ledger.history:
        if row.event_id not in latest or row.revision > latest[row.event_id].revision:
            latest[row.event_id] = row
    if not query.history_known:
        return None
    return sum(row.amount for row in latest.values()
               if row.op == "upsert" and row.customer_id == query.customer_id
               and query.window_start <= row.event_time < query.window_end)


def example_report() -> dict:
    ledger = load_fixture()
    queries = {"D1": Query("C1", 540, 600, 600),
               "D2": Query("C1", 550, 610, 610),
               "fixed_known_610": Query("C1", 540, 600, 610)}
    return {"queries": {name: {"reference": reference_value(ledger, query),
                               "sqlite": sqlite_value(ledger, query),
                               "explanation": explain(ledger, query)}
                        for name, query in queries.items()},
            "wrong_latest_first": wrong_latest_then_availability(ledger, queries["D1"]),
            "wrong_future_knowledge": wrong_ignore_availability(ledger, queries["D1"])}


if __name__ == "__main__":
    # Run through the canonical module so Query has one identity when the
    # independent SQL module imports it; __main__.Query would be a second type.
    from historical_lab import example_report as _report
    print(json.dumps(_report(), indent=2, sort_keys=True))
