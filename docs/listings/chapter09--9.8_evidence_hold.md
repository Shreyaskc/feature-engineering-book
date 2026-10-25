# Hold when recovery evidence expires

Generated view; the canonical source remains authoritative.

Listing ID: `9.8_evidence_hold`. Chapter: 9. Language: python.

Canonical source: [chapter09/printed_snippets.json](../../chapter09/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 09`. The root command checks the lesson and its listing expectations in clean copies.

```python
from dataclasses import replace
from operations_lab import build_change_packet, decide
packet = build_change_packet()
inventory = tuple(
    replace(a, expires_at=625) if a.artifact_id == "recovery_release"
    else a for a in packet.inventory)
report = decide(replace(packet, inventory=inventory))
print("contract:", report["contract"])
print("action:", report["action"])
print("blockers:", report["blockers"])
```

Expected stdout:

```text
contract: FAIL
action: HOLD
blockers: ['artifact:recovery_release:EXPIRED']
```
