-- Canonical source versions validated by the unchanged foundation ledger.
CREATE TABLE revisions (
    event_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    customer_id TEXT NOT NULL,
    event_time INTEGER NOT NULL,
    available_at INTEGER NOT NULL,
    amount INTEGER,
    op TEXT NOT NULL,
    PRIMARY KEY (event_id, revision)
);
INSERT INTO revisions VALUES ('A', 1, 'C1', 550, 551, 20, 'upsert');
INSERT INTO revisions VALUES ('B', 1, 'C1', 575, 607, 40, 'upsert');
INSERT INTO revisions VALUES ('C', 1, 'C1', 585, 586, 30, 'upsert');
INSERT INTO revisions VALUES ('C', 2, 'C1', 585, 605, 25, 'upsert');
INSERT INTO revisions VALUES ('D', 1, 'C1', 602, 603, 10, 'upsert');
WITH eligible AS (
    SELECT * FROM revisions WHERE available_at <= 600
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY event_id ORDER BY revision DESC
    ) AS position
    FROM eligible
), selected AS (
    SELECT * FROM ranked WHERE position = 1
)
SELECT CASE WHEN 1 = 0 THEN NULL
            ELSE COALESCE(SUM(amount), 0) END AS spend
FROM selected
WHERE customer_id = 'C1'
  AND event_time >= 540
  AND event_time < 600
  AND op = 'upsert'
  AND 1 = 1;
