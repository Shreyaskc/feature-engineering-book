"""Eight executable answers, with named failures rather than crash counting."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile

import capstone_lab as c
import foundations_lab as f


def expect_rejection(operation, error_type, expected_text: str) -> str:
    try:
        operation()
    except error_type as error:
        if expected_text not in str(error):
            raise AssertionError(f"wrong rejection reason: {error}") from error
        return str(error)
    raise AssertionError("expected rejection did not occur")


def exercise_report() -> dict:
    base, challenge = c.load_case(), c.load_case("challenge")
    report = {}
    report["1_chronology"] = {
        "base_rolling": [row["value"] for row in c.build_dataset(base)[:2]],
        "challenge_rolling": [row["value"] for row in c.build_dataset(challenge)[:2]],
        "challenge_baseline": [row["value"] for row in c.build_dataset(
            challenge, "snapshot_baseline")[:2]],
        "challenge_publications": [[row.published_at, row.value]
                                   for row in c.publications(challenge)]}
    late = {}
    for minute in (610, 611):
        deliveries = tuple(
            replace(row, delivered_at=minute,
                    record=replace(row.record, available_at=minute))
            if row.record.event_id == "E" else row
            for row in challenge.ledger.deliveries)
        case = replace(challenge, ledger=f.Ledger(deliveries))
        audit = c.audit_report(case)
        late[str(minute)] = {"closed": audit["closed_policy_value"],
                             "audit": audit["audit_source_value"],
                             "D2": c.build_dataset(case)[1]["value"]}
    report["2_deadline"] = late
    report["3_full_snapshots"] = {
        mode: c.consume_snapshots(c.publications(challenge), mode)["value"]
        for mode in c.IMPLEMENTATIONS}
    replay = f.ingest(base.ledger, tuple(reversed(base.ledger.deliveries)) * 2)
    missing = c.source_payload(base.ledger)
    del missing["deliveries"][0]["record"]["available_at"]
    first = base.ledger.deliveries[0]
    conflicting = replace(first, delivery_id="conflict",
                          record=replace(first.record, amount=999))
    report["4_replay_and_schema"] = {
        "replay_same": c.run_case(base) == c.run_case(replace(base, ledger=replay)),
        "missing_field_rejection": expect_rejection(
            lambda: f.ledger_from_dict(missing), f.ContractError, "record must have exactly"),
        "conflict_rejection": expect_rejection(
            lambda: f.ingest(base.ledger, [conflicting]), f.ContractError,
            "source revision reused with conflicting payload"),
        "delivery_identity_rejection": expect_rejection(
            lambda: f.ingest(base.ledger, [replace(conflicting,
                                                delivery_id=first.delivery_id)]),
            f.ContractError, "delivery_id reused with conflicting payload"),
        "deletion_rejection": expect_rejection(
            lambda: c.adapt_source(f.load_fixture("deletion_extension")),
            c.CapstoneError, "does not support deletion"),
        "restoration_rejection": expect_rejection(
            lambda: c.adapt_source(f.load_fixture("restoration_extension")),
            c.CapstoneError, "does not support restoration")}
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "run"
        c.persist_run(base, path)
        target = path / "improved_dataset.json"
        rows = json.loads(target.read_text(encoding="utf-8"))
        rows[0]["value"] = 51
        target.write_text(c.canonical(rows), encoding="utf-8")
        direct = expect_rejection(lambda: c.verify_artifacts(path),
                                  c.CapstoneError, "artifact content mismatch")
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifact_sha256"]["improved_dataset.json"] = c.digest(rows)
        manifest_path.write_text(c.canonical(manifest), encoding="utf-8")
        rehashed = expect_rejection(lambda: c.verify_artifacts(path),
                                    c.CapstoneError,
                                    "artifact digests disagree with recomputation")
    report["5_corruption"] = {"direct": direct, "rewritten_sibling_hash": rehashed}
    report["6_zero_and_unknown"] = [
        {name: row[name] for name in ("row_id", "value", "missing", "source_versions")}
        for row in c.build_dataset(base)[2:]]
    metrics = c.compare(base)["implementations"]
    report["7_denominators"] = {
        mode: {"historical": metrics[mode]["historical"]["numeric_parity"],
               "online": metrics[mode]["online"]["raw_policy_parity"],
               "missing": metrics[mode]["online"]["missing"],
               "fallback": metrics[mode]["online"]["fallback"]}
        for mode in c.IMPLEMENTATIONS}
    report["8_audit_explanation"] = {
        case.name: {**{field: c.audit_report(case)[field] for field in (
            "closed_policy_value", "audit_source_value",
            "after_deadline_source_versions", "difference", "explanation")},
            "Q5": c.online_lookups(case)[-1]}
        for case in (base, challenge)}
    return report


if __name__ == "__main__":
    print(c.canonical(exercise_report()), end="")
