"""Run the exact chapter listings, each in its own Python process."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def run_snippets() -> list[dict]:
    snippets = json.loads((ROOT / "printed_snippets.json").read_text(encoding="utf-8"))
    results = []
    for item in snippets:
        run = subprocess.run([sys.executable, "-B", "-c", item["code"]], cwd=ROOT,
                             capture_output=True, text=True, timeout=15, check=True)
        if run.stderr or run.stdout != item["stdout"]:
            raise AssertionError(f"listing output mismatch: {item['id']}")
        results.append({"id": item["id"], "stdout": run.stdout})
    return results


if __name__ == "__main__":
    print(json.dumps(run_snippets(), indent=2, sort_keys=True))
