"""Independent, reproducible generated checks for the Chapter 7 lab.

Run ``python3 randomized_checks.py`` for a deterministic JSON report. These
bounded checks provide evidence for the stated invariants, not a proof for
all inputs. The reference calculation groups raw input rows and explicitly
takes the maximum eligible revision; it never calls the lab's selector or
materializer to produce an expected value.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
from typing import Iterable

import backfill_lab as lab
from foundations_lab import Revision


DEFAULT_SEED = 7012026
DEFAULT_CASES = 48
PERMUTATIONS_PER_CASE = 2
WINDOWS = (1, 5, 15, 30, 60, 90)


def reference_records(history: Iterable[Revision],
                      decisions: Iterable[lab.Decision],
                      definition: lab.Definition) -> list[dict]:
    """Calculate semantic records from raw rows using an independent oracle.

    Inputs are valid upsert-only Chapter 7 histories. In particular, event
    customer/time are immutable and revision availability never decreases.
    Input order is deliberately not normalized by production code here.
    """
    groups: dict[str, list[Revision]] = {}
    for row in history:
        groups.setdefault(row.event_id, []).append(row)
    result = []
    for decision in sorted(decisions, key=lambda item: item.decision_id):
        cutoff = (decision.decision_at if definition.mode == "historical"
                  else definition.corrected_cutoff)
        start = decision.decision_at - definition.window_minutes
        winners = []
        for event_id in sorted(groups):
            eligible = [row for row in groups[event_id]
                        if row.available_at <= cutoff]
            if not eligible:
                continue
            winner = max(eligible, key=lambda row: row.revision)
            if (winner.customer_id == decision.customer_id
                    and start <= winner.event_time < decision.decision_at):
                winners.append(winner)
        result.append({
            "decision_id": decision.decision_id,
            "customer_id": decision.customer_id,
            "decision_at": decision.decision_at,
            "window_start": start,
            "window_end": decision.decision_at,
            "known_at": cutoff,
            "value": sum(row.amount for row in winners),
            "contributors": [[row.event_id, row.revision] for row in winners],
        })
    return result


@dataclass(frozen=True)
class GeneratedCase:
    history: tuple[Revision, ...]
    decisions: tuple[lab.Decision, ...]
    coverage: tuple[lab.Coverage, ...]
    definition: lab.Definition

    def spec(self) -> lab.RunSpec:
        # Capture current module hashes and the exact runtime at execution.
        return lab.make_spec(lab.SourceSnapshot(self.history),
                             decisions=self.decisions, coverage=self.coverage,
                             definition=self.definition)


def generated_cases(count: int = DEFAULT_CASES,
                    seed: int = DEFAULT_SEED) -> tuple[GeneratedCase, ...]:
    """Generate valid histories, boundary rows, corrections and empty sources.

    Every case has a covered customer with no rows. Every nonempty history
    has rows just before/at the lower bound and just before/at/after the upper
    bound, a late arrival, corrections at/after the cutoff, equal availability
    timestamps, revision gaps, and an unrelated customer. Random extra events
    vary cardinality, amounts, arrival delay and revision count.
    """
    if type(count) is not int or count < 1:
        raise ValueError("count must be a positive integer")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    rng = random.Random(seed)
    cases = []
    for index in range(count):
        window = WINDOWS[index % len(WINDOWS)]
        anchor = rng.randint(200, 600)
        decisions = [lab.Decision("D00", "C0", anchor),
                     lab.Decision("D01", "C0", anchor + 5),
                     lab.Decision("D02", "C1", anchor + 2),
                     lab.Decision("D03", "EMPTY", anchor)]
        for extra in range(rng.randint(0, 3)):
            decisions.append(lab.Decision(f"D{extra + 4:02d}",
                                          rng.choice(("C0", "C1")),
                                          anchor + rng.randint(0, 5)))
        mode = "historical" if (index // len(WINDOWS)) % 2 == 0 else "corrected"
        corrected_cutoff = anchor + 5 + rng.choice((0, 1, 17, 40))
        definition = lab.Definition(window, mode,
                                    corrected_cutoff if mode == "corrected" else None)
        cutoff = anchor if mode == "historical" else corrected_cutoff
        coverage = [lab.Coverage(customer, 0, anchor + 6,
                                max(anchor + 5, cutoff))
                    for customer in ("C0", "C1", "UNRELATED", "EMPTY")]
        rows = []
        if index % 17 != 0:
            for name, event_time in (("before_lower", anchor - window - 1),
                                     ("at_lower", anchor - window),
                                     ("before_upper", anchor - 1),
                                     ("at_upper", anchor),
                                     ("after_upper", anchor + 1)):
                rows.append(Revision(name, 1, "C0", event_time,
                                     event_time, rng.randint(1, 50)))
            rows.extend((
                Revision("late", 1, "C0", anchor - 1, anchor + 1, 23),
                Revision("correction", 2, "C0", anchor - 1, anchor - 1, 19),
                Revision("correction", 5, "C0", anchor - 1, cutoff, 7),
                Revision("correction", 9, "C0", anchor - 1, cutoff + 1, 31),
                Revision("same_availability", 1, "C0", anchor - 1, cutoff, 4),
                Revision("same_availability", 4, "C0", anchor - 1, cutoff, 15),
                Revision("same_availability", 10, "C0", anchor - 1, cutoff, 2),
                Revision("zero", 1, "C0", anchor - 1, anchor - 1, 0),
                Revision("other_customer", 1, "UNRELATED", anchor - 1,
                         anchor - 1, 900001),
            ))
            for event in range(rng.randint(0, 16)):
                customer = rng.choice(("C0", "C1", "UNRELATED"))
                event_time = rng.randint(anchor - window - 3, anchor + 8)
                available = event_time + rng.randint(0, window + 15)
                revision = 0
                for _ in range(rng.randint(1, 4)):
                    revision += rng.randint(1, 4)
                    available += rng.randint(0, 10)
                    rows.append(Revision(f"random_{event:02d}", revision,
                                         customer, event_time, available,
                                         rng.randint(0, 200)))
        rng.shuffle(rows)
        rng.shuffle(decisions)
        rng.shuffle(coverage)
        cases.append(GeneratedCase(tuple(rows), tuple(decisions),
                                   tuple(coverage), definition))
    return tuple(cases)


def _require(condition: bool, message: str) -> None:
    # Keep checks active under python -O as well as ordinary Python.
    if not condition:
        raise AssertionError(message)


def _compare(spec: lab.RunSpec, expected: list[dict], context: str) -> None:
    actual = [row.to_dict() for row in lab.materialize(spec)]
    semantics = [{key: row[key] for key in wanted}
                 for row, wanted in zip(actual, expected)]
    _require(len(actual) == len(expected) and semantics == expected,
             f"{context}: records disagree with independent oracle")
    _require(lab.values(spec) == [row["value"] for row in expected],
             f"{context}: values disagree with independent oracle")
    _require(all(row["source_sha256"] == spec.source.sha256
                 and row["spec_sha256"] == spec.sha256 for row in actual),
             f"{context}: record provenance differs from fixed run specification")


def _check_builds(spec: lab.RunSpec, expected: list[dict], index: int,
                  store: Path) -> None:
    """Publish equivalent whole and paused builds in independent stores."""
    whole_store = store / "whole"
    resumed_store = store / "resumed"
    count = len(spec.decisions)
    chunk_size = 1 + index % (count + 1)  # Also exercises a chunk larger than N.
    pause_chunks = index % 3  # Includes an initialized, zero-progress attempt.
    whole = lab.stage_build(whole_store, "whole", spec, chunk_size=count)
    _require(whole.complete and whole.next_index == count,
             f"case {index}: whole build incomplete")
    dataset = lab.publish_dataset(whole_store, "whole", spec, chunk_size=count)
    paused = lab.stage_build(resumed_store, "resumed", spec,
                             chunk_size=chunk_size, stop_after_chunks=pause_chunks)
    wanted_index = min(count, chunk_size * pause_chunks)
    _require(paused.next_index == wanted_index
             and paused.complete == (wanted_index == count),
             f"case {index}: pause did not stop at requested chunk boundary")
    resumed = lab.stage_build(resumed_store, "resumed", spec, chunk_size=chunk_size)
    _require(resumed.complete and resumed.next_index == count,
             f"case {index}: resumed build incomplete")
    checkpoint = resumed_store / "staging" / "resumed" / "checkpoint.json"
    before_replay = checkpoint.read_bytes()
    replayed = lab.stage_build(resumed_store, "resumed", spec, chunk_size=chunk_size)
    _require(replayed == resumed and checkpoint.read_bytes() == before_replay,
             f"case {index}: replay changed complete checkpoint")
    rebuilt = lab.publish_dataset(resumed_store, "resumed", spec,
                                   chunk_size=chunk_size)
    whole_bytes = lab.dataset_path(whole_store, dataset.dataset_id).read_bytes()
    resumed_bytes = lab.dataset_path(resumed_store, rebuilt.dataset_id).read_bytes()
    _require(whole_bytes == resumed_bytes,
             f"case {index}: published bytes depend on chunking/resume")
    _require(dataset.dataset_id == rebuilt.dataset_id == spec.dataset_id,
             f"case {index}: dataset identity changed across build paths")
    _require([row.value for row in rebuilt.records] == [row["value"] for row in expected],
             f"case {index}: published values disagree with oracle")


def run_checks(count: int = DEFAULT_CASES, seed: int = DEFAULT_SEED) -> dict:
    """Return a stable JSON-compatible summary; raise at the first mismatch."""
    cases = generated_cases(count, seed)
    rng = random.Random(seed + 1)
    fixture_expected = {
        "baseline": [50, 95, 0],
        "extended_historical": [50, 95, 0],
        "corrected": [102, 112, 0],
        "new_definition": [30, 35, 0],
    }
    for name, spec in lab.fixture_specs().items():
        expected = reference_records(spec.source.history, spec.decisions, spec.definition)
        _require([row["value"] for row in expected] == fixture_expected[name],
                 f"fixture {name}: independent result differs from stated vector")
        _compare(spec, expected, f"fixture {name}")
    decision_count = 0
    with TemporaryDirectory(prefix="chapter7-oracle-") as temporary:
        for index, case in enumerate(cases):
            expected = reference_records(case.history, case.decisions, case.definition)
            spec = case.spec()
            _compare(spec, expected, f"case {index}")
            decision_count += len(expected)
            for permutation in range(PERMUTATIONS_PER_CASE):
                rows, decisions, coverage = (list(case.history), list(case.decisions),
                                              list(case.coverage))
                rng.shuffle(rows)
                rng.shuffle(decisions)
                rng.shuffle(coverage)
                shuffled = GeneratedCase(tuple(rows), tuple(decisions), tuple(coverage),
                                          case.definition).spec()
                _compare(shuffled, expected, f"case {index}, permutation {permutation}")
                _require(shuffled.to_dict() == spec.to_dict()
                         and shuffled.dataset_id == spec.dataset_id,
                         f"case {index}: input ordering changed specification identity")
            _check_builds(spec, expected, index, Path(temporary) / str(index))
    return {
        "schema_version": 1,
        "seed": seed,
        "runtime": lab.local_runtime(),
        "generated_cases": count,
        "generated_decisions": decision_count,
        "historical_cases": sum(case.definition.mode == "historical" for case in cases),
        "corrected_cases": sum(case.definition.mode == "corrected" for case in cases),
        "fully_empty_sources": sum(not case.history for case in cases),
        "covered_empty_customer_cases": count,
        "window_minutes": sorted({case.definition.window_minutes for case in cases}),
        "permutation_checks": count * PERMUTATIONS_PER_CASE,
        "whole_vs_resumed_build_checks": count,
        "complete_attempt_replay_checks": count,
        "fixture_vectors": fixture_expected,
        "status": "passed",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=DEFAULT_CASES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    if args.cases < 1:
        parser.error("--cases must be a positive integer")
    print(json.dumps(run_checks(args.cases, args.seed), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
