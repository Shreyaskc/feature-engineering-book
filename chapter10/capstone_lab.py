"""Chapter 10: a deterministic event-log-to-feature-dataset capstone.

Python 3.12, standard library only. No model, service, or network calls.
The two vendored modules retain their original implementation bytes.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import platform
from typing import Iterable

import foundations_lab as foundation
import parity_lab as serving

ROOT = Path(__file__).resolve().parent
IMPLEMENTATIONS = ("snapshot_baseline", "contract_pipeline")
REQUESTS = tuple((f"Q{i}", t) for i, t in enumerate(
    (599, 600, 605, 606, 610, 620)))
CODE_FILES = ("capstone_lab.py", "foundations_lab.py", "parity_lab.py")
ARTIFACT_NAMES = (
    "source_snapshot.json", "baseline_dataset.json", "improved_dataset.json",
    "publications.json", "lookups.json", "comparison.json", "audit.json",
    "continuity.json")


class CapstoneError(ValueError):
    """A named capstone input, evidence, or artifact contract failed."""


def canonical(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def digest(value: object) -> str:
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def _mode(implementation: str) -> None:
    if implementation not in IMPLEMENTATIONS:
        raise CapstoneError("implementation must be snapshot_baseline or contract_pipeline")


@dataclass(frozen=True)
class Decision:
    row_id: str
    customer_id: str
    decision_at: int
    history_known: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.row_id, str) or not self.row_id.strip():
            raise CapstoneError("decision row_id is required")
        if not isinstance(self.customer_id, str) or not self.customer_id.strip():
            raise CapstoneError("decision customer_id is required")
        if type(self.decision_at) is not int or self.decision_at < 60:
            raise CapstoneError("decision_at must be an integer >= 60")
        if type(self.history_known) is not bool:
            raise CapstoneError("history_known must be a boolean")


DECISIONS = (Decision("D1", "C1", 600), Decision("D2", "C1", 610),
             Decision("Z1", "C9", 600), Decision("U1", "C1", 600, False))


@dataclass(frozen=True)
class Case:
    name: str
    ledger: foundation.Ledger
    audit_at: int = 620
    decisions: tuple[Decision, ...] = DECISIONS

    def __post_init__(self) -> None:
        if self.name not in ("base", "challenge"):
            raise CapstoneError("case must be base or challenge")
        if type(self.audit_at) is not int or self.audit_at < 610:
            raise CapstoneError("audit_at must be an integer >= 610")
        if not isinstance(self.ledger, foundation.Ledger):
            raise CapstoneError("case ledger must be a Ledger")
        if not isinstance(self.decisions, tuple) or not self.decisions:
            raise CapstoneError("decisions must be a nonempty tuple")
        if any(not isinstance(row, Decision) for row in self.decisions):
            raise CapstoneError("decisions must contain Decision records")
        if len({row.row_id for row in self.decisions}) != len(self.decisions):
            raise CapstoneError("duplicate decision row_id")
        if any(row.decision_at > self.audit_at for row in self.decisions):
            raise CapstoneError("audit must not precede a decision")
        adapt_source(self.ledger)


def adapt_source(ledger: foundation.Ledger) -> serving.SourceHistory:
    """Explicitly narrow the foundations contract to this upsert-only sink.

    Foundations supports tombstones/restoration. This serving adapter does not;
    silently dropping either would invent lineage. Reject before conversion.
    """
    if not isinstance(ledger, foundation.Ledger):
        raise CapstoneError("adapter requires a Ledger")
    if ledger.allow_restore:
        raise CapstoneError("serving adapter does not support restoration")
    if any(row.op != "upsert" for row in ledger.history):
        raise CapstoneError("serving adapter does not support deletion")
    return serving.SourceHistory(
        serving.SourceRevision(row.event_id, row.revision, row.customer_id,
                               row.event_time, row.available_at, row.amount)
        for row in ledger.history)


def input_files(name: str) -> tuple[str, ...]:
    if name not in ("base", "challenge"):
        raise CapstoneError("case must be base or challenge")
    extension = "late_arrival" if name == "base" else "challenge"
    return ("fixtures/base.json", f"fixtures/{extension}.json")


def load_case(name: str = "base") -> Case:
    ledgers = [foundation.ledger_from_dict(json.loads(
        (ROOT / path).read_text(encoding="utf-8"))) for path in input_files(name)]
    # Reject unsupported extension metadata before combining ledgers.
    for ledger in ledgers:
        adapt_source(ledger)
    return Case(name, foundation.ingest(ledgers[0], ledgers[1].deliveries))


def source_payload(ledger: foundation.Ledger) -> dict:
    return {"schema_version": 1, "allow_restore": ledger.allow_restore,
            "deliveries": [asdict(row) for row in ledger.deliveries]}


def source_identity(ledger: foundation.Ledger) -> str:
    """Source-version identity ignores harmless transport duplicates/order."""
    return digest([asdict(row) for row in ledger.history])


def build_dataset(case: Case, implementation: str = "contract_pipeline") -> list[dict]:
    """Feature rows only. A cutoff and selected contributing versions per row.

    Baseline intentionally looks ahead to audit_at. Both paths preserve an
    explicit unknown-history marker; missing is never silently changed to zero.
    """
    _mode(implementation)
    result = []
    for decision in case.decisions:
        cutoff = (case.audit_at if implementation == "snapshot_baseline"
                  else decision.decision_at)
        start, end = decision.decision_at - 60, decision.decision_at
        value = foundation.spend_in_window(
            case.ledger.history, decision.customer_id, window_start=start,
            window_end=end, known_at=cutoff,
            history_known=decision.history_known)
        selected = foundation.selected_revisions(case.ledger.history,
                                                  known_at=cutoff)
        versions = [[row.event_id, row.revision] for row in selected
                    if decision.history_known and row.op == "upsert"
                    and row.customer_id == decision.customer_id
                    and start <= row.event_time < end]
        result.append({**asdict(decision), "window_start": start,
                       "window_end": end, "source_cutoff": cutoff,
                       "value": value, "missing": value is None,
                       "source_versions": versions,
                       "definition_id": "known_spend_60m_v1"})
    return result


def publications(case: Case) -> tuple[serving.PublishedRevision, ...]:
    return serving.build_publications(adapt_source(case.ledger), serving.KEY,
                                      initial_at=600, deadline=610)


def consume_snapshots(records: Iterable[serving.PublishedRevision],
                      implementation: str = "contract_pipeline") -> dict:
    """Consume one full feature key; replay and reordering are idempotent.

    Canonicalizing transport deliveries is shared by both paths so that the
    comparison isolates addition versus replacement. Baseline still adds each
    unique *full* snapshot once, which is the deliberately incorrect operation.
    """
    _mode(implementation)
    by_revision = {}
    for record in records:
        if not isinstance(record, serving.PublishedRevision):
            raise CapstoneError("consumer requires PublishedRevision records")
        if record.key != serving.KEY or record.contracts != serving.CONTRACTS:
            raise CapstoneError("publication semantic key or contract mismatch")
        if type(record.value) is not int or record.value < 0:
            raise CapstoneError("publication value must be a nonnegative integer")
        old = by_revision.get(record.revision)
        if old is not None and old != record:
            raise CapstoneError("conflicting publication revision")
        if (record.source_cutoff != record.published_at
                or not 600 <= record.published_at <= 610):
            raise CapstoneError("publication violates cutoff/deadline contract")
        pairs = record.source_versions
        if (not pairs and record.value != 0) or any(
                            len(pair) != 2 or not isinstance(pair[0], str)
                            or not pair[0] or type(pair[1]) is not int
                            or pair[1] < 1 for pair in pairs):
            raise CapstoneError("publication source-version metadata is required")
        if len({pair[0] for pair in pairs}) != len(pairs):
            raise CapstoneError("publication source versions must select one per event")
        by_revision[record.revision] = record
    ordered = sorted(by_revision.values(), key=lambda record: record.revision)
    if any(left.published_at > right.published_at
           for left, right in zip(ordered, ordered[1:])):
        raise CapstoneError("publication time must not decrease by revision")
    if not ordered:
        return {"value": None, "publication_revisions": [],
                "source_versions": [], "source_cutoff": None}
    final = ordered[-1]
    value = (sum(record.value for record in ordered)
             if implementation == "snapshot_baseline" else final.value)
    inputs = ordered if implementation == "snapshot_baseline" else [final]
    return {"value": value,
            "publication_revisions": [record.revision for record in inputs],
            "source_versions": [list(pair) for pair in final.source_versions],
            "source_cutoff": final.source_cutoff}


def online_lookups(case: Case, implementation: str = "contract_pipeline") -> list[dict]:
    """Separate idealized schedule: all eligible publications visible at once.

    At equal timestamps publication precedes request. There is no cache or
    network-delay simulation here; continuity_report retains the earlier trace.
    """
    _mode(implementation)
    records = publications(case)
    result = []
    for request_id, minute in REQUESTS:
        eligible = tuple(record for record in records
                         if record.published_at <= minute)
        cell = consume_snapshots(eligible, implementation)
        policy = eligible[-1] if eligible else None
        raw = cell["value"]
        result.append({"request_id": request_id, "requested_at": minute,
                       "key": asdict(serving.KEY),
                       "contracts": asdict(serving.CONTRACTS),
                       "implementation": implementation,
                       "raw_value": raw, "lookup_input": 0 if raw is None else raw,
                       "feature_missing": raw is None, "fallback_used": raw is None,
                       "fallback_value": 0 if raw is None else None,
                       "policy_value": None if policy is None else policy.value,
                       "policy_revision": None if policy is None else policy.revision,
                       "latest_input_published_at": (None if policy is None
                                                     else policy.published_at),
                       "returned_publication_revision": (
                           policy.revision if policy is not None
                           and implementation == "contract_pipeline" else None),
                       "returned_published_at": (
                           policy.published_at if policy is not None
                           and implementation == "contract_pipeline" else None),
                       "consumer_inputs": cell,
                       "schedule": "immediate_publication_visibility"})
    return result


def metric(values: Iterable[bool | None]) -> dict:
    """None is explicitly excluded; zero denominator has no numeric rate."""
    values = tuple(values)
    if any(value is not None and type(value) is not bool for value in values):
        raise CapstoneError("metric entries must be booleans or explicit exclusions")
    denominator = sum(value is not None for value in values)
    numerator = sum(value is True for value in values)
    return {"numerator": numerator, "denominator": denominator,
            "excluded": len(values) - denominator, "population": len(values),
            "rate": None if denominator == 0 else numerator / denominator}


def compare(case: Case) -> dict:
    expected = build_dataset(case, "contract_pipeline")
    report = {}
    for mode in IMPLEMENTATIONS:
        dataset = build_dataset(case, mode)
        lookups = online_lookups(case, mode)
        historical = {
            "numeric_parity": metric(
                row["value"] == reference["value"] if reference["history_known"]
                else None for row, reference in zip(dataset, expected)),
            "complete_row_parity": metric(
                row == reference for row, reference in zip(dataset, expected)),
            "missing": metric(row["missing"] for row in dataset),
            "known_zero": metric(row["value"] == 0 and not row["missing"]
                                 for row in dataset)}
        online = {
            "raw_policy_parity": metric(
                row["raw_value"] == row["policy_value"]
                if row["policy_value"] is not None and row["raw_value"] is not None
                else None for row in lookups),
            "missing": metric(row["feature_missing"] for row in lookups),
            "fallback": metric(row["fallback_used"] for row in lookups)}
        report[mode] = {"historical": historical, "online": online}
    return {"scope": "Finite deterministic fixture checks; no statistical or ML claim",
            "decision_ids": [row.row_id for row in case.decisions],
            "request_ids": [row[0] for row in REQUESTS],
            "implementations": report}


def audit_report(case: Case) -> dict:
    history = adapt_source(case.ledger)
    final = publications(case)[-1]
    reference = history.reference(serving.KEY, case.audit_at)
    after_deadline = [[row.event_id, row.revision] for row in case.ledger.history
                      if 610 < row.available_at <= case.audit_at
                      and row.customer_id == "C1" and 540 <= row.event_time < 600]
    return {"case": case.name, "audit_at": case.audit_at,
            "fixed_window": [540, 600], "deadline_inclusive": 610,
            "closed_policy_value": final.value,
            "closed_policy_source_versions": [list(pair) for pair in final.source_versions],
            "audit_source_value": reference.value,
            "audit_source_versions": [list(pair) for pair in reference.source_versions],
            "after_deadline_source_versions": after_deadline,
            "difference": reference.value - final.value,
            "explanation": "Later source evidence is retained for audit; it does not reopen the closed policy output.",
            "rolling_historical_rows": build_dataset(case)[:2]}


def continuity_report() -> dict:
    trace, logs = serving.build_fixture()
    report = serving.reconcile(trace, logs)
    return {"scope": "Unchanged Chapter 6 trace with delayed store and cache",
            "request_ids": [row.request_id for row in logs],
            "request_times": [row.requested_at for row in logs],
            "raw_values": [row.raw_value for row in logs],
            "policy_values": [trace.policy_at(row.requested_at).value for row in logs],
            "source_values": [trace.source.reference(trace.key, row.requested_at).value
                              for row in logs], "metrics": report["metrics"]}


def run_case(case: Case) -> dict:
    return {"case": case.name, "source_identity": source_identity(case.ledger),
            "datasets": {mode: build_dataset(case, mode) for mode in IMPLEMENTATIONS},
            "publications": [asdict(row) for row in publications(case)],
            "lookups": {mode: online_lookups(case, mode) for mode in IMPLEMENTATIONS},
            "comparison": compare(case), "audit": audit_report(case),
            "continuity": continuity_report()}


def artifact_payloads(case: Case) -> dict:
    report = run_case(case)
    return {"source_snapshot.json": source_payload(case.ledger),
            "baseline_dataset.json": report["datasets"]["snapshot_baseline"],
            "improved_dataset.json": report["datasets"]["contract_pipeline"],
            "publications.json": report["publications"],
            "lookups.json": report["lookups"],
            "comparison.json": report["comparison"],
            "audit.json": report["audit"], "continuity.json": report["continuity"]}


def runtime_identity() -> dict:
    return {"implementation": platform.python_implementation(),
            "python_version": platform.python_version(), "dependencies": "stdlib only"}


def make_manifest(case: Case, payloads: dict) -> dict:
    official = load_case(case.name)
    if source_identity(case.ledger) != source_identity(official.ledger):
        raise CapstoneError("retained source disagrees with named input fixtures")
    if case.decisions != DECISIONS or case.audit_at != 620:
        raise CapstoneError("retained cohort disagrees with capstone contract")
    return {"schema_version": 1, "case": case.name, "runtime": runtime_identity(),
            "case_config": {"audit_at": case.audit_at,
                            "decisions": [asdict(row) for row in case.decisions]},
            "code_sha256": {name: sha256((ROOT / name).read_bytes()).hexdigest()
                            for name in CODE_FILES},
            "input_file_sha256": {name: sha256((ROOT / name).read_bytes()).hexdigest()
                                  for name in input_files(case.name)},
            "canonical_source_sha256": source_identity(case.ledger),
            "artifact_sha256": {name: digest(payloads[name]) for name in ARTIFACT_NAMES},
            "contracts": {"historical": "rolling 60 minutes, cutoff=decision_at",
                          "online_key": asdict(serving.KEY),
                          "online_schedule": "immediate_publication_visibility",
                          "initial_at": 600, "deadline_inclusive": 610,
                          "source_adapter": "upsert only; reject deletion/restoration",
                          "missingness": "known empty=0; unknown=None; explicit flags"},
            "training_boundary": {"artifact_kind": "feature_dataset_only",
                                  "labels_present": False, "model_fitted": False,
                                  "required_before_predictive_training": [
                                      "label definition and label availability",
                                      "split and leakage review",
                                      "fit-only preprocessing and state identities",
                                      "model and evaluation contracts"]}}


def persist_run(case: Case, output_dir: Path | str) -> dict:
    """Write artifacts, reread every byte, then freshly recompute them."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise CapstoneError("output directory must be empty")
    payloads = artifact_payloads(case)
    manifest = make_manifest(case, payloads)
    for name, payload in {**payloads, "manifest.json": manifest}.items():
        (output_dir / name).write_text(canonical(payload), encoding="utf-8")
    return verify_artifacts(output_dir)


