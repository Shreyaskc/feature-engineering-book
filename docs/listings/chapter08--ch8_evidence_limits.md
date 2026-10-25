# ch8_evidence_limits

Generated view; the canonical source remains authoritative.

Listing ID: `ch8_evidence_limits`. Chapter: 8. Language: python.

Canonical source: [chapter08/printed_snippets.json](../../chapter08/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 08`. The root command checks the lesson and its listing expectations in clean copies.

```python
from fault_testing_lab import blind_spot_report, mutation_report

for name, result in mutation_report()["suite_results"].items():
    print(name, result["detected_count"], "/", 5)
probe = blind_spot_report()["constant_zero_probe_outside_mutant_registry"]
for name in ("shuffled_input", "replayed_input", "later_info_invariance",
             "hand_calculated", "unknown_coverage"):
    print(name, probe[name])
```

Expected stdout:

```text
weak 1 / 5
diagnostic 5 / 5
shuffled_input PASS
replayed_input PASS
later_info_invariance PASS
hand_calculated ASSERTION_FAILED
unknown_coverage ASSERTION_FAILED
```
