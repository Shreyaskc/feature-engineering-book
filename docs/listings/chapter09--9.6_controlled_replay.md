# Compare the declared incident cohort

Generated view; the canonical source remains authoritative.

Listing ID: `9.6_controlled_replay`. Chapter: 9. Language: python.

Canonical source: [chapter09/printed_snippets.json](../../chapter09/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 09`. The root command checks the lesson and its listing expectations in clean copies.

```python
from operations_lab import build_change_packet, decide
packet = build_change_packet()
report = decide(packet)
for name in ("observation", "baseline_replay", "candidate_replay"):
    m = report[name]["metrics"]["full_model_parity"]
    print(name, f'{m["numerator"]}/{m["denominator"]}')
print("cohort:", list(packet.cohort))
```

Expected stdout:

```text
observation 0/4
baseline_replay 4/4
candidate_replay 0/4
cohort: [('C0', 621), ('C1', 622), ('C2', 623), ('C3', 624)]
```
