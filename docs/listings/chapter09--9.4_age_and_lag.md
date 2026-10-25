# Compare publication age with policy publication lag

Generated view; the canonical source remains authoritative.

Listing ID: `9.4_age_and_lag`. Chapter: 9. Language: python.

Canonical source: [chapter09/printed_snippets.json](../../chapter09/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 09`. The root command checks the lesson and its listing expectations in clean copies.

```python
from operations_lab import base_report
rows = base_report()["publication_timing"]
print("request age lag")
for row in rows:
    print(row["request_id"], row["publication_age"],
          row["publication_lag"])
print("R5: old publication, zero policy lag")
```

Expected stdout:

```text
request age lag
R0 None None
R1 2 0
R2 6 5
R3 8 7
R4 3 0
R5 13 0
R5: old publication, zero policy lag
```
