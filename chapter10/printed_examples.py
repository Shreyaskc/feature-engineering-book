"""Run each complete printed listing in its own fresh Python process."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def run() -> list[dict]:
    snippets = json.loads((ROOT / "printed_snippets.json").read_text(encoding="utf-8"))
    result = []
    identifiers = set()
    for snippet in snippets:
        if set(snippet) != {"id", "title", "code", "expected_stdout"}:
            raise AssertionError("printed snippet fields mismatch")
        if snippet["id"] in identifiers:
            raise AssertionError("duplicate snippet id")
        identifiers.add(snippet["id"])
        if any(len(line) > 72 for line in snippet["code"].splitlines()):
            raise AssertionError(f"listing exceeds 72 columns: {snippet['id']}")
        execution = subprocess.run(
            [sys.executable, "-B", "-c", snippet["code"]], cwd=ROOT,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0"),
            text=True, capture_output=True, timeout=30)
        if execution.returncode:
            raise AssertionError(f"listing failed: {snippet['id']}\n{execution.stderr}")
        if execution.stdout != snippet["expected_stdout"]:
            raise AssertionError(f"listing stdout mismatch: {snippet['id']}")
        result.append({"id": snippet["id"], "title": snippet["title"],
                       "stdout": execution.stdout})
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
