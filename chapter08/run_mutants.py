"""Run the allowlisted local fault experiment; no dynamic imports or edits.

Default exit0 means the experiment completed, not that faulty versions are
correct. With --implementation, exit0=all selected checks pass,
exit1=specified assertion mismatch, exit2=unexpected harness error.
"""
import argparse
import json

from fault_testing_lab import IMPLEMENTATIONS, mutation_report, run_suite


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print full evidence")
    parser.add_argument("--implementation", choices=tuple(IMPLEMENTATIONS))
    parser.add_argument("--suite", choices=("weak", "diagnostic"), default="diagnostic")
    args = parser.parse_args()
    if args.implementation:
        result = run_suite(args.implementation, suite=args.suite)
        print(json.dumps(result, indent=2, sort_keys=True))
        if any(cell["status"] == "ERROR" for cell in result["checks"].values()):
            return 2
        return 0 if result["passed"] else 1
    result = mutation_report()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("Check                    REF M1 M2 M3 M4 M5")
        for name, row in result["matrix"].items():
            marks = [" ." if status == "PASS" else " X" for status in row.values()]
            print(f"{name:24s} " + " ".join(marks))
        print(". = PASS; X = ASSERTION_FAILED; unexpected ERROR aborts")
        for name, suite in result["suite_results"].items():
            print(f"{name}: {suite['detected_count']}/5 selected faults detected")
        print("Conditional on these five faults, fixtures and assertions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
