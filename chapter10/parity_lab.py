"""Chapter 6: an evidence-aware, fixed-window serving-parity simulator.

Python 3.12, standard library only. Times are integer minutes on one synthetic
clock. This lab is a deterministic teaching model, not production monitoring.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import json
import math
from typing import Iterable

Number = int | float


def numeric_equal(left: Number | None, right: Number | None, *,
                  rel_tol: float = 0.0, abs_tol: float = 0.0) -> bool:
    """Compare finite numbers; missing pairs are not numeric matches.

    Core fixtures use exact integer comparison (zero tolerances). An isolated
    floating-point example opts into rel_tol=1e-9 and abs_tol=1e-12. Reject NaN,
    infinity, booleans, and negative/nonfinite tolerances rather than hiding them.
    """
    for tolerance in (rel_tol, abs_tol):
        if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool):
            raise TypeError("tolerances must be finite numbers")
        if tolerance < 0 or not math.isfinite(tolerance):
            raise ValueError("tolerances must be finite and nonnegative")
    for value in (left, right):
        if value is not None:
            _finite_number(value)
    if left is None or right is None:
        return False
    if rel_tol == 0 and abs_tol == 0:
        return left == right
    return math.isclose(left, right, rel_tol=rel_tol, abs_tol=abs_tol)


def _finite_number(value: Number) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("a feature value must be an int or float")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("NaN and infinity are not feature values")


def _same_value(left: Number | None, right: Number | None) -> bool:
    """Internal evidence-state equality; two known missing cells are equivalent."""
    return left is None and right is None or numeric_equal(left, right)


def _minute(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("times must be integer minutes")


def _identity(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value:
        raise ValueError(f"{name} must be nonempty")


def _revision(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("revisions must be positive integers")


def _source_versions(values: Iterable[tuple[str, int]]) -> tuple[tuple[str, int], ...]:
    """Freeze typed lineage without coercing equality aliases such as True/1."""
    result = []
    seen = set()
    for pair in values:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("source versions must contain (event ID, revision) pairs")
        event_id, revision = pair
        _identity(event_id, "source event ID")
        _revision(revision)
        if event_id in seen:
            raise ValueError("source versions must select one revision per event ID")
        seen.add(event_id)
        result.append((event_id, revision))
    return tuple(result)


def _instance(value: object, cls: type, name: str) -> None:
    if not isinstance(value, cls):
        raise TypeError(f"{name} must be a {cls.__name__}")


def _boolean(value: bool, name: str) -> None:
    if type(value) is not bool:
        raise TypeError(f"{name} must be a boolean")


@dataclass(frozen=True)
class FeatureKey:
    """The complete identity of a feature cell, including its fixed window."""
    feature_definition_id: str
    policy_id: str
    entity: str
    window_start: int
    window_end: int

    def __post_init__(self) -> None:
        _minute(self.window_start)
        _minute(self.window_end)
        if self.window_start >= self.window_end:
            raise ValueError("the half-open window must have positive width")
        for name in ("feature_definition_id", "policy_id", "entity"):
            _identity(getattr(self, name), name)


@dataclass(frozen=True)
class Contracts:
    policy_contract_version: str = "policy-v1"
    source_schema_version: str = "source-v1"
    publication_schema_version: str = "publication-v1"
    serving_log_schema_version: str = "serving-log-v1"
    preprocessing_id: str = "identity-v1"

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            _identity(getattr(self, name), name)


CONTRACTS = Contracts()
KEY = FeatureKey("known_spend_fixed_window_v1", "immediate_then_correct",
                 "C1", 540, 600)


@dataclass(frozen=True)
class SourceRevision:
    source_event_id: str
    revision: int
    entity: str
    event_time: int
    available_at: int
    amount: int

    def __post_init__(self) -> None:
        for minute in (self.event_time, self.available_at):
            _minute(minute)
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("source revisions must be positive integers")
        _identity(self.source_event_id, "source event ID")
        _identity(self.entity, "entity")
        if self.event_time > self.available_at:
            raise ValueError("a revision cannot be available before its event time")
        if isinstance(self.amount, bool) or not isinstance(self.amount, int) or self.amount < 0:
            raise ValueError("source amounts must be nonnegative integers")


@dataclass(frozen=True)
class Reference:
    value: Number | None
    source_versions: tuple[tuple[str, int], ...]
    history_known: bool


@dataclass(frozen=True, init=False)
class SourceHistory:
    """A canonical immutable source ledger, or explicitly unknown history.

    Equal duplicate deliveries are idempotent. Conflicting duplicate revisions,
    entity/time changes, and changed availability for a revision are rejected.
    available_at is each revision's first availability, not retry arrival time.
    Input order never determines the selected source revision.
    """
    revisions: tuple[SourceRevision, ...]
    known: bool

    def __init__(self, revisions: Iterable[SourceRevision] = (), *, known: bool = True):
        _boolean(known, "source history known")
        unique: dict[tuple[str, int], SourceRevision] = {}
        identity: dict[str, tuple[str, int]] = {}
        for row in revisions:
            _instance(row, SourceRevision, "source row")
            token = (row.source_event_id, row.revision)
            if token in unique and unique[token] != row:
                raise ValueError(f"conflicting source revision: {token}")
            stable = (row.entity, row.event_time)
            if row.source_event_id in identity and identity[row.source_event_id] != stable:
                raise ValueError(f"unstable event identity: {row.source_event_id}")
            identity[row.source_event_id] = stable
            unique[token] = row
        ordered = tuple(sorted(unique.values(), key=lambda r: (r.source_event_id, r.revision)))
        object.__setattr__(self, "revisions", ordered)
        object.__setattr__(self, "known", known)

    def reference(self, key: FeatureKey, cutoff: int) -> Reference:
        """Filter available revisions, choose highest revision, then window."""
        _instance(key, FeatureKey, "reference key")
        _minute(cutoff)
        if not self.known:
            return Reference(None, (), False)
        selected: dict[str, SourceRevision] = {}
        for row in self.revisions:
            if row.available_at <= cutoff:
                previous = selected.get(row.source_event_id)
                if previous is None or row.revision > previous.revision:
                    selected[row.source_event_id] = row
        included = [r for r in selected.values()
                    if r.entity == key.entity and key.window_start <= r.event_time < key.window_end]
        return Reference(sum(r.amount for r in included),
                         tuple(sorted((r.source_event_id, r.revision) for r in included)), True)


@dataclass(frozen=True)
class PublishedRevision:
    key: FeatureKey
    revision: int
    published_at: int
    source_cutoff: int
    value: Number
    source_versions: tuple[tuple[str, int], ...]
    contracts: Contracts = CONTRACTS

    def __post_init__(self) -> None:
        _instance(self.key, FeatureKey, "publication key")
        _instance(self.contracts, Contracts, "publication contracts")
        object.__setattr__(self, "source_versions", tuple(sorted(_source_versions(self.source_versions))))
        _finite_number(self.value)
        _minute(self.published_at)
        _minute(self.source_cutoff)
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("publication revisions must be positive integers")
        if self.source_cutoff > self.published_at:
            raise ValueError("publication cannot use future source evidence")


def build_publications(history: SourceHistory, key: FeatureKey, *,
                       initial_at: int, deadline: int) -> tuple[PublishedRevision, ...]:
    """Publish once at initial_at, then correct through the inclusive deadline.

    Every timestamp sees the full source snapshot. Changes in source provenance
    also publish when the numeric total is unchanged. After-deadline arrivals are
    kept in the source ledger for reconciliation and never reopen this output.
    """
    _instance(history, SourceHistory, "source history")
    _instance(key, FeatureKey, "publication key")
    _minute(initial_at)
    _minute(deadline)
    if not history.known:
        raise ValueError("cannot publish from unknown source history")
    if not key.window_end <= initial_at <= deadline:
        raise ValueError("require window_end <= initial_at <= deadline")
    times = {initial_at}
    times.update(r.available_at for r in history.revisions
                 if initial_at < r.available_at <= deadline
                 and r.entity == key.entity and key.window_start <= r.event_time < key.window_end)
    output: list[PublishedRevision] = []
    for minute in sorted(times):
        reference = history.reference(key, minute)
        if not output or reference.source_versions != output[-1].source_versions:
            assert reference.value is not None
            output.append(PublishedRevision(key, len(output) + 1, minute, minute,
                                            reference.value, reference.source_versions))
    return tuple(output)


@dataclass(frozen=True)
class Snapshot:
    record: PublishedRevision | None
    known: bool = True
    captured_at: int | None = None

    def __post_init__(self) -> None:
        _boolean(self.known, "snapshot known")
        if self.record is not None:
            _instance(self.record, PublishedRevision, "snapshot record")
        if self.captured_at is not None:
            _minute(self.captured_at)

    @property
    def value(self) -> Number | None:
        return None if self.record is None else self.record.value


@dataclass(frozen=True)
class StoreTimeline:
    """Accepted sink writes; a late older publication cannot roll back the cell."""
    accepted: tuple[tuple[int, PublishedRevision], ...]
    known: bool = True

    def __post_init__(self) -> None:
        _boolean(self.known, "store history known")
        object.__setattr__(self, "accepted", tuple(tuple(pair) for pair in self.accepted))
        for minute, record in self.accepted:
            _minute(minute)
            _instance(record, PublishedRevision, "store record")

    @classmethod
    def from_deliveries(cls, publications: Iterable[PublishedRevision],
                        deliveries: Iterable[tuple[int, int]], *, known: bool = True) -> StoreTimeline:
        by_revision: dict[int, PublishedRevision] = {}
        key: FeatureKey | None = None
        for record in publications:
            if key is not None and record.key != key:
                raise ValueError("a store timeline models exactly one full key")
            key = record.key
            if record.revision in by_revision and by_revision[record.revision] != record:
                raise ValueError("conflicting publication revision")
            by_revision[record.revision] = record
        accepted: list[tuple[int, PublishedRevision]] = []
        last_revision = 0
        for visible_at, revision in sorted(deliveries):
            _minute(visible_at)
            _revision(revision)
            if revision not in by_revision:
                raise ValueError("delivery references an unknown publication")
            record = by_revision[revision]
            if visible_at < record.published_at:
                raise ValueError("a publication cannot be visible before it exists")
            if revision > last_revision:
                accepted.append((visible_at, record))
                last_revision = revision
        return cls(tuple(accepted), known)

    def at(self, minute: int) -> Snapshot:
        _minute(minute)
        if not self.known:
            return Snapshot(None, False)
        candidates = [record for visible_at, record in self.accepted if visible_at <= minute]
        return Snapshot(candidates[-1] if candidates else None)


@dataclass(frozen=True)
class CacheTimeline:
    """Refreshes capture immutable store records, not live store references."""
    captures: tuple[tuple[int, Snapshot], ...]
    known: bool = True

    def __post_init__(self) -> None:
        _boolean(self.known, "cache history known")
        object.__setattr__(self, "captures", tuple(tuple(pair) for pair in self.captures))
        for minute, snapshot in self.captures:
            _minute(minute)
            _instance(snapshot, Snapshot, "cache snapshot")

    @classmethod
    def from_refreshes(cls, store: StoreTimeline, refreshes: Iterable[int], *,
                       known: bool = True) -> CacheTimeline:
        captures = []
        refreshes = tuple(refreshes)
        for minute in refreshes:
            _minute(minute)
        for minute in sorted(set(refreshes)):
            snapshot = store.at(minute)
            captures.append((minute, Snapshot(snapshot.record, snapshot.known, minute)))
        return cls(tuple(captures), known)

    def at(self, minute: int) -> Snapshot:
        _minute(minute)
        if not self.known:
            return Snapshot(None, False)
        candidates = [capture for captured_at, capture in self.captures if captured_at <= minute]
        return candidates[-1] if candidates else Snapshot(None)


LOG_FIELDS = frozenset({"key", "raw_value", "model_input", "feature_missing", "fallback_value",
                        "value_revision", "value_key", "value_source_cutoff", "value_source_versions",
                        "cache_capture_at", "fallback_used", "fallback_reason", "preprocessing_id", "contracts"})


@dataclass(frozen=True)
class ServingLog:
    """Immutable observations. present_fields separates absent evidence from None.

    raw_value=None with feature_missing=True is a known cache miss; the explicit
    fallback then supplies model_input. Omitting a field is unverifiable evidence.
    Present non-None metadata is strictly typed; booleans are not revisions and
    equal-valued floats are not integer clock times. None remains permitted.
    """
    request_id: str
    requested_at: int
    key: FeatureKey | None
    raw_value: Number | None
    model_input: Number | None
    feature_missing: bool | None
    fallback_value: Number | None
    fallback_used: bool | None
    fallback_reason: str | None
    value_revision: int | None
    value_key: FeatureKey | None
    value_source_cutoff: int | None
    value_source_versions: tuple[tuple[str, int], ...] | None
    cache_capture_at: int | None
    preprocessing_id: str | None
    contracts: Contracts | None
    present_fields: frozenset[str] = LOG_FIELDS

    def __post_init__(self) -> None:
        object.__setattr__(self, "present_fields", frozenset(self.present_fields))
        _identity(self.request_id, "request ID")
        _minute(self.requested_at)
        if not self.present_fields <= LOG_FIELDS:
            raise ValueError("unrecognized serving-log fields")
        for field_name in ("raw_value", "model_input", "fallback_value"):
            value = getattr(self, field_name)
            if field_name in self.present_fields and value is not None:
                _finite_number(value)
        for field_name in self.present_fields:
            value = getattr(self, field_name)
            if value is None:
                continue
            if field_name in ("key", "value_key"):
                _instance(value, FeatureKey, field_name)
            elif field_name == "contracts":
                _instance(value, Contracts, field_name)
            elif field_name in ("feature_missing", "fallback_used"):
                _boolean(value, field_name)
            elif field_name == "value_revision":
                _revision(value)
            elif field_name in ("value_source_cutoff", "cache_capture_at"):
                _minute(value)
            elif field_name in ("fallback_reason", "preprocessing_id"):
                _identity(value, field_name)
            elif field_name == "value_source_versions":
                object.__setattr__(self, field_name, _source_versions(value))


def identity_transform(value: Number) -> Number:
    """The explicit identity-v1 model preprocessing contract for this fixture."""
    _finite_number(value)
    return value


def log_request(request_id: str, minute: int, key: FeatureKey, cache: CacheTimeline,
                *, fallback: Number = 0) -> ServingLog:
    """Simulate logging the raw cell, missingness, provenance, and model input."""
    _finite_number(fallback)
    snapshot = cache.at(minute)
    if not snapshot.known:
        raise ValueError("cannot simulate a read from unknown cache history")
    record = snapshot.record
    missing = record is None
    raw = None if missing else record.value
    return ServingLog(request_id, minute, key, raw,
                      identity_transform(fallback if missing else raw), missing,
                      fallback if missing else None,
                      missing, "cache_miss" if missing else None,
                      None if missing else record.revision,
                      None if missing else record.key,
                      None if missing else record.source_cutoff,
                      None if missing else record.source_versions,
                      snapshot.captured_at,
                      CONTRACTS.preprocessing_id, CONTRACTS)


@dataclass(frozen=True)
class Trace:
    key: FeatureKey
    source: SourceHistory
    initial_at: int
    deadline: int
    publications: tuple[PublishedRevision, ...]
    store: StoreTimeline
    cache: CacheTimeline
    fallback: Number = 0
    contracts: Contracts = CONTRACTS

    def __post_init__(self) -> None:
        _instance(self.key, FeatureKey, "trace key")
        _instance(self.contracts, Contracts, "trace contracts")
        _instance(self.source, SourceHistory, "trace source")
        _instance(self.store, StoreTimeline, "trace store")
        _instance(self.cache, CacheTimeline, "trace cache")
        _minute(self.initial_at)
        _minute(self.deadline)
        _finite_number(self.fallback)
        object.__setattr__(self, "publications", tuple(self.publications))
        for record in self.publications:
            _instance(record, PublishedRevision, "trace publication")

    def policy_at(self, minute: int) -> PublishedRevision | None:
        records = [record for record in self.publications if record.published_at <= minute]
        return max(records, key=lambda record: record.revision) if records else None

    def after_deadline_at(self, minute: int) -> tuple[tuple[str, int], ...]:
        return tuple((r.source_event_id, r.revision) for r in self.source.revisions
                     if self.deadline < r.available_at <= minute and r.entity == self.key.entity
                     and self.key.window_start <= r.event_time < self.key.window_end)


FLAG_ORDER = ("store_missing", "materialization_lag", "cache_miss", "cache_lag",
              "fallback_used", "source_after_deadline", "numeric_mismatch",
              "provenance_mismatch", "definition_or_key_mismatch",
              "preprocessing_mismatch", "insufficient_evidence")


def _record_summary(record: PublishedRevision | None) -> dict | None:
    if record is None:
        return None
    return {"value": record.value, "revision": record.revision,
            "source_cutoff": record.source_cutoff,
            "source_versions": [list(pair) for pair in record.source_versions]}


def _same_record(left: PublishedRevision | None, right: PublishedRevision | None) -> bool:
    return left == right


def reconcile(trace: Trace, logs: Iterable[ServingLog]) -> dict:
    """Compare observations with source, policy, store, cache, and preprocessing.

    Lag diagnoses require trace evidence, never a difference between numbers
    alone. Reports do not mutate, overwrite, or repair serving logs. Absent log
    fields make full parity unverifiable even if the surviving numbers match.
    """
    rows: list[dict] = []
    counts: Counter[str] = Counter()
    request_ids: set[str] = set()
    for log in logs:
        if log.request_id in request_ids:
            raise ValueError(f"duplicate request_id: {log.request_id}; supply one row per request")
        request_ids.add(log.request_id)
        present = log.present_fields
        flags: set[str] = set()
        source = trace.source.reference(trace.key, log.requested_at)
        policy = trace.policy_at(log.requested_at)
        store = trace.store.at(log.requested_at)
        cache = trace.cache.at(log.requested_at)
        late = trace.after_deadline_at(log.requested_at)
        complete = present == LOG_FIELDS and source.history_known and store.known and cache.known
        if not complete or policy is None:
            flags.add("insufficient_evidence")
        if policy is not None and store.known:
            if store.record is None:
                flags.add("store_missing")
            elif store.record.revision < policy.revision:
                flags.add("materialization_lag")
        if cache.known:
            if cache.record is None:
                flags.add("cache_miss")
            elif store.known and store.record is not None and cache.record.revision < store.record.revision:
                flags.add("cache_lag")
        if "fallback_used" in present and log.fallback_used is True:
            flags.add("fallback_used")
        if late:
            flags.add("source_after_deadline")
        if "key" in present and log.key != trace.key:
            flags.add("definition_or_key_mismatch")
        if "value_key" in present and log.value_key is not None and log.value_key != trace.key:
            flags.add("definition_or_key_mismatch")
        if "contracts" in present and log.contracts != trace.contracts:
            flags.add("definition_or_key_mismatch")

        expected_model = None if policy is None else identity_transform(policy.value)
        expected_logged_model = (None if not cache.known else
                                 identity_transform(trace.fallback if cache.record is None else cache.record.value))
        # A plausible number from the wrong/unknown cell is not semantic parity.
        key_fields = {"key", "value_key", "feature_missing", "raw_value", "contracts"}
        observed_branch = (log.feature_missing is False and log.raw_value is not None
                           and log.value_key == trace.key)
        missing_branch = (log.feature_missing is True and log.raw_value is None and log.value_key is None
                          and {"fallback_used", "fallback_reason", "fallback_value"} <= present
                          and log.fallback_used is True and log.fallback_reason == "cache_miss"
                          and log.fallback_value is not None)
        key_verified = (key_fields <= present and log.key == trace.key and log.contracts == trace.contracts
                        and (observed_branch or missing_branch))
        model_contract_verified = ("preprocessing_id" in present
                                   and log.preprocessing_id == trace.contracts.preprocessing_id)
        policy_numeric = None
        raw_policy_numeric = None
        if key_verified and "raw_value" in present and log.raw_value is not None and policy is not None:
            raw_policy_numeric = numeric_equal(log.raw_value, policy.value)
        if key_verified and model_contract_verified and "model_input" in present and log.model_input is not None and expected_model is not None:
            policy_numeric = numeric_equal(log.model_input, expected_model)
            if not policy_numeric:
                flags.add("numeric_mismatch")
        if "raw_value" in present and cache.known and not _same_value(log.raw_value, cache.value):
            flags.add("numeric_mismatch")

        if cache.known:
            record = cache.record
            expected_provenance = {
                "value_key": None if record is None else record.key,
                "value_revision": None if record is None else record.revision,
                "value_source_cutoff": None if record is None else record.source_cutoff,
                "value_source_versions": None if record is None else record.source_versions,
                "feature_missing": record is None,
                "fallback_value": trace.fallback if record is None else None,
                "fallback_used": record is None,
                "fallback_reason": "cache_miss" if record is None else None,
                "cache_capture_at": cache.captured_at,
            }
            for name, expected in expected_provenance.items():
                if name in present and getattr(log, name) != expected:
                    flags.add("provenance_mismatch")

        if "preprocessing_id" in present and log.preprocessing_id != trace.contracts.preprocessing_id:
            flags.add("preprocessing_mismatch")
        if {"model_input", "raw_value", "feature_missing", "fallback_value"} <= present:
            transform_input = log.fallback_value if log.feature_missing is True else log.raw_value
            if transform_input is None or not numeric_equal(log.model_input, identity_transform(transform_input)):
                flags.add("preprocessing_mismatch")

        provenance_fields = {"key", "value_key", "value_revision", "value_source_cutoff",
                             "value_source_versions", "cache_capture_at", "feature_missing",
                             "fallback_value", "fallback_used", "fallback_reason", "contracts"}
        trace_provenance = None
        policy_provenance = None
        if provenance_fields <= present and cache.known:
            trace_provenance = not flags.intersection({"provenance_mismatch", "definition_or_key_mismatch"})
        if provenance_fields <= present and policy is not None:
            policy_provenance = (log.key == trace.key and log.value_key == policy.key
                                 and log.value_revision == policy.revision
                                 and log.value_source_cutoff == policy.source_cutoff
                                 and log.value_source_versions == policy.source_versions
                                 and log.feature_missing is False and log.fallback_value is None
                                 and log.fallback_used is False and log.fallback_reason is None
                                 and log.contracts == trace.contracts)
        trace_numeric = None
        if key_verified and model_contract_verified and {"raw_value", "model_input"} <= present and cache.known and log.raw_value is not None and cache.value is not None:
            trace_numeric = (numeric_equal(log.raw_value, cache.value)
                             and numeric_equal(log.model_input, expected_logged_model))

        logging_fields = LOG_FIELDS
        logging_evaluable = logging_fields <= present and cache.known
        logging_match = None
        if logging_evaluable:
            logging_match = (numeric_equal(log.model_input, expected_logged_model)
                             and _same_value(log.raw_value, cache.value)
                             and not flags.intersection({"provenance_mismatch", "definition_or_key_mismatch", "preprocessing_mismatch"}))
        full_evaluable = complete and policy is not None
        policy_full = None
        if full_evaluable:
            policy_full = bool(policy_numeric and logging_match and cache.record == policy)
        source_comparable = key_verified and source.history_known and "raw_value" in present and log.raw_value is not None
        source_match = (numeric_equal(log.raw_value, source.value) if source_comparable else None)
        row = {
            "request_id": log.request_id, "requested_at": log.requested_at,
            "logged": {name: asdict(log)[name] for name in sorted(present)},
            "expected_source": {"value": source.value, "history_known": source.history_known,
                                "source_versions": [list(pair) for pair in source.source_versions]},
            "expected_policy": _record_summary(policy),
            "expected_store": {"history_known": store.known, "record": _record_summary(store.record)},
            "expected_cache": {"history_known": cache.known, "captured_at": cache.captured_at,
                               "record": _record_summary(cache.record)},
            "expected_model_input": expected_model,
            "expected_logged_model_input_from_cache": expected_logged_model,
            "logged_raw_value": log.raw_value if "raw_value" in present else None,
            "logged_model_input": log.model_input if "model_input" in present else None,
            "logged_feature_missing": log.feature_missing if "feature_missing" in present else None,
            "logged_fallback_value": log.fallback_value if "fallback_value" in present else None,
            "logged_fallback_used": log.fallback_used if "fallback_used" in present else None,
            "logged_fallback_reason": log.fallback_reason if "fallback_reason" in present else None,
            "logged_cache_capture_at": log.cache_capture_at if "cache_capture_at" in present else None,
            "absent_log_fields": sorted(LOG_FIELDS - present),
            "model_delta_from_policy": (log.model_input - expected_model if "model_input" in present and log.model_input is not None and expected_model is not None else None),
            "semantic_key_verified": key_verified,
            "lag_attribution_scope": "independent publication/store/cache trace, not numeric differences",
            "comparisons": {
                "source_to_policy": (numeric_equal(source.value, policy.value) and source.source_versions == policy.source_versions
                                     if source.history_known and policy is not None else None),
                "policy_to_store": (_same_record(policy, store.record) if policy is not None and store.known else None),
                "store_to_cache": (_same_record(store.record, cache.record) if store.known and cache.known else None),
                "trace_to_log": logging_match,
                "trace_numeric_match": trace_numeric,
                "trace_provenance_match": trace_provenance,
                "policy_numeric_match": policy_numeric,
                "raw_policy_numeric_match": raw_policy_numeric,
                "policy_provenance_match": policy_provenance,
                "policy_full_match": policy_full,
                "raw_source_numeric_match": source_match,
            },
            "after_deadline_source_versions": [list(pair) for pair in late],
            "flags": [flag for flag in FLAG_ORDER if flag in flags],
        }
        rows.append(row)
        counts.update(row["flags"])
    def metric(field: str) -> dict:
        values = [r["comparisons"][field] for r in rows]
        return {"matches": sum(value is True for value in values),
                "evaluable": sum(value is not None for value in values),
                "excluded": sum(value is None for value in values)}
    return {
        "scope": "Synthetic teaching fixture; these are not production metrics.",
        "key": asdict(trace.key), "contracts": asdict(trace.contracts),
        "window_semantics": f"fixed half-open [{trace.key.window_start},{trace.key.window_end}); request time does not move this key",
        "deadline": trace.deadline, "total_requests": len(rows),
        "metrics": {
            "policy_numeric": metric("policy_numeric_match"),
            "raw_policy_numeric": metric("raw_policy_numeric_match"),
            "policy_provenance": metric("policy_provenance_match"),
            "policy_full": metric("policy_full_match"),
            "trace_logging": metric("trace_to_log"),
            "raw_source_numeric": metric("raw_source_numeric_match"),
        },
        "flag_counts": {flag: counts[flag] for flag in FLAG_ORDER}, "rows": rows,
    }


def build_fixture(*, include_late: bool = True) -> tuple[Trace, tuple[ServingLog, ...]]:
    """Build the chapter fixture entirely from source rows and replay rules."""
    revisions = [
        SourceRevision("A", 1, "C1", 550, 551, 20),
        SourceRevision("C", 1, "C1", 585, 586, 30),
        SourceRevision("D", 1, "C1", 602, 603, 10),
        SourceRevision("C", 2, "C1", 585, 605, 25),
        SourceRevision("B", 1, "C1", 575, 607, 40),
    ]
    if include_late:
        revisions.append(SourceRevision("E", 1, "C1", 595, 612, 15))
    history = SourceHistory(revisions)
    publications = build_publications(history, KEY, initial_at=600, deadline=610)
    store = StoreTimeline.from_deliveries(publications, ((601, 1), (606, 2), (609, 3)))
    cache = CacheTimeline.from_refreshes(store, (601, 609))
    trace = Trace(KEY, history, 600, 610, publications, store, cache)
    logs = tuple(log_request(f"R{index}", minute, KEY, cache)
                 for index, minute in enumerate((600, 602, 606, 608, 610, 620)))
    return trace, logs


def canonical_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def write_outputs(output_dir: str = "generated") -> dict:
    """Write a reproducible report and evidence manifest; never modify logs."""
    import hashlib
    from pathlib import Path
    import platform

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    trace, logs = build_fixture()
    report = reconcile(trace, logs)
    report_bytes = canonical_json(report).encode("utf-8")
    (directory / "parity_report.json").write_bytes(report_bytes)
    source_files = ("parity_lab.py", "printed_examples.py", "randomized_checks.py",
                    "test_parity_lab.py", "test_metadata_contract.py")
    root = Path(__file__).parent
    manifest = {
        "lab": "Chapter 6 fixed-window serving parity",
        "python_version": platform.python_version(),
        "key": asdict(trace.key), "contracts": asdict(trace.contracts),
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "code_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_files},
        "source_ledger_sha256": hashlib.sha256(canonical_json([asdict(row) for row in trace.source.revisions]).encode()).hexdigest(),
        "requests": len(logs), "metrics": report["metrics"],
        "verification_note": "This manifest identifies inputs and outputs; run the README verification commands separately.",
    }
    (directory / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="generated", help="report and manifest destination (default: generated)")
    arguments = parser.parse_args()
    print(canonical_json(write_outputs(arguments.output_dir)), end="")
