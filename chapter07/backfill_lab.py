"""Chapter 7: deterministic local backfills; Python 3.12, standard library.

This single-process teaching store is not a concurrent or crash-durable
database. SHA-256 detects accidental changes, not an adversary who can rewrite
both data and its hashes. The original Chapters 1–2 module is vendored unchanged.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import platform
import re
import sys

from foundations_lab import (ContractError, Revision, _history, _identity,
                            _integer, ledger_from_dict, selected_revisions)


ROOT = Path(__file__).parent


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def decode(data: bytes) -> object:
    try:
        return json.loads(data, object_pairs_hook=_pairs)
    except (ValueError, UnicodeError) as error:
        raise ContractError(f"invalid JSON: {error}") from error


def _exact(value: object, fields: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ContractError(f"{name} must have exactly {sorted(fields)}")
    return value


def _array(value: object, name: str) -> list:
    if not isinstance(value, list):
        raise ContractError(f"{name} must be an array")
    return value


def _hash(value: object) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ContractError("expected a lowercase SHA-256 digest")


def _dataset_id(value: object) -> None:
    if not isinstance(value, str) or not value.startswith("ds_"):
        raise ContractError("invalid dataset ID")
    _hash(value[3:])


def _read_canonical(path: Path) -> object:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ContractError(f"missing or unreadable artifact: {path.name}") from error
    result = decode(raw)
    if canonical(result) != raw:
        raise ContractError(f"noncanonical artifact bytes: {path.name}")
    return result


def _new_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ContractError(f"refuse to replace immutable artifact: {path.name}")
        return
    with path.open("xb") as handle:
        handle.write(data)


def _replace(path: Path, data: bytes) -> None:
    """Local replace, with no fsync, writer lock or crash-recovery promise."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


@dataclass(frozen=True)
class SourceSnapshot:
    history: tuple[Revision, ...]

    def __post_init__(self) -> None:
        ordered = _history(self.history, allow_restore=False)
        if any(row.op != "upsert" for row in ordered):
            raise ContractError("Chapter 7 snapshots use upserts only")
        object.__setattr__(self, "history", ordered)

    @property
    def bytes(self) -> bytes:
        return canonical([asdict(row) for row in self.history])

    @property
    def sha256(self) -> str:
        return digest(self.bytes)


def source_from_fixture(name: str = "base") -> SourceSnapshot:
    if name not in {"base", "chapter7_extension"}:
        raise ContractError("unknown Chapter 7 fixture")
    ledger = ledger_from_dict(decode((ROOT / "fixtures" / f"{name}.json").read_bytes()))
    return SourceSnapshot(ledger.history)


@dataclass(frozen=True)
class Decision:
    decision_id: str
    customer_id: str
    decision_at: int

    def __post_init__(self) -> None:
        _identity(self.decision_id, "decision_id")
        _identity(self.customer_id, "customer_id")
        _integer(self.decision_at, "decision_at")


@dataclass(frozen=True)
class Coverage:
    """An explicit completeness assertion, not inferred from returned rows.

    history_known describes events in [event_start,event_end) for this
    customer through available_through. This small lab permits one
    declaration per customer. Unknown history yields None, never zero.
    """
    customer_id: str
    event_start: int
    event_end: int
    available_through: int
    history_known: bool = True

    def __post_init__(self) -> None:
        _identity(self.customer_id, "customer_id")
        for name in ("event_start", "event_end", "available_through"):
            _integer(getattr(self, name), name)
        if self.event_start >= self.event_end:
            raise ContractError("coverage interval must be nonempty")
        if type(self.history_known) is not bool:
            raise ContractError("history_known must be boolean")


@dataclass(frozen=True)
class Definition:
    window_minutes: int = 60
    mode: str = "historical"
    corrected_cutoff: int | None = None
    feature_name: str = "spend_before_decision"

    def __post_init__(self) -> None:
        _integer(self.window_minutes, "window_minutes", 1)
        if self.feature_name != "spend_before_decision":
            raise ContractError("unsupported feature_name")
        if self.mode not in {"historical", "corrected"}:
            raise ContractError("mode must be historical or corrected")
        if self.mode == "historical" and self.corrected_cutoff is not None:
            raise ContractError("historical mode has no corrected cutoff")
        if self.mode == "corrected":
            _integer(self.corrected_cutoff, "corrected_cutoff")


