# Listing 1: keep the fixed event window separate from the knowledge cutoff.
from chapter5 import reference
assert sum(e.amount for e in reference(cutoff=600).values()) == 50
assert sum(e.amount for e in reference(cutoff=610).values()) == 85
moving = reference(start=550, end=610, cutoff=610)
assert sum(e.amount for e in moving.values()) == 95

# Listing 2: execute the two policies.
from chapter5 import simulate, IMMEDIATE, DELAYED
a = simulate(IMMEDIATE)['outputs']
b = simulate(DELAYED)['outputs']
expected = [(600, 50), (605, 45), (607, 85)]
assert [(o.emitted_at, o.total) for o in a] == expected
assert [(o.emitted_at, o.total) for o in b] == [(610, 85)]

# Listing 3: a diagnostic watermark does not control this fixed deadline.
from chapter5 import simulate, IMMEDIATE
with_trace = simulate(IMMEDIATE)
without_trace = simulate(IMMEDIATE, watermarks=())
assert with_trace['outputs'] == without_trace['outputs']
assert any(d['behind_watermark'] for d in with_trace['diagnostics'])
assert not any(d['behind_watermark'] for d in without_trace['diagnostics'])

# Listing 4: an arrival after closure stays out of published history.
from chapter5 import BASE, LATE_E, simulate, IMMEDIATE, reference
late_run = simulate(IMMEDIATE, BASE + (LATE_E,))
assert late_run['outputs'][-1].total == 85
assert [d.delivery_id for d in late_run['reconciliation']] == ['e1']
assert sum(e.amount for e in reference(BASE + (LATE_E,)).values()) == 100
old = reference(BASE + (LATE_E,), cutoff=600)
assert sum(e.amount for e in old.values()) == 50

# Listing 5: apply replacements idempotently.
from chapter5 import simulate, IMMEDIATE, latest_outputs
outputs = simulate(IMMEDIATE)['outputs']
assert sum(o.total for o in outputs) == 180  # Wrong consumer behavior.
latest = latest_outputs(list(reversed(outputs)) + outputs)
assert list(latest.values())[0].total == 85

# Listing 6: measure coverage separately from aggregate difference.
from chapter5 import BASE, LATE_E, reference, simulate, IMMEDIATE, score
audit = reference(BASE + (LATE_E,))
metrics = [score(o, audit) for o in simulate(IMMEDIATE)['outputs']]
assert [m['identities_seen'] for m in metrics] == [2, 2, 3]
assert [m['matching_latest_versions'] for m in metrics] == [1, 2, 3]
errors = [m['absolute_aggregate_difference'] for m in metrics]
assert errors == [50, 55, 15]

print('All six printed Python listings passed.')
