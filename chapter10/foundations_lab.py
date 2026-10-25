"""Small, synthetic feature-contract and source-identity lab.

Python 3.12; standard library only. Verified on Python 3.12.14; other
versions are untested. Integer minutes and synthetic spend units
deliberately avoid currency conversion and floating-point rounding.
No predictive model, database, network service, or feature store runs here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Iterable


class ContractError(ValueError):
    """Input violates a declared teaching-lab contract."""


def _integer(value: object, name: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ContractError(f"{name} must be an integer >= {minimum}")


def _identity(value: object, name: str) -> None:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ContractError(f"{name} must be a nonempty, trimmed string")


def _boolean(value: object, name: str) -> None:
    if type(value) is not bool:
        raise ContractError(f"{name} must be True or False")


@dataclass(frozen=True)
class Revision:
    """An immutable source version, independent of transport deliveries.

    event_id is globally unique in this tiny fixture. Real systems should
    use a documented namespace, such as (source_system, event_id).
    available_at is first source availability, never a retry arrival time.
    """

    event_id: str
    revision: int
    customer_id: str
    event_time: int
    available_at: int
    amount: int | None
    op: str = "upsert"

    def __post_init__(self) -> None:
        _identity(self.event_id, "event_id")
        _integer(self.revision, "revision", 1)
        _identity(self.customer_id, "customer_id")
        _integer(self.event_time, "event_time")
        _integer(self.available_at, "available_at")
        if self.available_at < self.event_time:
            raise ContractError("availability cannot precede event time")
        if self.op not in ("upsert", "delete"):
            raise ContractError("op must be 'upsert' or 'delete'")
        if self.op == "delete":
            if self.amount is not None:
                raise ContractError("a deletion must have amount=None")
        else:
            _integer(self.amount, "amount")


@dataclass(frozen=True)
class Delivery:
    """One transport observation of a source revision."""

    delivery_id: str
    record: Revision
    delivered_at: int

    def __post_init__(self) -> None:
        _identity(self.delivery_id, "delivery_id")
        if not isinstance(self.record, Revision):
            raise ContractError("record must be a Revision")
        _integer(self.delivered_at, "delivered_at")
        if self.delivered_at < self.record.available_at:
            raise ContractError("delivery cannot precede availability")


def _history(records: Iterable[Revision], *,
             allow_restore: bool) -> tuple[Revision, ...]:
    """Validate source invariants and return stable source-key order.

    This receives unique source versions. It rejects duplicates rather
    than guessing whether the caller intended transport deduplication.
    """
    try:
        records = tuple(records)
    except TypeError as error:
        raise ContractError("history must be iterable") from error
    seen: set[tuple[str, int]] = set()
    for row in records:
        if not isinstance(row, Revision):
            raise ContractError("history must contain Revision records")
        key = (row.event_id, row.revision)
        if key in seen:
            raise ContractError(f"duplicate canonical source version: {key}")
        seen.add(key)
    ordered = tuple(sorted(records,
                           key=lambda row: (row.event_id, row.revision)))
    previous: Revision | None = None
    for row in ordered:
        if previous is not None and row.event_id == previous.event_id:
            if (row.customer_id, row.event_time) != (
                    previous.customer_id, previous.event_time):
                raise ContractError("event customer and time are immutable")
            if row.available_at < previous.available_at:
                raise ContractError("availability must not decrease by revision")
            if previous.op == "delete" and row.op == "upsert":
                if not allow_restore:
                    raise ContractError("restoration requires allow_restore=True")
        previous = row
    return ordered


def _normalize(deliveries: Iterable[Delivery], *, allow_restore: bool
               ) -> tuple[tuple[Delivery, ...], tuple[Revision, ...]]:
    """Deduplicate both identities, then validate the entire candidate."""
    _boolean(allow_restore, "allow_restore")
    try:
        deliveries = tuple(deliveries)
    except TypeError as error:
        raise ContractError("deliveries must be iterable") from error
    by_delivery: dict[str, Delivery] = {}
    by_source: dict[tuple[str, int], Revision] = {}
    for delivery in deliveries:
        if not isinstance(delivery, Delivery):
            raise ContractError("a batch must contain Delivery records")
        old_delivery = by_delivery.get(delivery.delivery_id)
        if old_delivery is not None and old_delivery != delivery:
            raise ContractError("delivery_id reused with conflicting payload")
        by_delivery[delivery.delivery_id] = delivery
        row = delivery.record
        source_key = (row.event_id, row.revision)
        old_record = by_source.get(source_key)
        if old_record is not None and old_record != row:
            raise ContractError("source revision reused with conflicting payload")
        by_source[source_key] = row
    history = _history(by_source.values(), allow_restore=allow_restore)
    retained = tuple(sorted(by_delivery.values(),
                            key=lambda delivery: delivery.delivery_id))
    return retained, history


@dataclass(frozen=True)
class Ledger:
    """An append-only teaching ledger represented by immutable snapshots.

    Equal delivery retries are idempotent. Distinct delivery IDs remain
    in .deliveries, but equal source versions occur once in .history.
    Sorting makes full replay independent of input order. allow_restore
    is the explicit contract for accepting an upsert after a tombstone.
    """

    deliveries: tuple[Delivery, ...] = ()
    allow_restore: bool = False
    history: tuple[Revision, ...] = field(init=False)

    def __post_init__(self) -> None:
        deliveries, history = _normalize(
            self.deliveries, allow_restore=self.allow_restore)
        object.__setattr__(self, "deliveries", deliveries)
        object.__setattr__(self, "history", history)


def ingest(ledger: Ledger, batch: Iterable[Delivery]) -> Ledger:
    """Return a new snapshot, or reject the whole batch atomically.

    No accepted input is mutated. This function has no storage or network
    effects; its atomicity is that of a pure in-memory return-or-raise call.
    It makes no claim about distributed transactions or exactly-once IO.
    """
    if not isinstance(ledger, Ledger):
        raise ContractError("ledger must be a Ledger")
    try:
        candidate = tuple(batch)
    except TypeError as error:
        raise ContractError("batch must be iterable") from error
    return Ledger(ledger.deliveries + candidate,
                  allow_restore=ledger.allow_restore)


def selected_revisions(history: Iterable[Revision], *,
                       known_at: int) -> tuple[Revision, ...]:
    """Select greatest eligible revision per event, including tombstones.

    A query reads already-authorized history. Restoration permission is
    enforced when building the Ledger, not by this read-only calculation.
    Revision gaps are allowed. Delivery order and delivered_at do not
    participate in this source-availability reference calculation.
    """
    _integer(known_at, "known_at")
    ordered = _history(history, allow_restore=True)
    latest: dict[str, Revision] = {}
    for row in ordered:
        if row.available_at <= known_at:
            latest[row.event_id] = row
    return tuple(latest.values())


def spend_in_window(history: Iterable[Revision], customer_id: str, *,
                    window_start: int, window_end: int, known_at: int,
                    history_known: bool = True) -> int | None:
    """Sum known nondeleted spend in [window_start, window_end).

    Known empty history yields zero. An explicitly unknown relevant
    history yields None, even if the supplied partial rows sum to zero.
    Do not infer history_known from whether any records were returned.
    """
    _identity(customer_id, "customer_id")
    _integer(window_start, "window_start")
    _integer(window_end, "window_end")
    _integer(known_at, "known_at")
    _boolean(history_known, "history_known")
    if not window_start < window_end <= known_at:
        raise ContractError("require window_start < window_end <= known_at")
    selected = selected_revisions(history, known_at=known_at)
    if not history_known:
        return None
    return sum(row.amount for row in selected
               if row.customer_id == customer_id
               and window_start <= row.event_time < window_end
               and row.op == "upsert")


def spend(history: Iterable[Revision], customer_id: str, decision_at: int,
          *, window_minutes: int = 60,
          history_known: bool = True) -> int | None:
    """The Chapter 1 rolling-window feature contract.

    Current-order events at decision_at are excluded by the upper bound.
    This assumes the current order's event timestamp equals decision_at;
    earlier-dated current orders require a separate exclusion contract.
    """
    _integer(decision_at, "decision_at")
    _integer(window_minutes, "window_minutes", 1)
    if decision_at < window_minutes:
        raise ContractError("window extends before this lab's clock origin")
    return spend_in_window(
        history, customer_id, window_start=decision_at - window_minutes,
        window_end=decision_at, known_at=decision_at,
        history_known=history_known)


def _object(data: object, fields: set[str], name: str) -> dict:
    if not isinstance(data, dict) or set(data) != fields:
        raise ContractError(f"{name} must have exactly {sorted(fields)}")
    return data


def ledger_from_dict(data: object) -> Ledger:
    """Strict JSON-shape adapter; unexpected and missing fields reject."""
    data = _object(data, {"schema_version", "allow_restore", "deliveries"},
                   "fixture")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ContractError("schema_version must be integer 1")
    _boolean(data["allow_restore"], "allow_restore")
    if not isinstance(data["deliveries"], list):
        raise ContractError("deliveries must be a JSON array")
    deliveries = []
    for raw_delivery in data["deliveries"]:
        item = _object(raw_delivery,
                       {"delivery_id", "record", "delivered_at"}, "delivery")
        raw_record = _object(item["record"], {
            "event_id", "revision", "customer_id", "event_time",
            "available_at", "amount", "op"}, "record")
        deliveries.append(Delivery(item["delivery_id"],
                                   Revision(**raw_record),
                                   item["delivered_at"]))
    return Ledger(tuple(deliveries), allow_restore=data["allow_restore"])


def load_fixture(name: str = "base") -> Ledger:
    """Load a bundled synthetic fixture; extension fixtures are isolated."""
    if name not in ("base", "deletion_extension", "restoration_extension"):
        raise ContractError("unknown fixture name")
    path = Path(__file__).parent / "fixtures" / f"{name}.json"
    return ledger_from_dict(json.loads(path.read_text(encoding="utf-8")))


def example_report() -> dict:
    """Recompute every displayed example and exercise from source records."""
    base = load_fixture()
    history = base.history
    lower = Revision("K", 1, "C1", 540, 541, 5)
    upper = Revision("L", 1, "C1", 600, 600, 7)
    before_lower = Revision("K", 1, "C1", 539, 541, 5)
    inside_upper = Revision("L", 1, "C1", 599, 600, 7)
    retry = Delivery("a1-retry", history[0], 609)
    retried = ingest(base, [retry])
    deletion = load_fixture("deletion_extension")
    restoration = load_fixture("restoration_extension")

    def fixed(rows: tuple[Revision, ...], cutoff: int) -> int | None:
        return spend_in_window(rows, "C1", window_start=540,
                               window_end=600, known_at=cutoff,
                               history_known=True)

    return {
        "schema_version": 1,
        "clock": "integer synthetic minutes",
        "units": "nonnegative integer synthetic spend units",
        "decision": {"id": "D1", "customer_id": "C1", "at": 600},
        "history_known": True,
        "chapter_one": {
            "baseline_at_600": spend(history, "C1", 600),
            "lower_boundary_K_540": spend(history + (lower,), "C1", 600),
            "upper_boundary_L_600": spend(history + (upper,), "C1", 600),
            "known_empty_C9": spend(history, "C9", 600, history_known=True),
            "unknown_relevant_history": spend(history, "C1", 600,
                                               history_known=False),
        },
        "window_comparison": {
            "rolling_at_610": spend(history, "C1", 610),
            "fixed_540_600_known_at_610": fixed(history, 610),
        },
        "exercises": {
            "K_at_539": spend(history + (before_lower,), "C1", 600),
            "L_at_599_available_600": spend(history + (inside_upper,), "C1", 600),
            "window_width_30_at_600": spend(history, "C1", 600, window_minutes=30),
            "restoration_fixed_window_by_cutoff": {
                str(cutoff): fixed(restoration.history, cutoff)
                for cutoff in (600, 610, 619, 620)},
        },
        "identity": {
            "base_deliveries": len(base.deliveries),
            "base_source_versions": len(history),
            "retried_deliveries": len(retried.deliveries),
            "retried_source_versions": len(retried.history),
            "retry_preserves_available_at": retried.history[0].available_at,
            "retry_preserves_original_value": spend(retried.history, "C1", 600),
            "identical_batch_is_idempotent": ingest(base, base.deliveries) == base,
            "reversed_replay_is_identical": Ledger(tuple(reversed(base.deliveries)))
                                            == base,
        },
        "deletion_extension": {
            "original_at_600": spend(deletion.history, "C1", 600),
            "rolling_at_610": spend(deletion.history, "C1", 610),
            "fixed_540_600_known_at_620": fixed(deletion.history, 620),
        },
        "restoration_extension": {
            "allow_restore": restoration.allow_restore,
            "original_at_600": spend(restoration.history, "C1", 600),
            "rolling_at_610": spend(restoration.history, "C1", 610),
            "fixed_540_600_known_at_620": fixed(restoration.history, 620),
        },
        "base_selected_at_600": [
            {"event_id": row.event_id, "revision": row.revision,
             "amount": row.amount}
            for row in selected_revisions(history, known_at=600)],
    }


if __name__ == "__main__":
    print(json.dumps(example_report(), indent=2, sort_keys=True))
