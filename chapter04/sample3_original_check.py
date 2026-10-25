"""Verbatim function from the original Chapter 3 sample, with fixtures."""
from dataclasses import asdict
from chapter4 import EVENTS

def historical_sum(rows, customer, decision, width=60):
    latest = {}
    for row in rows:
        if row['customer'] != customer:
            continue
        if row['available_at'] > decision:
            continue
        key = row['event']
        previous = latest.get(key)
        if previous is None or row['version'] > previous['version']:
            latest[key] = row
    return sum(
        row['amount'] for row in latest.values()
        if decision - width <= row['event_time'] < decision
    )

rows = [asdict(e) for e in EVENTS[:6]]
assert historical_sum(rows, 'C1', 600) == 50
assert historical_sum(rows, 'C1', 610) == 95
assert historical_sum(rows*2, 'C1', 600) == 50
assert historical_sum(list(reversed(rows)), 'C1', 600) == 50
extra = [dict(customer='C1', event='E', version=1,
              event_time=540, available_at=541, amount=5),
         dict(customer='C1', event='F', version=1,
              event_time=600, available_at=600, amount=7)]
assert historical_sum(rows+extra, 'C1', 600) == 55
print('Original Chapter 3 function passed five direct assertions.')
