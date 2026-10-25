# Reproduce the full-snapshot arithmetic counterexample

Generated view; the canonical source remains authoritative.

Listing ID: `9.5_snapshot_hypothesis`. Chapter: 9. Language: python.

Canonical source: [chapter09/printed_snippets.json](../../chapter09/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 09`. The root command checks the lesson and its listing expectations in clean copies.

```python
from operations_lab import build_change_packet, consume_snapshots
packet = build_change_packet()
snapshots = packet.trace.publications
print("snapshots:", [p.value for p in snapshots])
print("replacement:", consume_snapshots(snapshots, "replace"))
print("addition:", consume_snapshots(snapshots, "add"))
```

Expected stdout:

```text
snapshots: [50, 45, 85]
replacement: 85
addition: 180
```