def local_code() -> tuple[tuple[str, str], ...]:
    return tuple((name, digest((ROOT / name).read_bytes()))
                 for name in ("backfill_lab.py", "foundations_lab.py"))


def local_runtime() -> str:
    if sys.version_info < (3, 12):
        raise ContractError("this lab requires Python 3.12 or newer")
    return f"{platform.python_implementation()} {platform.python_version()}"


@dataclass(frozen=True)
class RunSpec:
    source: SourceSnapshot
    decisions: tuple[Decision, ...]
    coverage: tuple[Coverage, ...]
    definition: Definition
    code: tuple[tuple[str, str], ...]
    runtime: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceSnapshot) or not isinstance(self.definition, Definition):
            raise ContractError("source and definition must be validated objects")
        decisions = tuple(self.decisions)
        coverage = tuple(self.coverage)
        if not decisions or not all(isinstance(row, Decision) for row in decisions):
            raise ContractError("decisions must be a nonempty list of Decision objects")
        if not all(isinstance(row, Coverage) for row in coverage):
            raise ContractError("coverage must contain Coverage objects")
        if len({row.decision_id for row in decisions}) != len(decisions):
            raise ContractError("duplicate decision_id, identical or conflicting")
        if len({row.customer_id for row in coverage}) != len(coverage):
            raise ContractError("duplicate coverage customer_id")
        object.__setattr__(self, "decisions", tuple(sorted(decisions, key=lambda row: row.decision_id)))
        object.__setattr__(self, "coverage", tuple(sorted(coverage, key=lambda row: row.customer_id)))
        code = tuple(tuple(item) for item in self.code)
        if tuple(item[0] for item in code if len(item) == 2) != ("backfill_lab.py", "foundations_lab.py"):
            raise ContractError("code identity requires the two exact lab modules")
        for _, value in code:
            _hash(value)
        object.__setattr__(self, "code", code)
        _identity(self.runtime, "runtime")
        declared = {row.customer_id: row for row in coverage}
        for decision in decisions:
            start = decision.decision_at - self.definition.window_minutes
            cutoff = self.cutoff(decision)
            proof = declared.get(decision.customer_id)
            if start < 0 or cutoff < decision.decision_at:
                raise ContractError("invalid event window or knowledge cutoff")
            if proof is None or not (proof.event_start <= start
                    and proof.event_end >= decision.decision_at
                    and proof.available_through >= cutoff):
                raise ContractError(f"missing complete coverage for {decision.decision_id}")

    def cutoff(self, decision: Decision) -> int:
        return (decision.decision_at if self.definition.mode == "historical"
                else self.definition.corrected_cutoff)

    def to_dict(self) -> dict:
        return {"schema_version": 1, "source": [asdict(row) for row in self.source.history],
                "source_sha256": self.source.sha256,
                "decisions": [asdict(row) for row in self.decisions],
                "coverage": [asdict(row) for row in self.coverage],
                "definition": asdict(self.definition), "code": dict(self.code),
                "runtime": self.runtime}

    @property
    def sha256(self) -> str:
        return digest(canonical(self.to_dict()))

    @property
    def dataset_id(self) -> str:
        return "ds_" + self.sha256


def make_spec(source: SourceSnapshot | None = None, *,
              decisions: tuple[Decision, ...] | None = None,
              coverage: tuple[Coverage, ...] | None = None,
              definition: Definition | None = None) -> RunSpec:
    return RunSpec(source if source is not None else source_from_fixture(),
                   decisions if decisions is not None else (
                       Decision("D1", "C1", 600), Decision("D2", "C1", 610),
                       Decision("X1", "C9", 610)),
                   coverage if coverage is not None else (
                       Coverage("C1", 0, 641, 640), Coverage("C9", 0, 641, 640)),
                   definition if definition is not None else Definition(),
                   local_code(), local_runtime())


