"""Synthetic Chapter 3 and 4 lab. Standard library only; Python 3.12.
All times are integer minutes from one fictional epoch, in UTC.
This is a small reference calculation, not a production service.
"""
from dataclasses import dataclass, asdict
from statistics import mean
import json
import hashlib
import platform
import sqlite3
from pathlib import Path

@dataclass(frozen=True)
class Event:
    customer: str
    event: str
    version: int
    event_time: int
    available_at: int
    amount: int

@dataclass(frozen=True)
class Decision:
    decision_id: str
    customer: str
    decision_time: int
    history_complete: bool = True

@dataclass(frozen=True)
class Outcome:
    outcome_id: str
    decision_id: str
    occurred_at: int
    available_at: int

EVENTS = [
    Event('C1', 'A', 1, 550, 551, 20),
    Event('C1', 'B', 1, 575, 607, 40),
    Event('C1', 'C', 1, 585, 586, 30),
    Event('C1', 'C', 2, 585, 605, 25),
    Event('C1', 'D', 1, 602, 603, 10),
    Event('C1', 'A', 1, 550, 551, 20),
    Event('C2', 'G', 1, 880, 881, 20),
    Event('C1', 'H', 1, 1280, 1281, 10),
    Event('C4', 'J', 1, 1290, 1291, 40),
]
DECISIONS = [
    Decision('D1', 'C1', 600),
    Decision('D2', 'C1', 610),
    Decision('D3', 'C2', 900),
    Decision('D4', 'C3', 1190),
    Decision('D5', 'C1', 1300),
    Decision('D6', 'C4', 1310),
]
OUTCOMES = [
    Outcome('O1', 'D1', 680, 700),
    Outcome('O4', 'D4', 1195, 1196),
    Outcome('O5', 'D5', 1370, 1450),
]
# Certificates are available at these times and finalize the entire
# (decision_time, decision_time + 120] interval, with no retractions.
FINALIZED_AT = dict(D1=730, D2=740, D3=1030,
                    D4=1320, D5=1450, D6=1440)
FIT_TIME, EVAL_END, EXTRACT_TIME, HORIZON = 1200, 1400, 1500, 120


def unique_by(rows, key):
    """Deduplicate identical records; reject conflicting identities."""
    result = {}
    for row in rows:
        identity = key(row)
        if identity in result and result[identity] != row:
            raise ValueError(f'conflicting identity: {identity}')
        result[identity] = row
    return list(result.values())


def canonical_events(events):
    """Validate global event/version identities, including one-shot inputs.

    An event ID belongs to one customer and event time across all revisions,
    following the source identity contract introduced in Chapter 2.
    """
    events = tuple(events)
    for e in events:
        if not e.customer or not e.event:
            raise ValueError('empty event identity')
        if any(type(v) is not int for v in
               (e.version, e.event_time, e.available_at, e.amount)):
            raise ValueError('event numeric fields must be integers')
        if e.version < 1 or e.amount < 0 or e.available_at < e.event_time:
            raise ValueError('invalid event fields')
    rows = unique_by(events, lambda e: (e.event, e.version))
    identities = {}
    for e in rows:
        identity = (e.customer, e.event_time)
        if e.event in identities and identities[e.event] != identity:
            raise ValueError('event customer and time are immutable')
        identities[e.event] = identity
    return rows


def historical_sum(events, customer, decision, width=60):
    if type(width) is not int or width <= 0:
        raise ValueError('width must be a positive integer')
    latest = {}
    for e in canonical_events(events):
        if e.customer != customer or e.available_at > decision:
            continue
        old = latest.get(e.event)
        if old is None or e.version > old.version:
            latest[e.event] = e
    return sum(e.amount for e in latest.values()
               if decision - width <= e.event_time < decision)


def label_at(d, outcomes, finalized_at, cutoff, horizon=HORIZON):
    """None means not mature; 0 and 1 are finalized binary labels."""
    end = d.decision_time + horizon
    final = finalized_at.get(d.decision_id)
    if final is not None and final < end:
        raise ValueError('finalization precedes horizon end')
    eligible = [o for o in outcomes
                if o.decision_id == d.decision_id
                and d.decision_time < o.occurred_at <= end]
    if final is not None and any(o.available_at > final for o in eligible):
        raise ValueError('outcome contradicts finalization certificate')
    if final is None or final > cutoff:
        return None
    return int(any(o.available_at <= cutoff for o in eligible))


