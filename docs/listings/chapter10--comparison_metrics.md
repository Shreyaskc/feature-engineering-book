# Keep the denominator visible

Generated view; the canonical source remains authoritative.

Listing ID: `comparison_metrics`. Chapter: 10. Language: python.

Canonical source: [chapter10/printed_snippets.json](../../chapter10/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 10`. The root command checks the lesson and its listing expectations in clean copies.

```python
from capstone_lab import compare, load_case
metrics = compare(load_case())["implementations"]
for mode, values in metrics.items():
    historical = values["historical"]["numeric_parity"]
    online = values["online"]["raw_policy_parity"]
    print(mode)
    for measure in (historical, online):
        print(measure["numerator"], measure["denominator"],
              measure["excluded"], measure["population"])
```

Expected stdout:

```text
snapshot_baseline
1 3 1 4
1 5 1 6
contract_pipeline
3 3 1 4
5 5 1 6
```
