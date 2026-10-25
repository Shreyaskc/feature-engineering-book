"""Executable checks for the chapter's eight exercises, without external actions."""
from dataclasses import replace

from operations_lab import (base_report, build_change_packet, consume_snapshots,
                            decide, required_artifacts, simulate_recovery)
from parity_lab import canonical_json


def _retained(packet):
    required = required_artifacts(packet)
    return replace(packet, inventory=tuple(replace(a, content_id=required[a.artifact_id][1])
                                          for a in packet.inventory))


def answers() -> dict:
    base = base_report()
    packet = build_change_packet()
    partial_healthy = tuple(replace(r, raw_value=85, model_input=85) for r in packet.observed[1:])
    partial = decide(_retained(replace(packet, observed=partial_healthy)))
    claimed_bad_baseline = tuple(replace(r, raw_value=180, model_input=180) for r in packet.baseline_replay)
    bad_baseline = decide(_retained(replace(packet, baseline_replay=claimed_bad_baseline)))

    def expires(minute):
        inventory = tuple(replace(a, expires_at=minute) if a.artifact_id == "recovery_release" else a
                          for a in packet.inventory)
        return replace(packet, inventory=inventory)

    expired = decide(expires(625))
    later = expires(626)
    recovered = simulate_recovery(packet)
    return {
        "exercise_1": {name: base["metrics"][name] for name in ("missing", "fallback", "raw_parity", "model_parity")},
        "exercise_2": {"R5": base["publication_timing"][5], "R3": base["publication_timing"][3],
                       "R3_latest_publication_age": 1, "age_alone_establishes_staleness": False},
        "exercise_3": {"action": partial["action"], "model_parity": partial["observation"]["metrics"]["model_parity"],
                       "declared_requests": 4, "healthy_complete_cohort": False},
        "exercise_4": {"replacement": consume_snapshots(packet.trace.publications, "replace"),
                       "addition": consume_snapshots(packet.trace.publications, "add"),
                       "scope": "one fixed feature-cell counterexample; not production causal proof"},
        "exercise_5": {"action": bad_baseline["action"], "baseline_full_parity": bad_baseline["baseline_replay"]["metrics"]["full_model_parity"],
                       "candidate_control_equal_values": True, "baseline_reproduced": False},
        "exercise_6": {"contract": expired["contract"], "action": expired["action"],
                       "recovery_artifact": expired["artifact_status"]["recovery_release"]},
        "exercise_7": {"decision_at625": decide(later)["action"],
                       "recovery_at626": simulate_recovery(later)["outcome"]},
        "exercise_8": {"outcome": recovered["outcome"], "observations": 4, "distinct_feature_cells": 1,
                       "production_recovery_proved": False, "external_action": recovered["external_action"],
                       "required_real_checks": ["actual post-change request observations under the restored release",
                                                "intended store/cache and preprocessing path without unintended fallback"],
                       "availability_assumption": "authorized access to retained diagnostics and recovery artifact throughout recovery"},
    }


if __name__ == "__main__":
    print(canonical_json(answers()), end="")
