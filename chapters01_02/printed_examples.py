"""Execute the exact standalone code snippets printed in Chapters 1–2."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path


def run_examples() -> dict:
    path = Path(__file__).parent / "printed_snippets.json"
    snippets = json.loads(path.read_text(encoding="utf-8"))
    results = []
    ids = set()
    for snippet in snippets:
        if snippet["id"] in ids:
            raise AssertionError("duplicate printed snippet ID")
        ids.add(snippet["id"])
        widths = [len(line) for line in snippet["code"].splitlines()]
        if max(widths, default=0) > 74:
            raise AssertionError(f"snippet exceeds 74 columns: {snippet['id']}")
        output = StringIO()
        with redirect_stdout(output):
            exec(compile(snippet["code"], snippet["id"], "exec"), {})
        actual = output.getvalue()
        if actual != snippet["expected_stdout"]:
            raise AssertionError(f"printed output drift: {snippet['id']}")
        results.append({"id": snippet["id"], "chapter": snippet["chapter"],
                        "stdout": actual, "line_count": len(widths),
                        "maximum_line_width": max(widths, default=0)})
    return {"snippets_executed": len(results), "results": results}


if __name__ == "__main__":
    print(json.dumps(run_examples(), indent=2, sort_keys=True))
