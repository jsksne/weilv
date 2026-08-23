"""Stage 8 — build the acceptance bundle ZIP and report its SHA-256."""

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
RUN_DIR = ROOT / "evaluation" / "runs" / RUN_ID
ZIP_PATH = ROOT / "evaluation" / "stage8_formal_acceptance_bundle.zip"

# (absolute path, archive name)
ENTRIES = [
    (ROOT / "evaluation/manifests/stage8_gold_v1_2_manifest.json",
     "gold/stage8_gold_v1_2_manifest.json"),
    (ROOT / "evaluation/datasets/agentic_complex_gold_frozen_v1_2.jsonl",
     "gold/agentic_complex_gold_frozen_v1_2.jsonl"),
    (ROOT / "evaluation/reviews/agentic_complex_gold_consensus_review_v1_2.csv",
     "gold/agentic_complex_gold_consensus_review_v1_2.csv"),
    (ROOT / "evaluation/reviews/agentic_complex_gold_review_v1_2.csv",
     "gold/agentic_complex_gold_review_v1_2_draft.csv"),
    (ROOT / "evaluation/reviews/agentic_complex_gold_task_audit_v1_2.csv",
     "gold/agentic_complex_gold_task_audit_v1_2.csv"),
    (ROOT / "evaluation/datasets/safety_gold_v1.jsonl", "gold/safety_gold_v1.jsonl"),
    (ROOT / "evaluation/STAGE6_FROZEN.md", "gold/STAGE6_FROZEN.md"),
    (ROOT / "evaluation/manifests/stage8_metric_preregistration_v1_2.json",
     "preregistration/stage8_metric_preregistration_v1_2.json"),
    (ROOT / "evaluation/claims/claim_registry_agentic_draft_v1_2.csv",
     "preregistration/claim_registry_agentic_draft_v1_2.csv"),
    (ROOT / "evaluation/runners/run_stage8_formal_evaluation.py",
     "evaluator/run_stage8_formal_evaluation.py"),
    (ROOT / "evaluation/runners/_stage8_validate_gold_draft.py",
     "evaluator/_stage8_validate_gold_draft.py"),
    (ROOT / "evaluation/runners/_stage8_freeze_gold.py",
     "evaluator/_stage8_freeze_gold.py"),
    (ROOT / "evaluation/runners/_stage8_fill_factor_coverage.py",
     "evaluator/_stage8_fill_factor_coverage.py"),
    (ROOT / "evaluation/runners/_stage8_verify_integrity.py",
     "evaluator/_stage8_verify_integrity.py"),
    (ROOT / "tests/test_stage8_formal_evaluator.py",
     "evaluator/tests/test_stage8_formal_evaluator.py"),
    (RUN_DIR / "raw_results.jsonl", "results/raw_results.jsonl"),
    (RUN_DIR / "case_metrics.csv", "results/case_metrics.csv"),
    (RUN_DIR / "system_metrics.csv", "results/system_metrics.csv"),
    (RUN_DIR / "factor_coverage_cases.csv", "results/factor_coverage_cases.csv"),
    (RUN_DIR / "factor_coverage_metrics.csv", "results/factor_coverage_metrics.csv"),
    (RUN_DIR / "safety_results.csv", "results/safety_results.csv"),
    (RUN_DIR / "safety_summary.json", "results/safety_summary.json"),
    (RUN_DIR / "memory_results.csv", "results/memory_results.csv"),
    (RUN_DIR / "agentic_diagnostics.jsonl", "results/agentic_diagnostics.jsonl"),
    (RUN_DIR / "isolation_audit.json", "audits/isolation_audit.json"),
    (RUN_DIR / "cleanup_audit.json", "audits/cleanup_audit.json"),
    (RUN_DIR / "retry_log.json", "audits/retry_log.json"),
    (RUN_DIR / "runtime_provenance.json", "audits/runtime_provenance.json"),
    (RUN_DIR / "claim_results.csv", "results/claim_results.csv"),
    (RUN_DIR / "run_manifest.json", "results/run_manifest.json"),
    (RUN_DIR / "formal_evaluation_summary.md", "summary/formal_evaluation_summary.md"),
    (RUN_DIR / "test_integrity_summary.md", "summary/test_integrity_summary.md"),
]

RUN_MANIFEST = {
    "artifact": "stage8_formal_acceptance_bundle",
    "created_at": datetime.now(UTC).isoformat(),
    "run_id": RUN_ID,
    "entries": [archive for _, archive in ENTRIES],
    "secrets_excluded": [".env", ".env.example", "DASHSCOPE_API_KEY", "ES passwords"],
}


def main() -> None:
    missing = [path for path, _ in ENTRIES if not path.exists()]
    if missing:
        raise SystemExit(f"missing files: {missing}")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path, archive in ENTRIES:
            bundle.write(path, archive)
        bundle.writestr(
            "manifest.json", json.dumps(RUN_MANIFEST, ensure_ascii=False, indent=2)
        )
    sha = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    print(f"zip: {ZIP_PATH}")
    print(f"sha256: {sha}")
    (RUN_DIR / "acceptance_bundle_sha256.txt").write_text(
        f"{ZIP_PATH.name}\n{sha}\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