def build_dataset(decisions=DECISIONS, events=EVENTS,
                  outcomes=OUTCOMES, finalized_at=FINALIZED_AT,
                  fit_time=FIT_TIME, eval_end=EVAL_END,
                  extract_time=EXTRACT_TIME):
    """Build one row per decision from finite list or one-shot iterable inputs."""
    if not fit_time < eval_end <= extract_time:
        raise ValueError('require fit_time < eval_end <= extract_time')
    decisions = tuple(decisions)
    ids = [d.decision_id for d in decisions]
    if len(ids) != len(set(ids)) or any(not i for i in ids):
        raise ValueError('decisions must have unique nonempty IDs')
    events = canonical_events(events)
    outcomes = unique_by(outcomes, lambda o: o.outcome_id)
    for o in outcomes:
        if o.decision_id not in ids or o.available_at < o.occurred_at:
            raise ValueError('invalid outcome identity or times')
    rows, excluded = [], []
    for d in decisions:
        if d.decision_time >= eval_end:
            excluded.append((d.decision_id, 'outside evaluation interval'))
            continue
        split = 'train' if d.decision_time < fit_time else 'validation'
        cutoff = fit_time if split == 'train' else extract_time
        y = label_at(d, outcomes, finalized_at, cutoff)
        if y is None:
            excluded.append((d.decision_id, 'label not mature at cutoff'))
            continue
        x = (historical_sum(events, d.customer, d.decision_time)
             if d.history_complete else None)
        rows.append(dict(decision_id=d.decision_id, customer=d.customer,
                         decision_time=d.decision_time, spend=x, label=y,
                         label_cutoff=cutoff, split=split))
    return rows, excluded


def fit_center(train_values):
    known = [x for x in train_values if x is not None]
    if not known:
        raise ValueError('cannot fit without observed training values')
    return mean(known)


def transform(values, center):
    # Fill missing values with training mean, then subtract that mean.
    return [(center if x is None else x) - center for x in values]


JOIN_BAD = '''SELECT d.decision_id, f.spend
FROM decisions d JOIN features f ON d.customer = f.customer
ORDER BY d.decision_id, f.spend'''
JOIN_GOOD = '''SELECT d.decision_id, f.spend
FROM decisions d LEFT JOIN features f
  ON d.decision_id = f.decision_id
ORDER BY d.decision_id'''


def join_demo():
    con = sqlite3.connect(':memory:')
    con.executescript('''CREATE TABLE decisions (
      decision_id TEXT PRIMARY KEY NOT NULL, customer TEXT NOT NULL);
    CREATE TABLE features (decision_id TEXT PRIMARY KEY NOT NULL,
      customer TEXT NOT NULL, spend INTEGER);
    INSERT INTO decisions VALUES ('D1','C1'),('D2','C1');
    INSERT INTO features VALUES ('D1','C1',50),('D2','C1',95);''')
    bad = con.execute(JOIN_BAD).fetchall()
    good = con.execute(JOIN_GOOD).fetchall()
    con.close()
    return bad, good


def main():
    rows, excluded = build_dataset()
    train = [r['spend'] for r in rows if r['split'] == 'train']
    valid = [r['spend'] for r in rows if r['split'] == 'validation']
    center = fit_center(train)
    manifest = dict(
        dataset_version='synthetic-ch04-v1', grain='one decision',
        primary_key='decision_id', feature='known_spend_60m_v1',
        feature_window='[decision_time-60, decision_time)',
        feature_availability='available_at <= decision_time',
        label='any confirmed adverse outcome for this decision',
        label_window='(decision_time, decision_time+120]',
        label_finalization='immutable source certificate; no retractions',
        fit_time=FIT_TIME, evaluation_interval=[FIT_TIME, EVAL_END],
        evaluation_upper_exclusive=True, extract_time=EXTRACT_TIME,
        train_ids=[r['decision_id'] for r in rows if r['split']=='train'],
        validation_ids=[r['decision_id'] for r in rows
                        if r['split']=='validation'],
        excluded=excluded, preprocessing_mean=center,
        source_fixture='chapter4.py constants; synthetic only',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        event_identity=['event', 'version'],
        revision_policy='highest eligible version; fixed customer and event time',
        entity_policy='future mixture of returning and new customers',
        preprocessing_policy='fit on training values only; freeze for validation',
        python=platform.python_version(), sqlite=sqlite3.sqlite_version,
        history_complete='assumed true for fixture at each decision',
        scope='toy reference, no performance or deployment claims')
    print(json.dumps(dict(rows=rows, excluded=excluded, train_mean=center,
                         centered_train=transform(train, center),
                         centered_validation=transform(valid, center),
                         join_row_counts=list(map(len, join_demo()))), indent=2))
    Path('dataset_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    Path('dataset_rows.json').write_text(json.dumps(rows, indent=2)+'\n')

if __name__ == '__main__':
    main()