def spec_from_dict(value: object) -> RunSpec:
    value = _exact(value, {"schema_version", "source", "source_sha256", "decisions",
                          "coverage", "definition", "code", "runtime"}, "run specification")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ContractError("unsupported specification schema")
    def records(name: str, cls: type) -> tuple:
        result = []
        for row in _array(value[name], name):
            _exact(row, set(cls.__dataclass_fields__), name)
            result.append(cls(**row))
        return tuple(result)
    source = SourceSnapshot(records("source", Revision))
    if source.sha256 != value["source_sha256"]:
        raise ContractError("source bytes do not match source fingerprint")
    _exact(value["definition"], set(Definition.__dataclass_fields__), "definition")
    _exact(value["code"], {"backfill_lab.py", "foundations_lab.py"}, "code")
    result = RunSpec(source, records("decisions", Decision), records("coverage", Coverage),
                     Definition(**value["definition"]), tuple(sorted(value["code"].items())),
                     value["runtime"])
    if result.to_dict() != value:
        raise ContractError("specification lists are not canonical")
    return result


def _local_execution(spec: RunSpec) -> None:
    if spec.code != local_code() or spec.runtime != local_runtime():
        raise ContractError("code/runtime mismatch: reproduce the recorded execution environment")


@dataclass(frozen=True)
class FeatureRecord:
    decision_id: str
    customer_id: str
    decision_at: int
    window_start: int
    window_end: int
    known_at: int
    value: int | None
    contributors: tuple[tuple[str, int], ...]
    source_sha256: str
    spec_sha256: str

    def __post_init__(self) -> None:
        Decision(self.decision_id, self.customer_id, self.decision_at)
        for name in ("window_start", "window_end", "known_at"):
            _integer(getattr(self, name), name)
        if self.value is not None:
            _integer(self.value, "value")
        if not self.window_start < self.window_end == self.decision_at <= self.known_at:
            raise ContractError("invalid feature record window")
        contributors = tuple(tuple(key) for key in self.contributors)
        for key in contributors:
            if len(key) != 2:
                raise ContractError("invalid contributor key")
            _identity(key[0], "contributor event_id")
            _integer(key[1], "contributor revision", 1)
        if len(set(key[0] for key in contributors)) != len(contributors):
            raise ContractError("duplicate contributor event")
        object.__setattr__(self, "contributors", contributors)
        _hash(self.source_sha256)
        _hash(self.spec_sha256)

    def to_dict(self) -> dict:
        value = asdict(self)
        value["contributors"] = [list(key) for key in self.contributors]
        return value


def materialize(spec: RunSpec) -> tuple[FeatureRecord, ...]:
    _local_execution(spec)
    result = []
    coverage = {row.customer_id: row for row in spec.coverage}
    for decision in spec.decisions:
        start = decision.decision_at - spec.definition.window_minutes
        cutoff = spec.cutoff(decision)
        selected = selected_revisions(spec.source.history, known_at=cutoff)
        included = tuple(row for row in selected if row.customer_id == decision.customer_id
                         and start <= row.event_time < decision.decision_at and row.op == "upsert")
        result.append(FeatureRecord(decision.decision_id, decision.customer_id,
                                   decision.decision_at, start, decision.decision_at, cutoff,
                                   (sum(row.amount for row in included)
                                    if coverage[decision.customer_id].history_known else None),
                                   tuple((row.event_id, row.revision) for row in included),
                                   spec.source.sha256, spec.sha256))
    return tuple(result)


@dataclass(frozen=True)
class Dataset:
    spec: RunSpec
    records: tuple[FeatureRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.spec, RunSpec):
            raise ContractError("dataset requires a RunSpec")
        records = tuple(self.records)
        if not all(isinstance(row, FeatureRecord) for row in records):
            raise ContractError("dataset requires FeatureRecord objects")
        object.__setattr__(self, "records", records)

    @property
    def dataset_id(self) -> str:
        return self.spec.dataset_id

    @property
    def manifest(self) -> dict:
        return {"schema_version": 1, "dataset_id": self.dataset_id,
                "spec": self.spec.to_dict(), "record_count": len(self.records),
                "records_sha256": digest(canonical([row.to_dict() for row in self.records]))}

    def to_dict(self) -> dict:
        manifest = self.manifest
        return {"manifest": manifest, "manifest_sha256": digest(canonical(manifest)),
                "records": [row.to_dict() for row in self.records]}


