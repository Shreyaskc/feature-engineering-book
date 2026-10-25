"""Chapter 5: deterministic synthetic late-data policy simulation.
Standard library only. Integer minutes from a fictional UTC epoch.
A fixed processing-time deadline is NOT an event-time allowed-lateness API.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import platform

FEATURE_ID = 'known_spend_fixed_window_v1'
ENTITY, START, END, AUDIT = 'C1', 540, 600, 620

@dataclass(frozen=True)
class Event:
    event_id: str
    version: int
    event_time: int
    available_at: int
    amount: int
    entity: str = ENTITY

@dataclass(frozen=True)
class Delivery:
    delivery_id: str
    at: int
    event: Event

@dataclass(frozen=True)
class Policy:
    policy_id: str
    first_emit: int
    close_at: int

@dataclass(frozen=True)
class Output:
    feature_id: str
    policy_id: str
    entity: str
    window_start: int
    window_end: int
    revision: int
    emitted_at: int
    input_cutoff: int
    total: int
    # Each member is (event_id, source_revision, amount, available_at).
    contributions: tuple

    @property
    def key(self):
        return (self.feature_id, self.policy_id, self.entity,
                self.window_start, self.window_end)

A = Event('A', 1, 550, 551, 20)
BASE = (
    Delivery('a1', 551, A),
    Delivery('c1', 586, Event('C', 1, 585, 586, 30)),
    Delivery('a_retry', 590, A),
    Delivery('d1', 603, Event('D', 1, 602, 603, 10)),
    Delivery('c2', 605, Event('C', 2, 585, 605, 25)),
    Delivery('b1', 607, Event('B', 1, 575, 607, 40)),
)
LATE_E = Delivery('e1', 612, Event('E', 1, 595, 612, 15))
# (processing minute, event-time watermark); supplied control trace.
WATERMARKS = ((580, 560), (600, 600), (604, 604), (608, 608), (615, 615))
IMMEDIATE = Policy('immediate_then_correct', 600, 610)
DELAYED = Policy('wait_then_freeze', 610, 610)


def checked(deliveries):
    by_delivery, versions, event_times, first_delivery = {}, {}, {}, {}
    for d in deliveries:
        e = d.event
        if not d.delivery_id or not e.entity or not e.event_id:
            raise ValueError('identities must be nonempty')
        fields = (d.at, e.version, e.event_time, e.available_at, e.amount)
        if any(type(v) is not int for v in fields):
            raise ValueError('numeric fields must be integers')
        if e.version < 1 or e.amount < 0 or not e.event_time <= e.available_at <= d.at:
            raise ValueError('invalid source values or clock order')
        if d.delivery_id in by_delivery and by_delivery[d.delivery_id] != d:
            raise ValueError('conflicting delivery identity')
        by_delivery[d.delivery_id] = d
        version_key = (e.entity, e.event_id, e.version)
        if version_key in versions and versions[version_key] != e:
            raise ValueError('conflicting source version')
        versions[version_key] = e
        event_key = (e.entity, e.event_id)
        if event_key in event_times and event_times[event_key] != e.event_time:
            raise ValueError('event time corrections are outside this contract')
        event_times[event_key] = e.event_time
        first_delivery[version_key] = min(first_delivery.get(version_key, d.at), d.at)
    for key, e in versions.items():
        if first_delivery[key] != e.available_at:
            raise ValueError('trace must include first usable delivery of each version')
    return sorted(by_delivery.values(), key=lambda d: (d.at, d.delivery_id))


def selected(events, entity=ENTITY, start=START, end=END, cutoff=AUDIT):
    if not start < end:
        raise ValueError('window must have positive width')
    latest = {}
    for e in events:
        if e.entity != entity or e.available_at > cutoff:
            continue
        previous = latest.get(e.event_id)
        if previous is None or e.version > previous.version:
            latest[e.event_id] = e
    return {key: e for key, e in latest.items() if start <= e.event_time < end}


def reference(deliveries=BASE, *, start=START, end=END, cutoff=AUDIT):
    ds = checked(deliveries)
    return selected([d.event for d in ds], start=start, end=end, cutoff=cutoff)


def simulate(policy, deliveries=BASE, watermarks=WATERMARKS,
             *, start=START, end=END, history_complete=True):
    if history_complete is not True:
        raise ValueError('unknown initial history needs an explicit missingness policy')
    if any(type(v) is not int for v in (start, end, policy.first_emit, policy.close_at)):
        raise ValueError('policy times must be integers')
    if not start < end <= policy.first_emit <= policy.close_at:
        raise ValueError('require start < end <= first_emit <= close_at')
    ds = checked(deliveries)
    ws = sorted(watermarks)
    if any(type(t) is not int or type(w) is not int for t, w in ws):
        raise ValueError('watermark trace must contain integer pairs')
    if len({t for t, _ in ws}) != len(ws):
        raise ValueError('only one watermark update per processing minute')
    if any(ws[i][1] > ws[i+1][1] for i in range(len(ws)-1)):
        raise ValueError('watermarks must not move backward')
    state, seen, outputs, late, diagnostics = {}, set(), [], [], []
    watermark = None
    moments = sorted({d.at for d in ds} | {t for t, _ in ws}
                     | {policy.first_emit, policy.close_at})

    def emit(now):
        contributions = tuple((e.event_id, e.version, e.amount, e.available_at)
                              for e in sorted(state.values(), key=lambda e: e.event_id))
        outputs.append(Output(FEATURE_ID, policy.policy_id, ENTITY, start, end,
                              len(outputs)+1, now, now,
                              sum(e.amount for e in state.values()), contributions))

    for now in moments:
        changed = False
        # Phase 1: all arrivals, in delivery-ID order within this minute.
        for d in (x for x in ds if x.at == now):
            e = d.event
            key = (e.entity, e.event_id, e.version)
            duplicate = key in seen
            behind = watermark is not None and e.event_time < watermark
            diagnostics.append(dict(delivery=d.delivery_id, at=now,
                                    watermark_before=watermark,
                                    behind_watermark=behind, duplicate=duplicate))
            if duplicate:
                continue
            seen.add(key)
            if e.entity != ENTITY or not start <= e.event_time < end:
                continue
            if now > policy.close_at:
                late.append(d)
                continue
            previous = state.get(e.event_id)
            if previous is not None and previous.version >= e.version:
                continue
            state[e.event_id] = e
            # Record changed provenance even if the sum is unchanged.
            changed = True
        # Phase 2: supplied watermark control, not an acceptance rule here.
        for t, w in ws:
            if t == now:
                watermark = w
        # Phase 3: first-output and closure timers, after same-time arrivals.
        if now == policy.first_emit:
            emit(now)
        elif changed and outputs:
            # One full inclusive snapshot after ALL same-time arrivals.
            emit(now)
    return dict(outputs=outputs, reconciliation=late, diagnostics=diagnostics,
                closed_at=policy.close_at)


def latest_outputs(outputs):
    """Toy idempotent replacement sink; not a distributed exactly-once claim."""
    seen, latest = {}, {}
    for row in outputs:
        identity = row.key + (row.revision,)
        if identity in seen and seen[identity] != row:
            raise ValueError('conflicting output revision')
        seen[identity] = row
        old = latest.get(row.key)
        if old is None or row.revision > old.revision:
            latest[row.key] = row
    return latest


def score(output, audit_reference):
    ids = set(audit_reference)
    supplied = {c[0]: c for c in output.contributions}
    matched = sum(key in supplied and supplied[key][1] == e.version
                  for key, e in audit_reference.items())
    total = sum(e.amount for e in audit_reference.values())
    return dict(window_age=output.emitted_at-output.window_end,
                identities_seen=len(ids & supplied.keys()),
                matching_latest_versions=matched, audit_identities=len(ids),
                identity_coverage=(len(ids & supplied.keys())/len(ids) if ids else None),
                latest_version_agreement=(matched/len(ids) if ids else None),
                absolute_aggregate_difference=abs(output.total-total),
                audit_total=total)


def report(deliveries=BASE):
    result = {}
    audit = reference(deliveries, cutoff=AUDIT)
    for policy in (IMMEDIATE, DELAYED):
        replay = simulate(policy, deliveries)
        result[policy.policy_id] = dict(
            outputs=[asdict(o) for o in replay['outputs']],
            first=score(replay['outputs'][0],audit),
            last=score(replay['outputs'][-1],audit),
            correction_outputs=len(replay['outputs'])-1,
            reconciliation=[d.delivery_id for d in replay['reconciliation']],
            closed_at=replay['closed_at'])
    return result


def main():
    data = dict(base=report(), after_deadline=report(BASE+(LATE_E,)))
    print(json.dumps(data, indent=2))
    manifest = dict(
        chapter=5, fixture='synthetic only', feature_id=FEATURE_ID,
        entity=ENTITY, event_window=[START,END], upper_bound_exclusive=True,
        audit_cutoff=AUDIT, audit_is_eventual_truth=False,
        policies=[asdict(IMMEDIATE),asdict(DELAYED)],
        ordering='all arrivals by delivery ID; watermark; one snapshot; closure',
        deadline='processing-time <= close_at; not allowed lateness',
        output='immutable full replacements with monotonic per-key revisions',
        history='fixture assumes complete initial history; unknown is rejected',
        missing_metrics='zero audit denominator is null, not 100 percent',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        python=platform.python_version(), dependencies='standard library only',
        limitations=['no streaming engine execution','no concurrency or crash recovery',
                     'no source finality proof','no real latency or model benchmark'])
    Path('comparison.json').write_text(json.dumps(data,indent=2)+'\n')
    Path('policy_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__ == '__main__':
    main()
