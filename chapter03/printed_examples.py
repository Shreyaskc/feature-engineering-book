"""Execute exactly the nine embedded listings; never regenerate expectations."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path

from foundations_lab import load_fixture
from historical_lab import Query
from sqlite_lab import connect

ROOT = Path(__file__).resolve().parent


def run_examples() -> dict:
    data = json.loads((ROOT / "printed_snippets.json").read_text(encoding="utf-8"))
    items = data["snippets"]
    if [item["id"] for item in items] != [f"ch3_{n:02d}" for n in range(1, 10)]:
        raise AssertionError("listing identities must be ch3_01 through ch3_09")
    reports = []
    for item in items:
        output = StringIO()
        if item["language"] == "python":
            with redirect_stdout(output):
                exec(compile(item["code"], item["id"], "exec"), {})
        elif item["language"] == "sql":
            if item["code"] != (ROOT / "selected_spend.sql").read_text(encoding="utf-8"):
                raise AssertionError("printed SQL must equal the executable SQL file")
            raw = item["parameters"]
            query = Query(raw["customer_id"], raw["window_start"], raw["window_end"],
                          raw["known_at"], bool(raw["history_known"]))
            connection = connect(load_fixture(item["fixture"]), query)
            try:
                value = connection.execute(item["code"], raw).fetchone()[0]
                output.write(f"{value}\n")
            finally:
                connection.close()
        else:
            raise AssertionError("unknown listing language")
        actual = output.getvalue()
        if actual != item["expected_stdout"]:
            raise AssertionError(f"{item['id']}: expected {item['expected_stdout']!r}, got {actual!r}")
        reports.append({"id": item["id"], "stdout": actual, "status": "passed"})
    return {"snippets_executed": len(reports), "snippets": reports}


if __name__ == "__main__":
    print(json.dumps(run_examples(), indent=2, sort_keys=True))