def validate_dataset(value: object) -> Dataset:
    value = _exact(value, {"manifest", "manifest_sha256", "records"}, "dataset")
    manifest = _exact(value["manifest"], {"schema_version", "dataset_id", "spec",
                                        "record_count", "records_sha256"}, "manifest")
    if digest(canonical(manifest)) != value["manifest_sha256"]:
        raise ContractError("manifest digest mismatch")
    spec = spec_from_dict(manifest["spec"])
    expected = Dataset(spec, materialize(spec))
    # Compare canonical bytes, not Python equality: bool is not the integer 1.
    # Recomputing all records checks keys, order, values, provenance and hashes.
    if canonical(expected.to_dict()) != canonical(value):
        raise ContractError("dataset differs from its complete recomputed contract")
    return expected


def dataset_path(store: Path, dataset_id: str) -> Path:
    _dataset_id(dataset_id)
    return Path(store) / "datasets" / f"{dataset_id}.json"


def load_dataset(store: Path, dataset_id: str) -> Dataset:
    dataset = validate_dataset(_read_canonical(dataset_path(store, dataset_id)))
    if dataset.dataset_id != dataset_id:
        raise ContractError("dataset filename identity mismatch")
    return dataset


def _attempt(store: Path, attempt_id: str) -> Path:
    if not isinstance(attempt_id, str) or re.fullmatch(r"[A-Za-z0-9_-]+", attempt_id) is None:
        raise ContractError("attempt_id must contain only letters, digits, underscore or hyphen")
    return Path(store) / "staging" / attempt_id


def _checkpoint(folder: Path, spec: RunSpec, chunk_size: int) -> tuple[dict, list[dict]]:
    _local_execution(spec)
    if canonical(_read_canonical(folder / "spec.json")) != canonical(spec.to_dict()):
        raise ContractError("attempt is bound to a different fixed run specification")
    checkpoint = _read_canonical(folder / "checkpoint.json")
    try:
        expected_digest = (folder / "checkpoint.sha256").read_text(encoding="ascii")
    except (OSError, UnicodeError) as error:
        raise ContractError("missing or unreadable checkpoint digest") from error
    if digest((folder / "checkpoint.json").read_bytes()) + "\n" != expected_digest:
        raise ContractError("checkpoint digest mismatch")
    _exact(checkpoint, {"schema_version", "spec_sha256", "chunk_size", "next_index", "chunks"}, "checkpoint")
    if (type(checkpoint["schema_version"]) is not int or checkpoint["schema_version"] != 1
            or checkpoint["spec_sha256"] != spec.sha256
            or type(checkpoint["chunk_size"]) is not int or checkpoint["chunk_size"] != chunk_size):
        raise ContractError("checkpoint specification/chunk-size mismatch")
    _integer(checkpoint["next_index"], "next_index")
    chunks = _array(checkpoint["chunks"], "chunks")
    expected = [row.to_dict() for row in materialize(spec)]
    assembled = []
    for index, entry in enumerate(chunks):
        _exact(entry, {"index", "count", "sha256"}, "chunk entry")
        target = expected[index * chunk_size:(index + 1) * chunk_size]
        if type(entry["index"]) is not int or entry["index"] != index or not target:
            raise ContractError("noncontiguous or extra chunk")
        if type(entry["count"]) is not int or entry["count"] != len(target):
            raise ContractError("chunk row count mismatch")
        path = folder / f"chunk_{index:06d}.json"
        actual = _read_canonical(path)
        if digest(path.read_bytes()) != entry["sha256"] or canonical(actual) != canonical(target):
            raise ContractError("chunk bytes/digest do not match fixed run specification")
        assembled.extend(actual)
    if checkpoint["next_index"] != len(assembled):
        raise ContractError("checkpoint next_index does not match verified chunks")
    expected_files = {f"chunk_{index:06d}.json" for index in range(len(chunks))}
    if {path.name for path in folder.glob("chunk_*.json")} != expected_files:
        raise ContractError("untracked chunk: interrupted write requires manual recovery or a new attempt")
    return checkpoint, assembled


