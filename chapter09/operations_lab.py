"""Chapter 9: synthetic operational evidence and a local change-control gate.

Python 3.12, standard library only. No deployment, external rollback, real ACL
enforcement, or claims about production outcomes. All times are synthetic minutes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from hashlib import sha256
import json
import inspect
from pathlib import Path
from typing import Iterable

from parity_lab import (CONTRACTS, KEY, LOG_FIELDS, FeatureKey, PublishedRevision,
                        ServingLog, Trace, build_fixture, canonical_json, reconcile)

BASELINE = "replacement-v1"
CANDIDATE = "add-snapshots-v2"
READER = "oncall-operator"
NOW = 625
MIN_REQUESTS = 4  # A teaching choice for this exact cohort, not an industry SLO.
COHORT = tuple((f"C{i}", minute) for i, minute in enumerate(range(621, 625)))
BASE_COHORT = tuple((f"R{i}", minute) for i, minute in enumerate((600, 602, 606, 608, 610, 620)))


def _plain(value):
    if hasattr(value, "__dataclass_fields__"):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(v) for v in value)
    return value


def digest(value) -> str:
    return sha256(canonical_json(_plain(value)).encode()).hexdigest()


def _optional_identity(value, name: str) -> None:
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{name} must be a string or unknown")


def _optional_minute(value, name: str) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        raise TypeError(f"{name} must use integer synthetic minutes or unknown")


def _request_cohort(values: Iterable[tuple[str, int]]) -> tuple[tuple[str, int], ...]:
    cohort = []
    for pair in values:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("cohort requires (request ID, integer minute) pairs")
        request_id, minute = pair
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("cohort request identity must be a nonempty string")
        if minute is None:
            raise TypeError("cohort request times require integer synthetic minutes")
        _optional_minute(minute, "cohort request time")
        cohort.append((request_id, minute))
    return tuple(cohort)


def _source_versions(values) -> tuple[tuple[str, int], ...]:
    versions, seen = [], set()
    for pair in values:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("source versions require (event ID, revision) pairs")
        event_id, revision = pair
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("source event IDs must be nonempty strings")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise ValueError("source revisions must be positive integers")
        if event_id in seen:
            raise ValueError("source versions must select one revision per event ID")
        seen.add(event_id)
        versions.append((event_id, revision))
    return tuple(sorted(versions))


@dataclass(frozen=True)
class Context:
    """Identity that must be identical across the matched experiment."""
    key: FeatureKey | None
    policy_contract_version: str | None
    preprocessing_id: str | None
    source_schema_version: str | None
    publication_schema_version: str | None
    serving_log_schema_version: str | None
    source_snapshot_id: str | None
    input_snapshot_id: str | None
    policy_initial_at: int | None
    policy_deadline: int | None

    def __post_init__(self):
        if self.key is not None and not isinstance(self.key, FeatureKey):
            raise TypeError("context key must be a FeatureKey or unknown")
        for field in fields(self):
            if field.name in {"policy_initial_at", "policy_deadline"}:
                _optional_minute(getattr(self, field.name), field.name)
            elif field.name != "key":
                _optional_identity(getattr(self, field.name), field.name)


@dataclass(frozen=True)
class Lineage:
    context: Context | None
    release_id: str | None
    implementation_digest: str | None

    def __post_init__(self):
        if self.context is not None and not isinstance(self.context, Context):
            raise TypeError("lineage context must be a Context or unknown")
        _optional_identity(self.release_id, "release_id")
        _optional_identity(self.implementation_digest, "implementation_digest")


VALUE_FIELDS = frozenset({"raw_value", "model_input", "feature_missing", "fallback_used",
                          "value_revision", "source_cutoff", "source_versions"})


@dataclass(frozen=True)
class Observation:
    request_id: str
    requested_at: int
    lineage: Lineage
    raw_value: int | None
    model_input: int | None
    feature_missing: bool | None
    fallback_used: bool | None
    value_revision: int | None
    source_cutoff: int | None
    source_versions: tuple[tuple[str, int], ...] | None
    kind: str
    present_fields: frozenset[str] = VALUE_FIELDS

    def __post_init__(self):
        object.__setattr__(self, "present_fields", frozenset(self.present_fields))
        if not self.present_fields <= VALUE_FIELDS:
            raise ValueError("unknown observation field")
        if isinstance(self.requested_at, bool) or not isinstance(self.requested_at, int):
            raise TypeError("request times are integer minutes")
        if not isinstance(self.request_id, str) or not self.request_id:
            raise ValueError("request identity is required")
        if not isinstance(self.lineage, Lineage):
            raise TypeError("observation lineage must be a Lineage")
        for name in ("raw_value", "model_input", "value_revision", "source_cutoff"):
            value = getattr(self, name)
            if name in self.present_fields and value is not None:
                if isinstance(value, bool) or not isinstance(value, int):
                    raise TypeError("this fixture uses exact integer feature values and revisions")
                if name == "value_revision" and value < 1:
                    raise ValueError("value revisions must be positive integers")
        for name in ("feature_missing", "fallback_used"):
            if name in self.present_fields and getattr(self, name) is not None:
                if type(getattr(self, name)) is not bool:
                    raise TypeError("missingness and fallback flags must be bool or unknown")
        if "source_versions" in self.present_fields and self.source_versions is not None:
            object.__setattr__(self, "source_versions", _source_versions(self.source_versions))


@dataclass(frozen=True)
class Release:
    release_id: str | None
    consumer_mode: str | None
    context: Context | None
    code_digest: str | None

    def __post_init__(self):
        if self.context is not None and not isinstance(self.context, Context):
            raise TypeError("release context must be a Context or unknown")
        for name in ("release_id", "consumer_mode", "code_digest"):
            _optional_identity(getattr(self, name), name)


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    purpose: str
    owner: str
    authorized_readers: tuple[str, ...]
    expires_at: int
    content_id: str | None
    exists: bool = True

    def __post_init__(self):
        if type(self.exists) is not bool:
            raise TypeError("artifact presence must be a boolean")
        if isinstance(self.authorized_readers, (str, bytes)):
            raise TypeError("authorized_readers must be a collection of reader identities")
        object.__setattr__(self, "authorized_readers", tuple(self.authorized_readers))
        if isinstance(self.expires_at, bool) or not isinstance(self.expires_at, int):
            raise TypeError("artifact expiry uses integer synthetic minutes")


@dataclass(frozen=True)
class Packet:
    trace: Trace
    context: Context
    cohort: tuple[tuple[str, int], ...]
    observed: tuple[Observation, ...]
    baseline_replay: tuple[Observation, ...]
    candidate_replay: tuple[Observation, ...]
    baseline: Release
    candidate: Release
    recovery_target: Release | None
    inventory: tuple[Artifact, ...]
    now: int = NOW
    reader: str = READER

    def __post_init__(self):
        object.__setattr__(self, "cohort", _request_cohort(self.cohort))


def context_for(trace: Trace) -> Context:
    return Context(trace.key, trace.contracts.policy_contract_version,
                   trace.contracts.preprocessing_id, trace.contracts.source_schema_version,
                   trace.contracts.publication_schema_version, trace.contracts.serving_log_schema_version,
                   digest(trace.source), digest(trace.publications), trace.initial_at, trace.deadline)


def release_for(release_id: str, mode: str, context: Context) -> Release:
    return Release(release_id, mode, context,
                   digest(release_payload(release_id, mode)))


def release_payload(release_id: str, mode: str) -> dict:
    """Retained source bytes plus mode; this is not a production build artifact."""
    return {"release_id": release_id, "consumer_mode": mode,
            "consumer_python_source": inspect.getsource(consume_snapshots),
            "implementation_contract": "chapter9-local-consumer-v1"}


def consume_snapshots(publications: Iterable[PublishedRevision], mode: str) -> int:
    """One delivery of each ordered full snapshot; addition is the deliberate bug.

    This is an arithmetic counterexample, not a retry/order/storage protocol.
    """
    rows = tuple(publications)
    if mode not in {"replace", "add"}:
        raise ValueError("unsupported consumer mode")
    if not rows or any(p.key != rows[0].key for p in rows):
        raise ValueError("require snapshots of one feature key")
    if [p.revision for p in rows] != sorted({p.revision for p in rows}):
        raise ValueError("this experiment requires ordered unique full snapshots")
    return rows[-1].value if mode == "replace" else sum(p.value for p in rows)


def replay(trace: Trace, cohort: Iterable[tuple[str, int]], release: Release,
           *, kind: str = "controlled_replay") -> tuple[Observation, ...]:
    if release.context != context_for(trace):
        raise ValueError("release/input context mismatch")
    state, reasons = _input_context_status(trace, release.context)
    if state != "OK":
        raise ValueError("incompatible publication/input evidence: " + ", ".join(reasons))
    output = []
    for request_id, minute in _request_cohort(cohort):
        eligible = tuple(p for p in trace.publications if p.published_at <= minute)
        value = consume_snapshots(eligible, release.consumer_mode)
        last = eligible[-1]
        output.append(Observation(request_id, minute, Lineage(release.context, release.release_id, release.code_digest),
                                  value, value, False, False, last.revision, last.source_cutoff, last.source_versions, kind))
    return tuple(output)


def _input_context_status(trace: Trace, context: Context) -> tuple[str, list[str]]:
    """Bind declared identities to every retained publication, not just hashes.

    Compatible labels do not authenticate the source or prove that a published
    value was correctly computed. They do establish which semantic input the
    replay and its metrics describe, including snapshots replaced by later ones.
    """
    missing, wrong = [], []

    def compare(actual, expected, prefix):
        if actual in (None, "") or expected in (None, ""):
            missing.append("missing:" + prefix)
        elif actual != expected:
            wrong.append("mismatch:" + prefix)

    expected = context_for(trace)
    for field in fields(expected):
        compare(getattr(context, field.name), getattr(expected, field.name), field.name)
    for publication in trace.publications:
        prefix = f"publication:{publication.revision}:"
        compare(publication.key, trace.key, prefix + "key")
        if publication.contracts is None:
            missing.append("missing:" + prefix + "contracts")
        else:
            for field in fields(trace.contracts):
                compare(getattr(publication.contracts, field.name),
                        getattr(trace.contracts, field.name), prefix + field.name)
    if wrong:
        return "EXCLUDED", wrong + missing
    return ("UNKNOWN", missing) if missing else ("OK", [])


def _context_status(actual: Lineage, context: Context, release_id: str) -> tuple[str, list[str]]:
    if actual.context is None:
        return "UNKNOWN", ["missing:context"]
    missing = ["missing:" + f.name for f in fields(context)
               if getattr(actual.context, f.name) in (None, "") or getattr(context, f.name) in (None, "")]
    if actual.release_id in (None, ""):
        missing.append("missing:release_id")
    if not actual.implementation_digest:
        missing.append("missing:implementation_digest")
    if missing:
        return "UNKNOWN", missing
    wrong = ["mismatch:" + f.name for f in fields(context)
             if getattr(actual.context, f.name) != getattr(context, f.name)]
    if actual.release_id != release_id:
        wrong.append("mismatch:release_id")
    expected_digest = release_for(release_id, "replace" if release_id == BASELINE else "add", context).code_digest
    if actual.implementation_digest != expected_digest:
        wrong.append("mismatch:implementation_digest")
    return ("EXCLUDED", wrong) if wrong else ("OK", [])


def _measurement_complete(row: Observation) -> bool:
    if row.present_fields != VALUE_FIELDS or row.model_input is None:
        return False
    if row.feature_missing is True:
        return (row.raw_value is None and row.fallback_used is True
                and row.value_revision is None and row.source_cutoff is None and row.source_versions is None)
    return (row.feature_missing is False and row.fallback_used is False and row.raw_value is not None
            and row.value_revision is not None and row.source_cutoff is not None and row.source_versions is not None)


def _metric(entries: list[tuple[str, bool | None]]) -> dict:
    evaluated = [value for state, value in entries if state == "OK"]
    count = sum(value is True for value in evaluated)
    return {"numerator": count, "denominator": len(evaluated),
            "excluded": sum(state == "EXCLUDED" for state, _ in entries),
            "unknown": sum(state == "UNKNOWN" for state, _ in entries),
            "rate": None if not evaluated else count / len(evaluated)}


def summarize(rows: Iterable[Observation], trace: Trace, context: Context,
              expected_release: str, cohort: Iterable[tuple[str, int]]) -> dict:
    """One row per declared request. Missing evidence is never a successful match.

    Numeric parity uses exact integers. The full denominator includes a known
    fallback request. Raw parity excludes a known absent raw value. Context
    mismatch is excluded; missing metadata is unknown. Neither is a match.
    """
    rows, cohort = tuple(rows), _request_cohort(cohort)
    if len({r.request_id for r in rows}) != len(rows):
        raise ValueError("duplicate request_id; retries cannot inflate denominators")
    if len({r[0] for r in cohort}) != len(cohort):
        raise ValueError("duplicate declared request_id")
    input_state, input_reasons = _input_context_status(trace, context)
    indexed = {r.request_id: r for r in rows}
    allowed = {r[0] for r in cohort}
    extras = sorted(set(indexed) - allowed)
    names = ("missing", "fallback", "raw_parity", "model_parity", "full_model_parity", "lineage")
    entries = {name: [] for name in names}
    details = []
    complete = 0
    for request_id, minute in cohort:
        row = indexed.get(request_id)
        state, reasons = ("UNKNOWN", ["missing:request_log"]) if row is None else _context_status(row.lineage, context, expected_release)
        if state == "OK" and input_state != "OK":
            state, reasons = input_state, list(input_reasons)
        if row is not None and row.requested_at != minute:
            state, reasons = "EXCLUDED", ["mismatch:requested_at"]
        policy = trace.policy_at(minute)
        if state == "OK" and policy is None:
            state, reasons = "UNKNOWN", ["missing:eligible_policy"]
        well_formed = row is not None and _measurement_complete(row)
        if state == "OK" and well_formed and row.feature_missing is False:
            served = next((p for p in trace.publications if p.revision == row.value_revision), None)
            if (served is None or served.published_at > minute or row.source_cutoff != served.source_cutoff
                    or row.source_versions != served.source_versions):
                state, reasons = "EXCLUDED", ["mismatch:value_provenance"]
        detail = {"request_id": request_id, "requested_at": minute, "context_status": state, "reasons": reasons}
        entries["lineage"].append((state, state == "OK"))
        if state != "OK" or not well_formed:
            evidence_state = state if state != "OK" else "UNKNOWN"
            if not well_formed and state == "OK":
                detail["reasons"] = ["missing_or_inconsistent:value_evidence"]
            for name in names[:-1]:
                entries[name].append((evidence_state, None))
        else:
            complete += 1
            entries["missing"].append(("OK", row.feature_missing))
            entries["fallback"].append(("OK", row.fallback_used))
            entries["raw_parity"].append(("EXCLUDED", None) if row.raw_value is None else ("OK", row.raw_value == policy.value))
            entries["model_parity"].append(("OK", row.model_input == policy.value))
            full = (row.raw_value == policy.value and row.model_input == policy.value
                    and row.value_revision == policy.revision and row.source_versions == policy.source_versions
                    and row.source_cutoff == policy.source_cutoff and row.model_input == row.raw_value
                    and row.feature_missing is False and row.fallback_used is False)
            entries["full_model_parity"].append(("OK", full))
        details.append(detail)
    return {"declared_requests": len(cohort), "received_requests": len(rows),
            "complete_comparable_requests": complete, "unexpected_request_ids": extras,
            "metrics": {name: _metric(entries[name]) for name in names}, "rows": details}


def base_report(trace: Trace | None = None, logs: Iterable[ServingLog] | None = None) -> dict:
    if trace is None and logs is None:
        trace, logs = build_fixture()
    if trace is None or logs is None:
        raise ValueError("provide both trace and logs")
    logs = tuple(logs)
    if len(logs) != len(BASE_COHORT) or {(r.request_id, r.requested_at) for r in logs} != set(BASE_COHORT):
        raise ValueError("base report requires all six declared R0-R5 requests exactly once")
    report = reconcile(trace, logs)
    # Preserve Chapter6's detailed provenance/full-parity evaluation; do not
    # substitute reconstructed values for the observations supplied to it.
    metrics = {}
    for name, source in (("raw_parity", "raw_policy_numeric"), ("model_parity", "policy_numeric"), ("full_model_parity", "policy_full")):
        m = report["metrics"][source]
        unknown = sum(row["comparisons"][{"raw_parity": "raw_policy_numeric_match", "model_parity": "policy_numeric_match", "full_model_parity": "policy_full_match"}[name]] is None
                      and not (name == "raw_parity" and row["logged_feature_missing"] is True and row["semantic_key_verified"])
                      for row in report["rows"])
        metrics[name] = {"numerator": m["matches"], "denominator": m["evaluable"],
                         "excluded": m["excluded"] - unknown, "unknown": unknown,
                         "rate": None if not m["evaluable"] else m["matches"] / m["evaluable"]}
    for name, field in (("missing", "feature_missing"), ("fallback", "fallback_used")):
        metrics[name] = _metric([("OK", getattr(log, field)) if field in log.present_fields and type(getattr(log, field)) is bool
                                 else ("UNKNOWN", None) for log in logs])
    by_revision = {p.revision: p for p in trace.publications}
    ages = []
    for log in logs:
        latest = trace.policy_at(log.requested_at)
        served = by_revision.get(log.value_revision) if "value_revision" in log.present_fields else None
        known = (log.present_fields == LOG_FIELDS and log.key == trace.key and log.value_key == trace.key
                 and served is not None and latest is not None and served.published_at <= log.requested_at
                 and log.value_source_versions == served.source_versions
                 and log.value_source_cutoff == served.source_cutoff and log.contracts == trace.contracts)
        no_value = (log.present_fields == LOG_FIELDS and log.feature_missing is True and log.raw_value is None
                    and log.value_key is None and log.value_revision is None and log.value_source_cutoff is None
                    and log.value_source_versions is None and log.fallback_used is True)
        ages.append({"request_id": log.request_id,
                     "publication_age": log.requested_at - served.published_at if known else None,
                     "publication_lag": latest.published_at - served.published_at if known else None,
                     "status": "KNOWN" if known else ("NO_VALUE" if no_value else "UNKNOWN")})
    return {"scope": "Synthetic logs and independent reconstruction; no real serving observations.",
            "metrics": metrics, "publication_timing": ages,
            "publication_timing_coverage": {"declared_requests": len(logs),
                                            "measurable": sum(r["status"] == "KNOWN" for r in ages),
                                            "excluded_no_value": sum(r["status"] == "NO_VALUE" for r in ages),
                                            "unknown": sum(r["status"] == "UNKNOWN" for r in ages)},
            "chapter6_report": report}


def build_change_packet() -> Packet:
    trace, _ = build_fixture()
    context = context_for(trace)
    baseline = release_for(BASELINE, "replace", context)
    candidate = release_for(CANDIDATE, "add", context)
    last = trace.publications[-1]
    # Fictional incident log values are recorded explicitly. The separate replay
    # executes both consumers, so an observation is not called a reconstruction.
    observed = tuple(Observation(rid, minute, Lineage(context, CANDIDATE, candidate.code_digest), 180, 180,
                                 False, False, 3, last.source_cutoff, last.source_versions, "synthetic_observation")
                     for rid, minute in COHORT)
    packet = Packet(trace, context, COHORT, observed, replay(trace, COHORT, baseline),
                    replay(trace, COHORT, candidate), baseline, candidate, baseline, ())
    required = required_artifacts(packet)
    inventory = tuple(Artifact(name, purpose, "feature-platform", (READER, "release-reviewer"),
                               700, content_id) for name, (purpose, content_id) in required.items())
    return replace(packet, inventory=inventory)


def required_artifacts(packet: Packet) -> dict[str, tuple[str, str | None]]:
    return {"request_log": ("inspect the synthetic candidate observations", digest(packet.observed)),
            "source_snapshot": ("establish the retained source/input identity", packet.context.source_snapshot_id),
            "publication_bundle": ("replay the same three full snapshots", packet.context.input_snapshot_id),
            "release_manifest": ("identify both implementations and compatibility", digest((packet.baseline, packet.candidate))),
            "replay_report": ("retain paired controlled replay outputs", digest((packet.baseline_replay, packet.candidate_replay))),
            "recovery_release": ("restore the exact compatible replacement consumer locally", packet.baseline.code_digest)}


def inspect_inventory(packet: Packet) -> dict:
    """Synthetic authorized-reader and exclusive-expiry checks, not real ACLs."""
    if len({a.artifact_id for a in packet.inventory}) != len(packet.inventory):
        raise ValueError("duplicate artifact_id")
    artifacts = {a.artifact_id: a for a in packet.inventory}
    statuses = {}
    for artifact_id, (purpose, expected) in required_artifacts(packet).items():
        item = artifacts.get(artifact_id)
        if item is None or not item.exists:
            status = "MISSING"
        elif packet.reader not in item.authorized_readers:
            status = "DENIED"
        elif packet.now >= item.expires_at:
            status = "EXPIRED"
        elif not item.owner or not item.purpose:
            status = "UNKNOWN_METADATA"
        elif item.owner != "feature-platform" or item.purpose != purpose:
            status = "METADATA_MISMATCH"
        elif not item.content_id or not expected:
            status = "UNKNOWN_IDENTITY"
        elif item.content_id != expected:
            status = "IDENTITY_MISMATCH"
        else:
            status = "AVAILABLE"
        statuses[artifact_id] = status
    return statuses


def _cohort_complete(summary: dict, size: int) -> bool:
    return (size >= MIN_REQUESTS and summary["complete_comparable_requests"] == size
            and summary["received_requests"] == size and not summary["unexpected_request_ids"])


def _passes(summary: dict, size: int) -> bool:
    m = summary["metrics"]
    return (_cohort_complete(summary, size)
            and all(m[name]["numerator"] == size and m[name]["denominator"] == size
                    for name in ("raw_parity", "model_parity", "full_model_parity", "lineage"))
            and all(m[name]["numerator"] == 0 and m[name]["denominator"] == size for name in ("missing", "fallback")))


def decide(packet: Packet) -> dict:
    """Pedagogical exact-cohort gate. A recommendation never deploys anything."""
    size = len(packet.cohort)
    observed = summarize(packet.observed, packet.trace, packet.context, CANDIDATE, packet.cohort)
    baseline = summarize(packet.baseline_replay, packet.trace, packet.context, BASELINE, packet.cohort)
    candidate = summarize(packet.candidate_replay, packet.trace, packet.context, CANDIDATE, packet.cohort)
    evidence = inspect_inventory(packet)
    blockers = []
    if isinstance(packet.now, bool) or not isinstance(packet.now, int):
        raise TypeError("decision time uses integer synthetic minutes")
    evidence_times = [minute for _, minute in packet.cohort]
    evidence_times.extend(r.requested_at for rows in (packet.observed, packet.baseline_replay, packet.candidate_replay) for r in rows)
    if evidence_times and packet.now < max(evidence_times):
        blockers.append("future_request_evidence")
    # The declared cohort/input experiment is fixed, not selected after seeing results.
    if packet.cohort != COHORT:
        blockers.append("cohort_contract_mismatch")
    if packet.context != context_for(packet.trace):
        blockers.append("input_context_mismatch")
    _, input_reasons = _input_context_status(packet.trace, packet.context)
    blockers.extend("input_" + reason for reason in input_reasons)
    if packet.baseline != release_for(BASELINE, "replace", packet.context) or packet.candidate != release_for(CANDIDATE, "add", packet.context):
        blockers.append("release_manifest_mismatch")
    for label, summary in (("observation", observed), ("baseline_replay", baseline), ("candidate_replay", candidate)):
        if not _cohort_complete(summary, size):
            blockers.append(label + "_incomplete_or_incomparable")
    for label, rows, expected_kind in (("observation", packet.observed, "synthetic_observation"),
                                      ("baseline_replay", packet.baseline_replay, "controlled_replay"),
                                      ("candidate_replay", packet.candidate_replay, "controlled_replay")):
        if any(row.kind != expected_kind for row in rows):
            blockers.append(label + "_evidence_kind_mismatch")
    blockers.extend(f"artifact:{name}:{status}" for name, status in evidence.items() if status != "AVAILABLE")
    if packet.recovery_target is None:
        blockers.append("missing_recovery_target")
    elif packet.recovery_target != packet.baseline:
        blockers.append("incompatible_recovery_target")
    observed_complete = _cohort_complete(observed, size)
    contract = "UNKNOWN" if not observed_complete else ("PASS" if _passes(observed, size) else "FAIL")
    if not _passes(baseline, size):
        blockers.append("baseline_contract_not_established")
    observation_values = {r.request_id: (r.raw_value, r.model_input, r.feature_missing, r.fallback_used,
                                       r.value_revision, r.source_cutoff, r.source_versions) for r in packet.observed}
    replay_values = {r.request_id: (r.raw_value, r.model_input, r.feature_missing, r.fallback_used,
                                  r.value_revision, r.source_cutoff, r.source_versions) for r in packet.candidate_replay}
    if observation_values != replay_values:
        blockers.append("observation_replay_disagreement")
    if contract == "FAIL" and (observation_values != replay_values or _passes(candidate, size)):
        blockers.append("candidate_failure_not_reproduced")
    # Re-run supplied replay rows against their declared implementations, binding
    # their numbers to the retained inputs rather than trusting a report label.
    if not blockers or all(not b.startswith(("input_", "release_")) for b in blockers):
        try:
            if packet.baseline_replay != replay(packet.trace, packet.cohort, packet.baseline):
                blockers.append("baseline_replay_not_reproducible")
            if packet.candidate_replay != replay(packet.trace, packet.cohort, packet.candidate):
                blockers.append("candidate_replay_not_reproducible")
        except (ValueError, TypeError):
            blockers.append("controlled_replay_failed")
    action = "HOLD" if blockers else ("ROLLBACK" if contract == "FAIL" else "CONTINUE")
    return {"contract": contract, "action": action, "blockers": blockers,
            "observation": observed, "baseline_replay": baseline, "candidate_replay": candidate,
            "artifact_status": evidence,
            "scope": "Synthetic evidence; ROLLBACK is a recommendation for a local simulation only."}


def simulate_recovery(packet: Packet, *, checked_at: int = 626) -> dict:
    if checked_at <= packet.now:
        raise ValueError("recovery check must follow decision time")
    at_check = replace(packet, now=checked_at)
    decision = decide(at_check)
    if decision["action"] != "ROLLBACK":
        return {"outcome": "HOLD", "blockers": decision["blockers"] or ["no_rollback_recommendation"],
                "external_action": False}
    rows = replay(packet.trace, packet.cohort, packet.recovery_target, kind="recovery_check")
    summary = summarize(rows, packet.trace, packet.context, BASELINE, packet.cohort)
    fresh = all(row.kind == "recovery_check" for row in rows)
    return {"outcome": "RECOVERED" if fresh and _passes(summary, len(packet.cohort)) else "FAIL",
            "checked_at": checked_at, "external_action": False,
            "phase": "fresh_post_restore_replay", "attempt_id": f"local-restore-{checked_at}",
            "scope": "Local replay of the identical requests; not proof of production recovery.",
            "restored_release": packet.recovery_target.release_id,
            "rows": _plain(rows),
            "raw_values": [r.raw_value for r in rows], "model_values": [r.model_input for r in rows],
            "checks": summary}


def evidence_report(packet: Packet | None = None) -> dict:
    packet = packet or build_change_packet()
    return {"scope": "Entirely fictional evidence packet, clocks, inventory and outcomes.",
            "change": {"deployed_at": 620, "baseline": _plain(packet.baseline), "candidate": _plain(packet.candidate)},
            "observation": {"cohort": _plain(packet.cohort), "rows": _plain(packet.observed),
                            "statement": "Four synthetic post-change requests logged 180; eligible policy remains 85.",
                            "limitation": "Timing alone does not identify the cause."},
            "hypothesis": "The candidate adds full snapshots 50 + 45 + 85 instead of replacing the cell.",
            "controlled_replay": {"snapshots": _plain(packet.trace.publications),
                                  "baseline_rows": _plain(packet.baseline_replay),
                                  "candidate_rows": _plain(packet.candidate_replay),
                                  "limitation": "One fixed input/cohort counterexample, not general causal proof."},
            "permissions_and_retention": _plain(packet.inventory),
            "decision": decide(packet), "recovery_check": simulate_recovery(packet)}


def write_outputs(output_dir: str | Path) -> dict:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    output = {"base_report.json": base_report(), "evidence_packet.json": evidence_report()}
    for name, value in output.items():
        (directory / name).write_text(canonical_json(value), encoding="utf-8")
    return {"base_full_parity": "3/6", "candidate_full_parity": "0/4",
            "baseline_replay_full_parity": "4/4", "decision": output["evidence_packet.json"]["decision"]["action"],
            "recovery": output["evidence_packet.json"]["recovery_check"]["outcome"]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="generated")
    args = parser.parse_args()
    print(canonical_json(write_outputs(args.output_dir)), end="")
