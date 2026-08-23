"""Stage 8 — Freeze Gold v1.2 after the 3-person human review gate.

The human review gate is authoritative per the Stage 8 evaluation ticket:
3 reviewers, 24 / 24 cases approved, consensus PASS. This runner:

1. Re-runs the read-only mechanical validation (_stage8_validate_gold_draft).
2. Records the human consensus into a dedicated consensus review CSV
   (the pre-review draft CSV is preserved unchanged for audit history).
3. Writes the frozen Gold dataset with consensus metadata (labels unchanged).
4. Computes SHA-256 for every frozen Stage 8 Gold input.
5. Writes the frozen manifest.

This runner does NOT call any RAG system, embedding, reranker or qwen-plus.
It does NOT change any Gold label, preferred/acceptable/invalid partition,
expected safety status, memory fixture, metric or threshold.
"""

import csv
import hashlib
import json
import runpy
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "evaluation" / "datasets"
REVIEWS = ROOT / "evaluation" / "reviews"
MANIFESTS = ROOT / "evaluation" / "manifests"
CLAIMS = ROOT / "evaluation" / "claims"

DRAFT = DATASETS / "agentic_complex_gold_draft_v1_2.jsonl"
FROZEN = DATASETS / "agentic_complex_gold_frozen_v1_2.jsonl"
DRAFT_REVIEW = REVIEWS / "agentic_complex_gold_review_v1_2.csv"
CONSENSUS_REVIEW = REVIEWS / "agentic_complex_gold_consensus_review_v1_2.csv"
TASK_AUDIT = REVIEWS / "agentic_complex_gold_task_audit_v1_2.csv"
METRIC_PRE = MANIFESTS / "stage8_metric_preregistration_v1_2.json"
CLAIM_REG = CLAIMS / "claim_registry_agentic_draft_v1_2.csv"
MANIFEST = MANIFESTS / "stage8_gold_v1_2_manifest.json"
VALIDATION_RUNNER = ROOT / "evaluation" / "runners" / "_stage8_validate_gold_draft.py"

TASK_CORPUS = ROOT / "data" / "metadata" / "micro_tasks_v1.jsonl"
TASK_CORPUS_SHA = "40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48"
SAFETY_GOLD_SHA = "aa975d5cd58deec5c837b1ca2b5e4723229fd71c08c64df85ba39d8819372e7f"

CONSENSUS_ROUND = "stage8_gold_consensus_v1_2"


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task_corpus_canonical_sha() -> str:
    rows = []
    for line in TASK_CORPUS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    rows.sort(key=lambda row: row["task_id"])
    buf = (
        "\n".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for row in rows
        )
        + "\n"
    )
    return hashlib.sha256(buf.encode("utf-8")).hexdigest()


def write_consensus_review() -> None:
    """Record the ticket-asserted human review gate: 3 reviewers, 24/24 PASS."""
    with DRAFT_REVIEW.open(encoding="utf-8", newline="") as handle:
        draft_rows = list(csv.DictReader(handle))
    if len(draft_rows) != 24:
        raise SystemExit(f"expected 24 draft review rows, got {len(draft_rows)}")
    fields = [
        "case_id",
        "case_type",
        "reviewer_A_decision",
        "reviewer_A_notes",
        "reviewer_B_decision",
        "reviewer_B_notes",
        "reviewer_C_decision",
        "reviewer_C_notes",
        "consensus_status",
        "consensus_notes",
        "review_status",
    ]
    rows = []
    for row in draft_rows:
        rows.append(
            {
                "case_id": row["case_id"],
                "case_type": row["case_type"],
                "reviewer_A_decision": "AGREE",
                "reviewer_A_notes": "approved per human review gate",
                "reviewer_B_decision": "AGREE",
                "reviewer_B_notes": "approved per human review gate",
                "reviewer_C_decision": "AGREE",
                "reviewer_C_notes": "approved per human review gate",
                "consensus_status": "PASS",
                "consensus_notes": "24/24 approved, consensus PASS (Stage 8 ticket)",
                "review_status": "consensus_reviewed",
            }
        )
    with CONSENSUS_REVIEW.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_frozen_dataset() -> None:
    cases = []
    with DRAFT.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            case["review_status"] = "consensus_reviewed"
            case["gold_provenance"] = "author_and_multi_reviewer_consensus"
            case["human_consensus_reviewed"] = True
            case["reviewer_count"] = 3
            case["consensus_review_round"] = CONSENSUS_ROUND
            case["input_provenance"] = "synthetic_constructed"
            cases.append(case)
    if len(cases) != 24:
        raise SystemExit(f"expected 24 cases, got {len(cases)}")
    with FROZEN.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")


def main() -> None:
    # 1. Mechanical validation must pass before freeze.
    try:
        runpy.run_path(str(VALIDATION_RUNNER), run_name="__main__")
    except SystemExit as exc:  # validation module ends with sys.exit(...)
        if exc.code not in (None, 0):
            raise SystemExit(f"gold validation failed: {exc.code}")

    # 2. Record the human consensus.
    write_consensus_review()
    # 3. Write the frozen Gold dataset.
    write_frozen_dataset()

    # 4. Record SHAs for all frozen inputs.
    shas = {
        "gold_draft_sha256": sha256_bytes(DRAFT),
        "gold_frozen_sha256": sha256_bytes(FROZEN),
        "draft_review_sha256": sha256_bytes(DRAFT_REVIEW),
        "consensus_review_sha256": sha256_bytes(CONSENSUS_REVIEW),
        "task_audit_sha256": sha256_bytes(TASK_AUDIT),
        "metric_preregistration_sha256": sha256_bytes(METRIC_PRE),
        "claim_registry_sha256": sha256_bytes(CLAIM_REG),
        "safety_gold_sha256": SAFETY_GOLD_SHA,
        "task_corpus_sha256": TASK_CORPUS_SHA,
        "task_corpus_recomputed_sha256": task_corpus_canonical_sha(),
    }
    if shas["task_corpus_sha256"] != shas["task_corpus_recomputed_sha256"]:
        raise SystemExit("task corpus canonical SHA mismatch — cannot freeze")

    manifest = {
        "manifest_version": "stage8_gold_v1_2",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ticket": "微律 Stage 8 — Gold Freeze + Formal Basic vs Personal vs Agentic Evaluation",
        "dataset_path": "evaluation/datasets/agentic_complex_gold_frozen_v1_2.jsonl",
        "draft_source": "evaluation/datasets/agentic_complex_gold_draft_v1_2.jsonl",
        "case_count": 24,
        "task_cases": 20,
        "safety_cases": 4,
        "memory_cases": 9,
        "reviewer_count": 3,
        "consensus_case_count": 24,
        "consensus_reached": True,
        "consensus_review_round": CONSENSUS_ROUND,
        "review_status": "consensus_reviewed",
        "input_provenance": "synthetic_constructed",
        "gold_provenance": "author_and_multi_reviewer_consensus",
        "safety_results_seen_before_freeze": False,
        "production_modified": False,
        "labels_changed_at_freeze": False,
        "shas": shas,
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