def _save_checkpoint(folder: Path, checkpoint: dict) -> None:
    raw = canonical(checkpoint)
    _replace(folder / "checkpoint.json", raw)
    _replace(folder / "checkpoint.sha256", (digest(raw) + "\n").encode("ascii"))


@dataclass(frozen=True)
class BuildProgress:
    dataset_id: str
    next_index: int
    total: int
    complete: bool


def stage_build(store: Path, attempt_id: str, spec: RunSpec, *, chunk_size: int = 1,
                stop_after_chunks: int | None = None) -> BuildProgress:
    """Stop only at a verified chunk boundary; resume rechecks every disk byte.

    stop_after_chunks counts newly written chunks in this call. Replaying a
    complete attempt writes no additional rows. Arbitrary crash recovery is
    intentionally unsupported: reject inconsistent or orphaned state.
    """
    _integer(chunk_size, "chunk_size", 1)
    if stop_after_chunks is not None:
        _integer(stop_after_chunks, "stop_after_chunks")
    _local_execution(spec)
    folder = _attempt(store, attempt_id)
    if not folder.exists():
        folder.mkdir(parents=True)
        _new_file(folder / "spec.json", canonical(spec.to_dict()))
        _save_checkpoint(folder, {"schema_version": 1, "spec_sha256": spec.sha256,
                                 "chunk_size": chunk_size, "next_index": 0, "chunks": []})
    checkpoint, _ = _checkpoint(folder, spec, chunk_size)
    rows = [row.to_dict() for row in materialize(spec)]
    written = 0
    while checkpoint["next_index"] < len(rows):
        if stop_after_chunks is not None and written >= stop_after_chunks:
            break
        start = checkpoint["next_index"]
        chunk = rows[start:start + chunk_size]
        index = len(checkpoint["chunks"])
        raw = canonical(chunk)
        _new_file(folder / f"chunk_{index:06d}.json", raw)
        checkpoint["chunks"].append({"index": index, "count": len(chunk), "sha256": digest(raw)})
        checkpoint["next_index"] += len(chunk)
        _save_checkpoint(folder, checkpoint)
        written += 1
    verified, _ = _checkpoint(folder, spec, chunk_size)
    return BuildProgress(spec.dataset_id, verified["next_index"], len(rows),
                         verified["next_index"] == len(rows))


def publish_dataset(store: Path, attempt_id: str, spec: RunSpec, *, chunk_size: int = 1) -> Dataset:
    """Validate complete staging before publishing one retained immutable file."""
    _integer(chunk_size, "chunk_size", 1)
    checkpoint, rows = _checkpoint(_attempt(store, attempt_id), spec, chunk_size)
    if checkpoint["next_index"] != len(spec.decisions):
        raise ContractError("cannot publish an incomplete dataset")
    dataset = Dataset(spec, materialize(spec))
    candidate = dataset.to_dict()
    candidate["records"] = rows
    validate_dataset(candidate)
    _new_file(dataset_path(store, dataset.dataset_id), canonical(candidate))
    return load_dataset(store, dataset.dataset_id)


@dataclass(frozen=True)
class ReleaseToken:
    dataset_id: str | None = None
    generation: int = 0

    def __post_init__(self) -> None:
        _integer(self.generation, "generation")
        if self.dataset_id is not None:
            _dataset_id(self.dataset_id)
        if (self.dataset_id is None) != (self.generation == 0):
            raise ContractError("only generation zero has no dataset")


