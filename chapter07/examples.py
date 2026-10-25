"""Run the full local lifecycle; optionally retain a reviewable demo store."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import backfill_lab as lab


def _rejected(operation) -> bool:
    try:
        operation()
    except lab.ContractError:
        return True
    raise AssertionError("operation unexpectedly succeeded")


def _report(store: Path) -> dict:
    if store.exists() and any(store.iterdir()):
        raise lab.ContractError("demo --store must be absent or empty")
    specs = lab.fixture_specs()
    baseline = specs["baseline"]
    first = lab.stage_build(store, "baseline", baseline, stop_after_chunks=1)
    resumed = lab.stage_build(store, "baseline", baseline)
    replayed = lab.stage_build(store, "baseline", baseline)
    published = {"baseline": lab.publish_dataset(store, "baseline", baseline)}
    for name, spec in specs.items():
        if name != "baseline":
            lab.stage_build(store, name, spec, chunk_size=2)
            published[name] = lab.publish_dataset(store, name, spec, chunk_size=2)
    registry = lab.ReleaseRegistry(store)
    pinned = lab.Experiment("baseline_trial", baseline.dataset_id)
    lab._new_file(store / "experiments" / "baseline_trial.json", lab.canonical(asdict(pinned)))
    original = lab.dataset_path(store, baseline.dataset_id).read_bytes()
    one = registry.promote("historical", baseline.dataset_id, expected_current=lab.ReleaseToken())
    corrected_rejected = _rejected(lambda: registry.promote(
        "historical", specs["corrected"].dataset_id, expected_current=one))
    new_window_rejected = _rejected(lambda: registry.promote(
        "historical", specs["new_definition"].dataset_id, expected_current=one))
    two = registry.promote("historical", specs["extended_historical"].dataset_id, expected_current=one)
    three = registry.rollback("historical", baseline.dataset_id, expected_current=two)
    stale_rejected = _rejected(lambda: registry.promote(
        "historical", specs["extended_historical"].dataset_id, expected_current=one))
    channel30 = registry.promote("historical_30m", specs["new_definition"].dataset_id,
                                 expected_current=lab.ReleaseToken())
    corrected_channel = registry.promote("corrected", specs["corrected"].dataset_id,
                                         expected_current=lab.ReleaseToken())
    unknown = replace(baseline, coverage=(baseline.coverage[0],
                      replace(baseline.coverage[1], history_known=False)))
    at620 = lab.make_spec(specs["corrected"].source,
                          definition=lab.Definition(mode="corrected", corrected_cutoff=620))
    corrected_records = lab.materialize(specs["corrected"])
    return {
        "fixture_values": {name: lab.values(spec) for name, spec in specs.items()},
        "source_version_counts": {name: len(spec.source.history) for name, spec in specs.items()},
        "distinct_dataset_identities": len({spec.dataset_id for spec in specs.values()}),
        "equal_historical_values_different_identity": (
            lab.values(baseline) == lab.values(specs["extended_historical"])
            and baseline.dataset_id != specs["extended_historical"].dataset_id),
        "unknown_coverage_values": lab.values(unknown),
        "unknown_coverage_changes_identity": unknown.dataset_id != baseline.dataset_id,
        "corrected_view_continuity": {
            "original_event_windows": {
                row.decision_id: [row.window_start, row.window_end] for row in corrected_records},
            "at_cutoff_620": lab.values(at620),
            "at_cutoff_640": lab.values(specs["corrected"]),
            "d1_late_E_reference_at_620": 100,
            "d1_after_B_revision_2_at_640": 102},
        "staging": {"first_next_index": first.next_index, "first_complete": first.complete,
                    "resumed_next_index": resumed.next_index, "resumed_complete": resumed.complete,
                    "replay_unchanged": resumed == replayed,
                    "published_rows": len(published["baseline"].records)},
        "release": {"historical_generations": [one.generation, two.generation, three.generation],
                    "corrected_into_historical_rejected": corrected_rejected,
                    "new_window_into_old_channel_rejected": new_window_rejected,
                    "stale_aba_token_rejected": stale_rejected,
                    "historical_30m_generation": channel30.generation,
                    "corrected_generation": corrected_channel.generation,
                    "rollback_restored_dataset_identity": three.dataset_id == one.dataset_id,
                    "audit_actions": [entry["action"] for entry in registry.history()]},
        "pinned_experiment": {"values": [row.value for row in pinned.read(store).records],
                              "identity_unchanged": pinned.dataset_id == baseline.dataset_id,
                              "dataset_bytes_unchanged": original == lab.dataset_path(store, baseline.dataset_id).read_bytes()},
        "status": "passed",
    }


def example_report(store: Path | None = None) -> dict:
    if store is not None:
        return _report(Path(store))
    with TemporaryDirectory(prefix="chapter7-example-") as temporary:
        return _report(Path(temporary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path)
    args = parser.parse_args()
    print(json.dumps(example_report(args.store), indent=2, sort_keys=True))