def verify_artifacts(output_dir: Path | str) -> dict:
    """Validate exact inventory, metadata, retained bytes and recomputation.

    Hashes identify bytes, not authorship. A hostile party replacing all code,
    fixtures and manifests is outside this local integrity check's trust model.
    """
    output_dir = Path(output_dir)
    wanted = set(ARTIFACT_NAMES) | {"manifest.json"}
    if not output_dir.is_dir() or {path.name for path in output_dir.iterdir()} != wanted:
        raise CapstoneError("artifact inventory mismatch")
    try:
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        snapshot = json.loads((output_dir / "source_snapshot.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise CapstoneError("manifest must be an object")
        required = {"schema_version", "case", "runtime", "case_config", "code_sha256",
                    "input_file_sha256", "canonical_source_sha256", "artifact_sha256",
                    "contracts", "training_boundary"}
        if set(manifest) != required:
            raise CapstoneError("manifest fields mismatch")
        config = manifest["case_config"]
        if not isinstance(config, dict) or set(config) != {"audit_at", "decisions"}:
            raise CapstoneError("manifest case_config fields mismatch")
        if not isinstance(config["decisions"], list):
            raise CapstoneError("manifest decisions must be an array")
        case = Case(manifest["case"], foundation.ledger_from_dict(snapshot),
                    config["audit_at"], tuple(Decision(**row) for row in config["decisions"]))
        payloads = artifact_payloads(case)
        expected = make_manifest(case, payloads)
        for name in ("schema_version", "runtime", "code_sha256", "input_file_sha256",
                     "canonical_source_sha256", "contracts", "training_boundary"):
            if manifest[name] != expected[name]:
                raise CapstoneError(f"manifest {name} mismatch")
        if manifest["artifact_sha256"] != expected["artifact_sha256"]:
            raise CapstoneError("manifest artifact digests disagree with recomputation")
        for name in ARTIFACT_NAMES:
            raw = (output_dir / name).read_bytes()
            if sha256(raw).hexdigest() != expected["artifact_sha256"][name]:
                raise CapstoneError(f"artifact content mismatch: {name}")
        if (output_dir / "manifest.json").read_text(encoding="utf-8") != canonical(expected):
            raise CapstoneError("manifest serialization mismatch")
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, KeyError,
            foundation.ContractError) as error:
        raise CapstoneError(f"invalid retained evidence: {error}") from error
    return {"status": "PASS", "case": case.name, "artifacts_verified": len(wanted),
            "canonical_source_sha256": source_identity(case.ledger),
            "recomputed_from_retained_snapshot": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("base", "challenge"), default="base")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "generated" / "base")
    args = parser.parse_args()
    print(canonical(persist_run(load_case(args.case), args.output_dir)), end="")


if __name__ == "__main__":
    main()
