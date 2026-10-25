"""The seven chapter listings, executed verbatim in isolated namespaces."""

from parity_lab import canonical_json

LISTING_TITLES = (
    "Fixed means fixed", "Policy publication is a source calculation",
    "A missing cell and its fallback", "Two lag causes at one request",
    "The same number with the wrong revision", "Missing evidence is unverifiable",
    "Finite floating-point tolerance is an explicit choice",
)

# Listing 1
LISTINGS = (
'''from dataclasses import replace
from parity_lab import KEY, build_fixture
trace, _ = build_fixture()
fixed = trace.source.reference(KEY, 610).value
rolling_key = replace(KEY, window_start=550, window_end=610)
rolling = trace.source.reference(rolling_key, 610).value
assert (fixed, rolling) == (85, 95)
result = {"fixed": fixed, "rolling": rolling}''',

# Listing 2
'''from parity_lab import build_fixture
trace, _ = build_fixture()
published = [(p.revision, p.source_cutoff, p.value)
             for p in trace.publications]
assert published == [(1, 600, 50), (2, 605, 45), (3, 607, 85)]
assert trace.source.reference(trace.key, 620).value == 100
assert trace.policy_at(620).value == 85
result = {"published": published, "late": trace.after_deadline_at(620)}''',

# Listing 3
'''from parity_lab import build_fixture
trace, logs = build_fixture()
miss = logs[0]
assert miss.raw_value is None and miss.feature_missing is True
assert miss.model_input == 0 and miss.fallback_value == 0
assert miss.fallback_used and miss.fallback_reason == "cache_miss"
result = {"raw": miss.raw_value, "model": miss.model_input,
          "missing": miss.feature_missing, "reason": miss.fallback_reason}''',

# Listing 4
'''from parity_lab import build_fixture, reconcile
trace, logs = build_fixture()
row = reconcile(trace, logs)["rows"][3]
assert row["expected_policy"]["value"] == 85
assert row["expected_store"]["record"]["value"] == 45
assert row["expected_cache"]["record"]["value"] == 50
assert {"materialization_lag", "cache_lag"} <= set(row["flags"])
result = {"request": row["request_id"], "flags": row["flags"]}''',

# Listing 5
'''from dataclasses import replace
from parity_lab import build_fixture, reconcile
trace, logs = build_fixture()
wrong_revision = replace(logs[4], value_revision=1)
row = reconcile(trace, [wrong_revision])["rows"][0]
assert row["comparisons"]["policy_numeric_match"] is True
assert row["comparisons"]["trace_provenance_match"] is False
result = {"numeric_match": True, "flags": row["flags"]}''',

# Listing 6
'''from dataclasses import replace
from parity_lab import KEY, SourceHistory, build_fixture, reconcile
trace, logs = build_fixture()
partial = replace(
    logs[4], present_fields=logs[4].present_fields - {"value_revision"})
row = reconcile(trace, [partial])["rows"][0]
assert row["comparisons"]["policy_full_match"] is None
assert "insufficient_evidence" in row["flags"]
assert SourceHistory(known=False).reference(KEY, 610).value is None
assert SourceHistory().reference(KEY, 610).value == 0
result = {"full_match": None, "absent": row["absent_log_fields"]}''',

# Listing 7
'''from parity_lab import numeric_equal
tolerance = {"rel_tol": 1e-9, "abs_tol": 1e-12}
assert numeric_equal(0.0, 5e-13, **tolerance)
assert not numeric_equal(0.0, 2e-12, **tolerance)
assert not numeric_equal(84, 85)
assert not numeric_equal(None, None)
result = {"near_zero_inside": True, "near_zero_outside": False,
          "integer_match": False, "missing_is_numeric_match": False}''',
)


def run_listings() -> list[dict]:
    results = []
    for number, (title, listing) in enumerate(zip(LISTING_TITLES, LISTINGS), 1):
        if len(listing.splitlines()) > 12:
            raise AssertionError(f"Listing {number} exceeds twelve lines")
        namespace: dict = {}
        exec(compile(listing, f"chapter6-listing-{number}", "exec"), namespace)
        results.append({"listing": number, "title": title, "result": namespace["result"]})
    return results


if __name__ == "__main__":
    print(canonical_json(run_listings()), end="")
