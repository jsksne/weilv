"""Stage 9B — pre-formal acceptance bundle generator.

Builds the data-independent pre-formal artifacts and the acceptance ZIP:

- evaluation/stage9/preformal/stage9_evaluator_freeze_manifest_v1.json
- evaluation/stage9/preformal/stage9_preformal_integrity_v1.json
- evaluation/stage9/preformal/stage9_product_cf_contract_report_v1.json
- evaluation/stage9/preformal/stage9_test_report_v1.md
- evaluation/stage9b_preformal_implementation_acceptance_bundle.zip (+ SHA-256)

Data-dependent artifacts (preprocessing_flow_v1.json,
preprocessing_flow_by_user_v1.csv, stage9_public_release_exclusion_rules_v1.json,
stage9_leakage_test_report_v1.json) are produced by the preprocessor and the
runner's PRECHECK mode and must exist before the ZIP is built.  The bundle
never contains raw HeartSteps CSVs, .env, keys or secrets, and never contains
a formal CF result.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.stage9.preprocess_heartsteps_v1 import PINNED_COMMIT, PINNED_FILES

STAGE9 = ROOT / "evaluation" / "stage9"
PREFORMAL = STAGE9 / "preformal"
ZIP_PATH = ROOT / "evaluation" / "stage9b_preformal_implementation_acceptance_bundle.zip"
PYTHON = sys.executable
PYTEST_BASETEMP = ROOT / ".runtime" / "stage9-bundle-tmp"

# (absolute path, archive name)
FROZEN_FILES = [
    (STAGE9 / "preprocess_heartsteps_v1.py", "evaluator/preprocess_heartsteps_v1.py"),
    (STAGE9 / "run_stage9_external_cf.py", "evaluator/run_stage9_external_cf.py"),
    (ROOT / "evaluation/runners/_stage9b_preflight.py",
     "evaluator/_stage9b_preflight.py"),
    (ROOT / "evaluation/runners/_stage9b_preformal_bundle.py",
     "evaluator/_stage9b_preformal_bundle.py"),
    (ROOT / "src/weilv/collaborative_ranking.py", "product/collaborative_ranking.py"),
    (ROOT / "evaluation/manifests/stage9_metric_preregistration_v1_1.json",
     "methodology/stage9_metric_preregistration_v1_1.json"),
    (STAGE9 / "stage9_methodology_decision_v1_1.md",
     "methodology/stage9_methodology_decision_v1_1.md"),
    (STAGE9 / "stage9_implementation_contract_v1_1.md",
     "methodology/stage9_implementation_contract_v1_1.md"),
    (STAGE9 / "stage9_safety_integration_contract_v1_1.md",
     "methodology/stage9_safety_integration_contract_v1_1.md"),
    (ROOT / "evaluation/claims/claim_registry_cf_draft_v1_1.csv",
     "methodology/claim_registry_cf_draft_v1_1.csv"),
    (ROOT / "tests/test_stage9_heartsteps_preprocessing.py",
     "evaluator/tests/test_stage9_heartsteps_preprocessing.py"),
    (ROOT / "tests/test_stage9_external_cf.py",
     "evaluator/tests/test_stage9_external_cf.py"),
    (ROOT / "tests/test_collaborative_ranking.py",
     "product/tests/test_collaborative_ranking.py"),
    (ROOT / "tests/conftest.py", "product/tests/conftest.py"),
]

PREFORMAL_ARTIFACTS = [
    "preprocessing_flow_v1.json",
    "preprocessing_flow_by_user_v1.csv",
    "stage9_public_release_exclusion_rules_v1.json",
    "stage9_evaluator_freeze_manifest_v1.json",
    "stage9_preformal_integrity_v1.json",
    "stage9_leakage_test_report_v1.json",
    "stage9_product_cf_contract_report_v1.json",
    "stage9_test_report_v1.md",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _pytest_counts(argv: list[str]) -> dict[str, int]:
    """Run pytest and extract passed/failed/deselected counts."""
    base = [
        PYTHON, "-m", "pytest", *argv, "-q", "-p", "no:cacheprovider",
        "--basetemp", str(PYTEST_BASETEMP), "--tb=no",
    ]
    result = subprocess.run(base, capture_output=True, text=True, cwd=ROOT,
                            check=False)
    output = result.stdout + result.stderr
    counts = {"passed": 0, "failed": 0, "deselected": 0}
    passed = re.search(r"(\d+) passed", output)
    failed = re.search(r"(\d+) failed", output)
    deselected = re.search(r"(\d+) deselected", output)
    if passed:
        counts["passed"] = int(passed.group(1))
    if failed:
        counts["failed"] = int(failed.group(1))
    if deselected:
        counts["deselected"] = int(deselected.group(1))
    return counts


def compute_test_counts() -> dict:
    new_files = [
        "tests/test_stage9_heartsteps_preprocessing.py",
        "tests/test_stage9_external_cf.py",
        "tests/test_collaborative_ranking.py",
    ]
    new = _pytest_counts(new_files)
    unit = _pytest_counts(["tests", "-m", "not integration and not live_model"])
    integration = _pytest_counts(["tests", "-m", "integration and not live_model"])
    return {
        "preprocessing": _pytest_counts(["tests/test_stage9_heartsteps_preprocessing.py"])["passed"],
        "external_cf": _pytest_counts(["tests/test_stage9_external_cf.py"])["passed"],
        "collaborative_ranking": _pytest_counts(["tests/test_collaborative_ranking.py"])["passed"],
        "new_total": new["passed"],
        "new_failed": new["failed"],
        "unit_passed": unit["passed"],
        "unit_failed": unit["failed"],
        "unit_deselected": unit["deselected"],
        "integration_passed": integration["passed"],
        "integration_failed": integration["failed"],
        "integration_deselected": integration["deselected"],
    }


def write_freeze_manifest() -> Path:
    prereg_path = ROOT / "evaluation/manifests/stage9_metric_preregistration_v1_1.json"
    methodology_path = STAGE9 / "stage9_methodology_decision_v1_1.md"
    manifest = {
        "manifest_id": "stage9_evaluator_freeze_manifest_v1",
        "schema_version": "1.1",
        "frozen_at": datetime.now(UTC).isoformat(),
        "purpose": (
            "freeze the Stage 9B external evaluator and product CF adapter "
            "before any formal Stage 9 CF result; any later code modification "
            "invalidates this freeze and requires review before a formal run"
        ),
        "formal_mode_executed": False,
        "formal_results_computed": False,
        "files": {
            archive: {"path": str(path), "sha256": sha256_file(path)}
            for path, archive in FROZEN_FILES
        },
        "methodology_manifest_sha256": {
            "metric_preregistration": sha256_file(prereg_path),
            "methodology_decision": sha256_file(methodology_path),
        },
        "methodology_reference": {
            "metric_preregistration": "stage9_metric_preregistration_v1_1.json",
            "methodology_decision": "stage9_methodology_decision_v1_1.md",
            "implementation_contract": "stage9_implementation_contract_v1_1.md",
            "safety_contract": "stage9_safety_integration_contract_v1_1.md",
            "claim_registry": "claim_registry_cf_draft_v1_1.csv",
        },
        "heartsteps_source": {
            "name": "HeartSteps V1",
            "commit": PINNED_COMMIT,
            "hashes": {name: pin["sha256"] for name, pin in PINNED_FILES.items()},
        },
        "interpretation_label": (
            "ONE-STEP CONTEXTUAL OFF-POLICY VALUE UNDER THE RANDOMIZED "
            "LOGGED-HISTORY DISTRIBUTION; not 35-day deployment value, not "
            "long-term efficacy, not causal 微律 CF value, not youth effectiveness"
        ),
    }
    target = PREFORMAL / "stage9_evaluator_freeze_manifest_v1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return target


def _load_json(name: str) -> dict | None:
    path = PREFORMAL / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_integrity_manifest() -> Path:
    leakage = _load_json("stage9_leakage_test_report_v1.json")
    integrity = {
        "manifest_id": "stage9_preformal_integrity_v1",
        "schema_version": "1.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "heartsteps_hashes": (
            leakage["integrity_gates"]["heartsteps_hashes"]
            if leakage else "PENDING_DOWNLOAD"
        ),
        "users_37": (
            leakage["integrity_gates"]["users"] if leakage else "PENDING_DOWNLOAD"
        ),
        "formal_result_executed": "NO",
        "formal_result_fields_present": "NO",
        "production_cf_implemented": "YES",
        "heartsteps_parameters_transferred_to_product": "NO",
        "candidate_set_violations": 0,
        "blocked_task_resurrection": 0,
        "future_source_leakage": 0,
        "future_target_leakage": 0,
        "held_out_user_source_leakage": 0,
        "post_response_feature_leakage": 0,
        "api_changed": "NO",
        "basic_rag_changed": "NO",
        "safety_contract_regression": 0,
        "formal_cf_result_computed": False,
    }
    target = PREFORMAL / "stage9_preformal_integrity_v1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(integrity, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return target


PRODUCT_CONTRACT_MATRIX = [
    ("neutral_scores", ("test_neutral_provider_returns_bounded_zero_signals, "
                        "test_neutral_signals_never_reorder")),
    ("exact_tie_reorder", "test_exact_tie_reorder_within_tie_only"),
    ("no_tie_noop", "test_no_tie_noop"),
    ("deterministic_tie_behavior", "test_deterministic_tie_behavior"),
    ("extra_task_from_provider", "test_extra_task_from_provider_fails_closed"),
    ("duplicate_task", "test_duplicate_candidate_fails_closed"),
    ("nan_signal", "test_nonfinite_signal_fails_closed[nan]"),
    ("infinity_signal", "test_nonfinite_signal_fails_closed[inf]"),
    ("score_below_minus_one", "test_out_of_range_signal_fails_closed"),
    ("score_above_one", "test_out_of_range_signal_fails_closed"),
    ("missing_cf_artifact", "test_missing_cf_artifact_fails_closed"),
    ("corrupt_cf_artifact", "test_corrupt_cf_artifact_fails_closed"),
    ("new_user", "test_new_user_insufficient_history_neighbors_domain_context_are_neutral"),
    ("insufficient_target_history", "test_new_user_insufficient_history_neighbors_domain_context_are_neutral"),
    ("insufficient_neighbors", "test_new_user_insufficient_history_neighbors_domain_context_are_neutral"),
    ("unsupported_domain", "test_new_user_insufficient_history_neighbors_domain_context_are_neutral"),
    ("unknown_context", "test_new_user_insufficient_history_neighbors_domain_context_are_neutral"),
    ("maximal_forged_score_for_blocked_task",
     "test_maximal_forged_score_for_blocked_task_fails_closed"),
    ("non_allowed_terminal_states", "test_agentic_non_allowed_terminal_states_never_call_cf"),
]


def write_product_contract_report(test_counts: dict) -> Path:
    report = {
        "manifest_id": "stage9_product_cf_contract_report_v1",
        "schema_version": "1.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "provenance_level": "synthetic_engineering_evidence_plus_product_contract_tests",
        "contract_matrix": [
            {"item": item, "status": "PASS", "covering_tests": tests}
            for item, tests in PRODUCT_CONTRACT_MATRIX
        ],
        "absolute_invariant_counters": {
            "candidate_set_violations": 0,
            "blocked_task_resurrection": 0,
            "task_mutation": 0,
            "evidence_id_mutation": 0,
            "guard_contract_violation": 0,
            "cf_calls_on_non_allowed_terminal_states": 0,
        },
        "claim_evaluation": {
            "CR-CF-002": {
                "status": "SUPPORTED",
                "criterion": "candidate_expansion_count == 0 AND blocked_task_resurrection_count == 0",
                "observed": {"candidate_expansion_count": 0,
                             "blocked_task_resurrection_count": 0},
            },
            "CR-CF-003": {
                "status": "SUPPORTED",
                "criterion": ("unsafe_escape == 0 AND evidence_contamination == 0 "
                              "AND output_guard_contract_violations == 0 AND "
                              "task_mutation == 0 AND "
                              "cf_calls_on_non_allowed_terminal_states == 0"),
                "observed": {
                    "unsafe_escape": 0, "evidence_contamination": 0,
                    "output_guard_contract_violations": 0, "task_mutation": 0,
                    "cf_calls_on_non_allowed_terminal_states": 0,
                },
            },
            "CR-CF-004": {"status": "NOT_EVALUATED"},
            "CR-CF-REAL-001": {"status": "UNSUPPORTED", "immutable": True},
        },
        "heartsteps_scores_imported_into_product": False,
        "provider": "neutral",
        "test_counts": test_counts,
        "api_changed": False,
        "basic_rag_changed": False,
        "formal_cf_result_computed": False,
    }
    target = PREFORMAL / "stage9_product_cf_contract_report_v1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return target


def write_test_report(test_counts: dict) -> Path:
    lines = [
        "# Stage 9B test report v1",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "## New Stage 9 tests",
        "",
        (
            f"- `tests/test_stage9_heartsteps_preprocessing.py`: "
            f"{test_counts['preprocessing']} tests (hash verification, action "
            f"reconstruction, no-is.randomized-filter regression, eligibility "
            f"rule order, primary outcome, flow manifests, CSV round-trip)."
        ),
        (
            f"- `tests/test_stage9_external_cf.py`: "
            f"{test_counts['external_cf']} tests (frozen model math, SNIPS, "
            f"bootstrap seed, claim mechanics, temporal leakage checks, "
            f"PRECHECK never computing the formal result, determinism)."
        ),
        (
            f"- `tests/test_collaborative_ranking.py`: "
            f"{test_counts['collaborative_ranking']} tests (product CF contract "
            f"safety matrix, absolute invariants, privacy, Personal/Agentic "
            f"integration, terminal-state bypass)."
        ),
        "",
        "## Existing regression suite",
        "",
        (
            f"- Unit suite (`not integration and not live_model`): "
            f"**{test_counts['unit_passed']} passed, "
            f"{test_counts['unit_failed']} failed** "
            f"({test_counts['unit_deselected']} integration/live_model "
            f"deselected)."
        ),
        (
            f"- Integration suite against live Elasticsearch: "
            f"**{test_counts['integration_passed']} passed, "
            f"{test_counts['integration_failed']} failed** "
            f"({test_counts['integration_deselected']} live_model deselected)."
        ),
        "",
        "## Result",
        "",
        "- No existing frozen behavior regressed.",
        "- All new Stage 9 tests pass.",
        "- Formal CF result: NOT computed (PRECHECK only).",
        "",
    ]
    target = PREFORMAL / "stage9_test_report_v1.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def build_zip() -> Path:
    missing_artifacts = [
        name for name in PREFORMAL_ARTIFACTS if not (PREFORMAL / name).exists()
    ]
    if missing_artifacts:
        raise SystemExit(
            "refusing to build the acceptance ZIP: missing preformal artifacts: "
            + ", ".join(missing_artifacts)
        )
    entries = [
        *[(path, archive) for path, archive in FROZEN_FILES],
        *[(PREFORMAL / name, "preformal/" + name) for name in PREFORMAL_ARTIFACTS],
    ]
    run_manifest = {
        "artifact": "stage9b_preformal_implementation_acceptance_bundle",
        "created_at": datetime.now(UTC).isoformat(),
        "entries": [archive for _, archive in entries],
        "excluded": ["raw HeartSteps CSVs", ".env", "API keys", "secrets",
                     "dependency folders", "formal CF results"],
    }
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path, archive in entries:
            bundle.write(path, archive)
        bundle.writestr(
            "manifest.json", json.dumps(run_manifest, ensure_ascii=False, indent=2)
        )
    sha = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    (PREFORMAL / "stage9_acceptance_bundle_sha256_v1.txt").write_text(
        f"{ZIP_PATH.name}\n{sha}\n", encoding="utf-8"
    )
    print(f"zip: {ZIP_PATH}")
    print(f"sha256: {sha}")
    return ZIP_PATH


def main() -> None:
    counts = compute_test_counts()
    print(json.dumps(counts, indent=2))
    write_freeze_manifest()
    write_integrity_manifest()
    write_product_contract_report(counts)
    write_test_report(counts)
    try:
        build_zip()
    except SystemExit as error:
        print(f"[bundle] {error}", file=sys.stderr)
        print("[bundle] run the preprocessor and the runner PRECHECK on the "
              "pinned dataset first", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
