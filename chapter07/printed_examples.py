"""Verify every printed snippet in its own fresh Python process."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).parent


def run_examples() -> dict:
    snippets = json.loads((ROOT / "printed_snippets.json").read_text(encoding="utf-8"))
    results, seen = [], set()
    for snippet in snippets:
        if snippet["id"] in seen:
            raise AssertionError("duplicate printed snippet ID")
        seen.add(snippet["id"])
        widths = [len(line) for line in snippet["code"].splitlines()]
        if max(widths, default=0) > 74:
            raise AssertionError(f"snippet exceeds 74 columns: {snippet['id']}")
        completed = subprocess.run([sys.executable, "-c", snippet["code"]],
                                   cwd=ROOT, capture_output=True, text=True, check=True)
        if completed.stderr or completed.stdout != snippet["expected_stdout"]:
            raise AssertionError(f"printed output drift: {snippet['id']}: {completed.stdout!r}")
        results.append({"id": snippet["id"], "chapter": snippet["chapter"],
                        "stdout": completed.stdout, "line_count": len(widths),
                        "maximum_line_width": max(widths, default=0)})
    return {"snippets_executed": len(results), "fresh_process_per_snippet": True,
            "results": results}


if __name__ == "__main__":
    print(json.dumps(run_examples(), indent=2, sort_keys=True))
