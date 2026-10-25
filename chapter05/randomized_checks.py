"""Reproducible, standard-library property checks for the Chapter 5 simulator.

Default: seeds 0 through 499 inclusive, with both policies for every fixture.
Run: "$CODEX_PRIMARY_RUNTIME_PYTHON" randomized_checks.py
Optional: --start-seed 500 --seeds 500

These are bounded synthetic checks, not an engine integration test or proof.
The independent oracle below does not call selected() or reference(). Every
emitted snapshot, rather than only the terminal value, is checked against the
versions available by its inclusive input cutoff and the policy close time.
"""

import argparse
import random

from chapter5 import (
    AUDIT, DELAYED, END, ENTITY, FEATURE_ID, IMMEDIATE, START,
    Delivery, Event, latest_outputs, reference, score, simulate,
)


def fixture(seed):
    rng = random.Random(seed)
    deliveries = []
    for index in range(rng.randint(0, 12)):
        event_id = f"R{index}"
        entity = rng.choice((ENTITY, ENTITY, ENTITY, "C2"))
        event_time = rng.choice((539, 540, 550, 575, 585, 595, 599,
                                 600, 602, rng.randint(535, 610)))
        for version in range(1, rng.randint(1, 5) + 1):
            # Availability need not follow source-version order: a newer
            # version may become usable before an older version is delivered.
            available_at = rng.choice((max(event_time, 600),
                                       max(event_time, 610),
                                       max(event_time, 611),
                                       rng.randint(event_time, 640)))
            amount = rng.choice((0, 25, rng.randint(0, 100)))
            event = Event(event_id, version, event_time, available_at,
                          amount, entity)
            identity = f"{index:02d}_v{version}"
            delivery = Delivery(identity, available_at, event)
            deliveries.append(delivery)
            if rng.randrange(2):
                deliveries.append(Delivery(identity + "_retry",
                                           available_at + rng.randint(0, 30),
                                           event))
            if rng.randrange(4) == 0:
                # Repeated physical storage of the exact same delivery.
                deliveries.append(delivery)
    rng.shuffle(deliveries)
    return deliveries


def oracle(deliveries, cutoff):
    """Latest eligible versions, independent of simulator implementation."""
    latest = {}
    for delivery in deliveries:
        event = delivery.event
        if event.entity != ENTITY or event.available_at > cutoff:
            continue
        old = latest.get(event.event_id)
        if old is None or event.version > old.version:
            latest[event.event_id] = event
    return {key: event for key, event in latest.items()
            if START <= event.event_time < END}


def contributions(events):
    return tuple((event.event_id, event.version, event.amount,
                  event.available_at)
                 for event in sorted(events.values(), key=lambda e: e.event_id))


def oracle_sequence(deliveries, policy):
    """Enumerate complete expected publications, without calling the simulator.

    The trace contract includes a first usable delivery at available_at for
    every revision. Scan each integer minute, retaining every provenance change
    (even equal-valued changes), after coalescing all same-minute information.
    """
    output=[]
    for minute in range(policy.first_emit,policy.close_at+1):
        selected=oracle(deliveries,minute)
        detail=contributions(selected)
        if not output or detail != output[-1]['contributions']:
            output.append(dict(feature_id=FEATURE_ID,policy_id=policy.policy_id,
                               entity=ENTITY,window_start=START,window_end=END,
                               revision=len(output)+1,emitted_at=minute,input_cutoff=minute,
                               total=sum(event.amount for event in selected.values()),
                               contributions=detail))
    return output


def assert_sequence(outputs,expected,context):
    if len(outputs)!=len(expected):
        raise AssertionError(f'{context}, sequence.length: expected {len(expected)}, observed {len(outputs)}')
    for index,(row,wanted) in enumerate(zip(outputs,expected)):
        for field,value in wanted.items():
            actual=getattr(row,field)
            if type(actual) is not type(value) or actual!=value:
                raise AssertionError(f'{context}, sequence[{index}].{field}: expected {value!r}, observed {actual!r}')


def check(seed, policy):
    deliveries = fixture(seed)
    result = simulate(policy, deliveries)
    outputs = result["outputs"]
    context = f"seed={seed}, policy={policy.policy_id}"
    assert_sequence(outputs,oracle_sequence(deliveries,policy),context)
    assert outputs, context
    assert outputs[0].emitted_at == policy.first_emit, context
    assert result["closed_at"] == policy.close_at, context
    assert len({row.emitted_at for row in outputs}) == len(outputs), context
    audit = oracle(deliveries, AUDIT)
    assert reference(deliveries, cutoff=AUDIT) == audit, context

    for revision, row in enumerate(outputs, 1):
        detail = f"{context}, revision={revision}"
        assert row.revision == revision, detail
        assert row.emitted_at == row.input_cutoff, detail
        assert policy.first_emit <= row.emitted_at <= policy.close_at, detail
        # Explicitly bound the oracle by policy closure even though all
        # publication timestamps must already be at or before close_at.
        cutoff = min(row.input_cutoff, policy.close_at)
        expected = oracle(deliveries, cutoff)
        assert reference(deliveries, cutoff=cutoff) == expected, detail
        assert row.contributions == contributions(expected), detail
        assert row.total == sum(e.amount for e in expected.values()), detail
        metrics = score(row, audit)
        ids = set(audit)
        present = set(expected)
        matched = sum(key in expected and expected[key].version == event.version
                      for key, event in audit.items())
        assert metrics["window_age"] == row.emitted_at - END, detail
        assert metrics["identities_seen"] == len(ids & present), detail
        assert metrics["matching_latest_versions"] == matched, detail
        assert metrics["identity_coverage"] == (
            len(ids & present) / len(ids) if ids else None), detail
        assert metrics["latest_version_agreement"] == (
            matched / len(ids) if ids else None), detail
        assert metrics["absolute_aggregate_difference"] == abs(
            row.total - sum(e.amount for e in audit.values())), detail

    accepted = oracle(deliveries, policy.close_at)
    assert outputs[-1].contributions == contributions(accepted), context
    assert list(latest_outputs(outputs[::-1] + outputs + outputs).values()) == [
        outputs[-1]], context

    # Empty and deliberately aggressive watermark traces must not change
    # this processing-deadline policy's publications or reconciliation.
    for watermarks in ((), ((500, 1000),)):
        alternate = simulate(policy, deliveries, watermarks=watermarks)
        assert alternate["outputs"] == outputs, context
        assert alternate["reconciliation"] == result["reconciliation"], context

    # A post-deadline version can be audited but cannot alter publications.
    future = Delivery("late_probe", 612,
                      Event("late_probe", 1, 595, 612, 15))
    with_future = simulate(policy, deliveries + [future])
    assert with_future["outputs"] == outputs, context
    assert future in with_future["reconciliation"], context
    return len(outputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-seed", type=int, default=0)
    parser.add_argument("--seeds", type=int, default=500)
    args = parser.parse_args()
    if args.seeds <= 0:
        parser.error("--seeds must be positive")
    snapshots = 0
    for seed in range(args.start_seed, args.start_seed + args.seeds):
        for policy in (IMMEDIATE, DELAYED):
            snapshots += check(seed, policy)
    print(f"PASS: seeds {args.start_seed}..{args.start_seed + args.seeds - 1}; "
          f"{args.seeds} fixtures; {args.seeds * 2} policy cases; "
          f"{snapshots} emitted snapshots checked")
    print("Verified inclusive cutoff parity, terminal state, provenance, metrics, "
          "same-time coalescing, closure, replacement sink, and watermark "
          "independence on these bounded synthetic cases")


if __name__ == "__main__":
    main()
