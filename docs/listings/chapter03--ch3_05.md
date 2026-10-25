# Select eligible versions in SQLite

Generated view; the canonical source remains authoritative.

Listing ID: `ch3_05`. Chapter: 3. Language: sql.

Canonical source: [chapter03/printed_snippets.json](../../chapter03/printed_snippets.json).

Run from the repository root: `.venv/bin/python -B verify_all.py --chapter 03`. The root command checks the lesson and its listing expectations in clean copies.

```sql
WITH eligible AS (
    SELECT * FROM revisions WHERE available_at <= :known_at
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY event_id ORDER BY revision DESC
    ) AS position
    FROM eligible
), selected AS (
    SELECT * FROM ranked WHERE position = 1
)
SELECT CASE WHEN :history_known = 0 THEN NULL
            ELSE COALESCE(SUM(amount), 0) END AS spend
FROM selected
WHERE customer_id = :customer_id
  AND event_time >= :window_start
  AND event_time < :window_end
  AND op = 'upsert'
  AND :history_known = 1;
```

Expected stdout:

```text
50
```
