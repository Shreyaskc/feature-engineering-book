# Python values and explicit absence

Generated readable view of the unchanged book refresher.

ID: `refresher_python_values`. Source: reader draft version 2, paragraph 2027, Reading the lab code / Python values and explicit absence.

Canonical source: [book_refresher_examples.json](book_refresher_examples.json). Run both examples from the repository root with `.venv/bin/python -B verify_all.py --prerequisites-only`.

```python
rows = [{"value": 0}, {"value": None}, {"value": 50}]
print([row["value"] is None for row in rows])
print(rows[0]["value"] == 0)
```

Expected stdout:

```text
[False, True, False]
True
```