class ReleaseRegistry:
    """Expected-current CAS in one process, not a lock-free distributed CAS."""
    def __init__(self, store: Path):
        self.store = Path(store)
        self.path = self.store / "releases.json"

    @staticmethod
    def _channel(channel: str) -> None:
        if channel not in {"historical", "historical_30m", "corrected"}:
            raise ContractError("unknown release channel")

    @staticmethod
    def channel_definition(channel: str) -> Definition:
        """Three explicit consumer contracts, fixed for this teaching lab."""
        ReleaseRegistry._channel(channel)
        return {"historical": Definition(),
                "historical_30m": Definition(window_minutes=30),
                "corrected": Definition(mode="corrected", corrected_cutoff=640)}[channel]

    def _read(self) -> dict:
        if not self.path.exists():
            return {"schema_version": 1, "channels": {}, "history": []}
        value = _read_canonical(self.path)
        _exact(value, {"schema_version", "channels", "history"}, "registry")
        if type(value["schema_version"]) is not int or value["schema_version"] != 1:
            raise ContractError("unsupported registry schema")
        if not isinstance(value["channels"], dict):
            raise ContractError("channels must be an object")
        reconstructed = {}
        for sequence, entry in enumerate(_array(value["history"], "release history"), 1):
            _exact(entry, {"sequence", "channel", "action", "before", "after"}, "audit entry")
            self._channel(entry["channel"])
            if type(entry["sequence"]) is not int or entry["sequence"] != sequence:
                raise ContractError("noncontiguous audit sequence")
            if entry["action"] not in {"promote", "rollback"}:
                raise ContractError("unknown audit action")
            for name in ("before", "after"):
                _exact(entry[name], {"dataset_id", "generation"}, "release token")
                ReleaseToken(**entry[name])
            before = reconstructed.get(entry["channel"], asdict(ReleaseToken()))
            if entry["before"] != before or entry["after"]["generation"] != before["generation"] + 1:
                raise ContractError("audit transition mismatch")
            reconstructed[entry["channel"]] = entry["after"]
        if canonical(reconstructed) != canonical(value["channels"]):
            raise ContractError("release pointer disagrees with audit history")
        return value

    def current(self, channel: str) -> ReleaseToken:
        self._channel(channel)
        return ReleaseToken(**self._read()["channels"].get(channel, asdict(ReleaseToken())))

    def history(self) -> tuple[dict, ...]:
        return tuple(self._read()["history"])

    def promote(self, channel: str, dataset_id: str, *, expected_current: ReleaseToken) -> ReleaseToken:
        return self._move(channel, dataset_id, expected_current, "promote")

    def rollback(self, channel: str, dataset_id: str, *, expected_current: ReleaseToken) -> ReleaseToken:
        return self._move(channel, dataset_id, expected_current, "rollback")

    def _move(self, channel: str, dataset_id: str, expected: ReleaseToken, action: str) -> ReleaseToken:
        self._channel(channel)
        if not isinstance(expected, ReleaseToken):
            raise ContractError("expected_current must be a ReleaseToken")
        registry = self._read()
        current = ReleaseToken(**registry["channels"].get(channel, asdict(ReleaseToken())))
        if current != expected:
            raise ContractError("stale release token: dataset ID and generation must both match")
        dataset = load_dataset(self.store, dataset_id)
        if dataset.spec.definition != self.channel_definition(channel):
            raise ContractError("semantic definition cannot be promoted to this channel")
        if action == "rollback" and not any(entry["channel"] == channel
                and entry["after"]["dataset_id"] == dataset_id for entry in registry["history"]):
            raise ContractError("rollback target was never released on this channel")
        if dataset_id == current.dataset_id:
            return current
        target = ReleaseToken(dataset_id, current.generation + 1)
        registry["channels"][channel] = asdict(target)
        registry["history"].append({"sequence": len(registry["history"]) + 1,
                                    "channel": channel, "action": action,
                                    "before": asdict(current), "after": asdict(target)})
        _replace(self.path, canonical(registry))
        return self.current(channel)


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    dataset_id: str

    def __post_init__(self) -> None:
        _identity(self.experiment_id, "experiment_id")
        _dataset_id(self.dataset_id)

    def read(self, store: Path) -> Dataset:
        return load_dataset(store, self.dataset_id)


def fixture_specs() -> dict[str, RunSpec]:
    extended = source_from_fixture("chapter7_extension")
    return {"baseline": make_spec(),
            "extended_historical": make_spec(extended),
            "corrected": make_spec(extended, definition=Definition(mode="corrected", corrected_cutoff=640)),
            "new_definition": make_spec(extended, definition=Definition(window_minutes=30))}


def values(spec: RunSpec) -> list[int | None]:
    return [row.value for row in materialize(spec)]
