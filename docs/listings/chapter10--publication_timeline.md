# Inspect full publication snapshots

Generated view; the canonical source remains authoritative.

Listing ID: `publication_timeline`. Chapter: 10. Language: python.

Canonical source: [chapter10/printed_snippets.json](../../chapter10/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 10`. The root command checks the lesson and its listing expectations in clean copies.

```python
from capstone_lab import load_case, publications
for row in publications(load_case()):
    print(row.revision, row.published_at, row.value)
```

Expected stdout:

```text
1 600 50
2 605 45
3 607 85
```
