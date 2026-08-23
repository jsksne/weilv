"""Stage 8 — build the post-run audit acceptance bundle ZIP."""

import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUN_ID = "20260818T020417Z_stage8_formal"
AUDIT_DIR = ROOT / "evaluation" / "stage8" / "postrun_audit_v1"
RUN_DIR = ROOT / "evaluation" / "runs" / RUN_ID
REVIEW_CSV = ROOT / "evaluation" / "reviews" / "stage8_agentic_factor_coverage_human_review_v1.csv"
ZIP_PATH = ROOT / "evaluation" / "stage8_postrun_audit_acceptance_bundle.zip"

ENTRIES = [
    # correction artifacts
    (AUDIT_DIR / "postrun_audit_report.md", "correction/postrun_audit_report.md"),
    (AUDIT_DIR / "corrected_claim_results.csv", "correction/corrected_claim_results.csv"),
    (AUDIT_DIR / "corrected_evaluator_metrics.json", "correction/corrected_evaluator_metrics.json"),
    (AUDIT_DIR / "candidate_invariance_audit.json", "correction/candidate_invariance_audit.json"),
    (AUDIT_DIR / "guard_unsafe_leakage_audit.json", "correction/guard_unsafe_leakage_audit.json"),
    (AUDIT_DIR / "evidence_audit.json", "correction/evidence_audit.json"),
    (AUDIT_DIR / "stage8_agentic_factor_coverage_human_review_v1.csv", "correction/stage8_agentic_factor_coverage_human_review_v1.csv"),
    (AUDIT_DIR / "stage8_soft_preference_alignment_audit_v1.csv", "correction/stage8_soft_preference_alignment_audit_v1.csv"),
    (AUDIT_DIR / "raw_results_sha256.txt", "correction/raw_results_sha256.txt"),
    # factor human review (canonical location)
    (REVIEW_CSV, "factor_review/stage8_agentic_factor_coverage_human_review_v1.csv"),
    # changed evaluator source / tests
    (ROOT / "evaluation/runners/run_stage8_formal_evaluation.py", "evaluator/run_stage8_formal_evaluation.py"),
    (ROOT / "evaluation/runners/_stage8_postrun_audit.py", "evaluator/_stage8_postrun_audit.py"),
    (ROOT / "tests/test_stage8_formal_evaluator.py", "evaluator/tests/test_stage8_formal_evaluator.py"),
    # reference to the original frozen run
    (RUN_DIR / "runtime_provenance.json", "original_run/runtime_provenance.json"),
    (RUN_DIR / "raw_results.jsonl", "original_run/raw_results.jsonl"),
    (RUN_DIR / "claim_results.csv", "original_run/claim_results.csv"),
    (ROOT / "evaluation/manifests/stage8_gold_v1_2_manifest.json", "gold/stage8_gold_v1_2_manifest.json"),
]

MANIFEST = {
    "artifact": "stage8_postrun_audit_acceptance_bundle",
    "created_at": datetime.now(UTC).isoformat(),
    "original_frozen_run_id": RUN_ID,
    "note": "derived-artifact correction only; NO production rerun",
    "raw_results_sha256": (AUDIT_DIR / "raw_results_sha256.txt").read_text(encoding="utf-8").strip().splitlines()[1],
    "entries": [archive for _, archive in ENTRIES],
    "secrets_excluded": [".env", "DASHSCOPE_API_KEY"],
}


def main() -> None:
    missing = [path for path, _ in ENTRIES if not path.exists()]
    if missing:
        raise SystemExit(f"missing files: {missing}")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path, archive in ENTRIES:
            bundle.write(path, archive)
        bundle.writestr("manifest.json", json.dumps(MANIFEST, ensure_ascii=False, indent=2))
    sha = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    print(f"zip: {ZIP_PATH}")
    print(f"sha256: {sha}")
    (AUDIT_DIR / "acceptance_bundle_sha256.txt").write_text(
        f"{ZIP_PATH.name}\n{sha}\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
