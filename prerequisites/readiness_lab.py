"""Small, offline reading exercises before Chapter 1. No output files are written."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def fixture():
    """A fixture is a small, repeatable input with an independently stated answer."""
    return json.loads((ROOT/'fixtures/readiness.json').read_text())


def book_examples():
    """Run the two preserved book examples in fresh Python processes."""
    results = {}
    for item in json.loads((ROOT/'book_refresher_examples.json').read_text()):
        if sha256(item['code'].encode()).hexdigest() != item['code_sha256']:
            raise AssertionError('Book refresher code identity differs')
        result = subprocess.run([sys.executable,'-B','-c',item['code']],
                                cwd=ROOT,capture_output=True,text=True,timeout=10)
        if result.returncode != 0 or result.stdout != item['expected_stdout']:
            raise AssertionError(f'Book refresher output differs: {item["id"]}')
        results[item['id']] = {'stdout':result.stdout,'returncode':result.returncode}
    return results


def absence_example():
    values = [0, None, False, 50]
    # Truthiness collapses several states; an identity check asks about absence.
    return {'is_missing':[value is None for value in values],
            'truthiness':[bool(value) for value in values],
            'types':[type(value).__name__ for value in values],
            'zero_equals_false':0 == False}


@dataclass(frozen=True)
class Event:
    event_id: str
    event_time: int
    available_at: int
    amount: int


def record_example():
    original = Event('A',550,551,20)
    try:
        original.amount = 25
    except FrozenInstanceError:
        rejected = True
    else:
        raise AssertionError('Frozen record unexpectedly changed')
    corrected = replace(original,amount=25)
    return {'assignment_rejected':rejected,'original_amount':original.amount,
            'replacement_amount':corrected.amount,'original_unchanged':original.amount == 20}


def eligible(event, start, end, cutoff):
    return start <= event.event_time < end and event.available_at <= cutoff


def total(events, start=540, end=600, cutoff=600):
    return sum(event.amount for event in events if eligible(event,start,end,cutoff))


def boundary_example(data):
    events = [Event(*row) for row in data['base_events']]
    return {'base':total(events),
            'lower_boundary_included':total(events+[Event('K',540,599,5)]),
            'upper_boundary_excluded':total(events+[Event('U',600,600,7)]),
            'available_exactly_cutoff':total(events+[Event('K',540,600,5)]),
            'available_after_cutoff':total(events+[Event('K',540,601,5)])}


def sql_example(data):
    """Two small previews; the unchanged SQL refresher above has one version/event."""
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE decisions(id TEXT, customer TEXT, time INT)')
        db.execute('CREATE TABLE features(decision_id TEXT, customer TEXT, value INT)')
        db.executemany('INSERT INTO decisions VALUES (?,?,?)',data['decisions'])
        db.executemany('INSERT INTO features VALUES (?,?,?)',data['features'])
        wrong = db.execute('SELECT COUNT(*) FROM decisions d JOIN features f ON d.customer=f.customer').fetchone()[0]
        correct = db.execute('SELECT d.id,f.value FROM decisions d JOIN features f ON d.id=f.decision_id ORDER BY d.id').fetchall()
        db.execute('CREATE TABLE revisions(event_id TEXT, revision INT, event_time INT, available_at INT, amount INT)')
        db.executemany('INSERT INTO revisions VALUES (?,?,?,?,?)',data['revisions'])
        # Eligibility must be decided before ranking. Otherwise C2 hides C1 at 600.
        good_query = '''WITH eligible AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY revision DESC) AS position
            FROM revisions WHERE available_at <= ?)
            SELECT SUM(amount) FROM eligible WHERE position=1 AND event_time>=540 AND event_time<600'''
        bad_query = '''WITH ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY revision DESC) AS position
            FROM revisions)
            SELECT SUM(amount) FROM ranked WHERE position=1 AND available_at<=600
            AND event_time>=540 AND event_time<600'''
        return {'wrong_customer_join_rows':wrong,'decision_join_rows':len(correct),
                'decision_values':[list(row) for row in correct],
                'latest_eligible_fixed_at_600':db.execute(good_query,(600,)).fetchone()[0],
                'wrong_rank_before_availability':db.execute(bad_query).fetchone()[0],
                'latest_eligible_fixed_at_610':db.execute(good_query,(610,)).fetchone()[0]}


def report():
    data = fixture()
    # Assert one independently calculated fixture answer before adding variations.
    assert total([Event(*row) for row in data['base_events']]) == 50
    return {'book_refresher_examples':book_examples(),'absence':absence_example(),
            'immutable_record':record_example(),'boundaries':boundary_example(data),
            'fixture_assertion':'base total 20 + 30 = 50','sql_previews':sql_example(data)}


if __name__ == '__main__':
    if sys.flags.optimize:
        raise SystemExit('Run without -O/-OO so fixture assertions execute')
    print(json.dumps(report(),indent=2,sort_keys=True))
