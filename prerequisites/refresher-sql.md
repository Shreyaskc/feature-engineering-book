# SQL filtering before aggregation

Generated readable view of the unchanged book refresher.

ID: `refresher_sql_filtering`. Source: reader draft version 2, paragraph 2032, Reading the lab code / SQL filtering before aggregation.

Canonical source: [book_refresher_examples.json](book_refresher_examples.json). Run both examples from the repository root with `.venv/bin/python -B verify_all.py --prerequisites-only`.

```python
import sqlite3
with sqlite3.connect(":memory:") as db:
    db.execute("CREATE TABLE e(t INT, a INT, amount INT)")
    db.executemany("INSERT INTO e VALUES (?, ?, ?)",
        [(550, 551, 20), (575, 607, 40), (585, 586, 30)])
    value = db.execute(
        "SELECT SUM(amount) FROM e "
        "WHERE a <= ? AND t >= ? AND t < ?",
        (600, 540, 600)).fetchone()[0]
    print(value)
```

Expected stdout:

```text
50
```
