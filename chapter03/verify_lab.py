"""Run the portable repository checks in isolated temporary copies."""
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    raise SystemExit(subprocess.call([sys.executable, "-B", str(root / "verify_all.py"), "--chapter", "03"], cwd=root))
