# Listing 1. The join demonstration, from the companion directory.
from chapter4 import join_demo
bad, good = join_demo()
assert len(bad) == 4
assert good == [('D1', 50), ('D2', 95)]

# Listing 2. Features remain fixed at each original decision.
from chapter4 import EVENTS, historical_sum
assert historical_sum(EVENTS, 'C1', 600) == 50
assert historical_sum(EVENTS, 'C1', 610) == 95

# Listing 3. A known early positive is still immature under our policy.
from chapter4 import DECISIONS, OUTCOMES, FINALIZED_AT, label_at
assert label_at(DECISIONS[3], OUTCOMES, FINALIZED_AT, 1200) is None
assert label_at(DECISIONS[3], OUTCOMES, FINALIZED_AT, 1320) == 1

# Listing 4. Build the rows before fitting a transformation.
from chapter4 import build_dataset, fit_center, transform
rows, excluded = build_dataset()
train = [r['spend'] for r in rows if r['split'] == 'train']
valid = [r['spend'] for r in rows if r['split'] == 'validation']
center = fit_center(train)
assert center == 55
assert transform(train, center) == [-5, 40, -35]
assert transform(valid, center) == [-45, -15]
assert fit_center(train + valid) == 43  # Wrong fit scope.
assert excluded == [('D4', 'label not mature at cutoff')]

# Listing 5. Missing values use the training mean.
from chapter4 import fit_center, transform
center = fit_center([50, None, 20])
assert center == 35
assert transform([None, 100], center) == [0, 65]

print('All five printed Python listings passed.')
