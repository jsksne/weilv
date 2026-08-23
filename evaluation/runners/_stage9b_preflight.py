"""Stage 9B — real-data preflight runner (PRECHECK only, never FORMAL).

Runs the frozen preprocessor and the runner's PRECHECK over the pinned
HeartSteps release found in the cache directory and emits the data-dependent
pre-formal artifacts:

- preprocessing_flow_v1.json
- preprocessing_flow_by_user_v1.csv
- stage9_public_release_exclusion_rules_v1.json
- stage9_leakage_test_report_v1.json

It NEVER computes or persists Delta_V / bootstrap CI / CR-CF-001 and never
executes the frozen model on the real cohort (PRECHECK is data-driven).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.stage9.preprocess_heartsteps_v1 import (
    _read_csv,
    apply_eligibility,
    build_analysis_rows,
    run_preprocessing,
    verify_pinned_files,
)
from evaluation.stage9.run_stage9_external_cf import (
    check_integrity_gates,
    run_precheck,
)

CACHE_DIR = ROOT / ".runtime" / "stage9_heartsteps"
PREFORMAL = ROOT / "evaluation" / "stage9" / "preformal"


def main() -> int:
    if not (CACHE_DIR / "suggestions.csv").exists():
        print(
            f"[preflight] missing pinned HeartSteps files in {CACHE_DIR}; "
            "place users.csv, suggestions.csv, gfsteps.csv, jbsteps.csv there "
            "(from HeartSteps V1 commit "
            "3016391de426116bdef41880d72bc8cd4b9b2477) and re-run.",
            file=sys.stderr,
        )
        return 2

    verification = verify_pinned_files(CACHE_DIR)
    print("[preflight] pinned hashes:", json.dumps(verification, indent=2)[:600])

    # 1) preprocessing -> flow + exclusion-rules artifacts
    summary = run_preprocessing(
        CACHE_DIR, PREFORMAL, verify_hashes=True, duplicate_policy="report"
    )
    print(
        "[preflight] preprocessing: raw={raw_rows} final={final_primary_rows} "
        "users={users}".format(**summary)
    )

    # 2) integrity gates + PRECHECK leakage report (no model execution)
    gates = check_integrity_gates(CACHE_DIR, duplicate_policy="report")
    users = _read_csv(CACHE_DIR / "users.csv")
    suggestions = _read_csv(CACHE_DIR / "suggestions.csv")
    flow = apply_eligibility(suggestions, users, duplicate_policy="report")
    analysis_rows = build_analysis_rows(flow["final_rows"], flow)
    report = run_precheck(analysis_rows, gates, PREFORMAL)
    print(
        "[preflight] leakage checks:",
        json.dumps(report["leakage_checks"], indent=2),
    )
    print("[preflight] formal_result_computed:", report["formal_result_computed"])
    print("[preflight] model_executed_on_real_data:",
          report["model_executed_on_real_data"])
    print(f"[preflight] artifacts written to {PREFORMAL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
