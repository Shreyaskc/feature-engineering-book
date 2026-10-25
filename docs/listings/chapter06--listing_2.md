# Policy publication is a source calculation

Generated view; the canonical source remains authoritative.

Listing ID: `listing_2`. Chapter: 6. Language: python.

Canonical source: [chapter06/printed_examples.py](../../chapter06/printed_examples.py).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 06`. The root command checks the lesson and its listing expectations in clean copies.

```python
from parity_lab import build_fixture
trace, _ = build_fixture()
published = [(p.revision, p.source_cutoff, p.value)
             for p in trace.publications]
assert published == [(1, 600, 50), (2, 605, 45), (3, 607, 85)]
assert trace.source.reference(trace.key, 620).value == 100
assert trace.policy_at(620).value == 85
result = {"published": published, "late": trace.after_deadline_at(620)}
```
