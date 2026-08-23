"""Stage 6G Phase B — freeze Safety Gold v1.

Reads the approved consensus draft (safety_gold_draft_v2.jsonl), enriches each
case with the consensus metadata fields required by Phase B, and writes
safety_gold_v1.jsonl. Then computes SHA-256 over the exact output bytes and
writes the v1 manifest. The gold file is NOT modified after SHA calculation.
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "evaluation" / "datasets"
MANIFESTS = ROOT / "evaluation" / "manifests"

DRAFT = DATASETS / "safety_gold_draft_v2.jsonl"
GOLD_V1 = DATASETS / "safety_gold_v1.jsonl"
MANIFEST = MANIFESTS / "safety_gold_v1_manifest.json"

TASK_CORPUS_SHA = "40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48"


def freeze() -> None:
    cases = []
    with DRAFT.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            case["review_status"] = "consensus_reviewed"
            case["gold_provenance"] = "author_and_multi_reviewer_consensus"
            case["human_consensus_reviewed"] = True
            case["reviewer_count"] = 3
            case["consensus_review_round"] = "safety_gold_consensus_v1"
            case["input_provenance"] = "synthetic_constructed"
            # preserve draft provenance if useful
            case["draft_provenance"] = "AI_assisted_draft_pending_project_review"
            cases.append(case)

    if len(cases) != 20:
        raise SystemExit(f"expected 20 cases, got {len(cases)}")

    with GOLD_V1.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case, ensure_ascii=False) + "\n")

    sha = hashlib.sha256(GOLD_V1.read_bytes()).hexdigest()
    print(f"safety_gold_sha256 = {sha}")
    print(f"case_count = {len(cases)}")

    manifest = {
        "manifest_version": "safety_gold_v1",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset_path": "evaluation/datasets/safety_gold_v1.jsonl",
        "draft_source": "evaluation/datasets/safety_gold_draft_v2.jsonl",
        "safety_gold_sha256": sha,
        "task_corpus_sha256": TASK_CORPUS_SHA,
        "case_count": len(cases),
        "reviewer_count": 3,
        "consensus_case_count": 20,
        "consensus_reached": True,
        "input_provenance": "synthetic_constructed",
        "gold_provenance": "author_and_multi_reviewer_consensus",
        "safety_results_seen_before_freeze": False,
        "production_modified": False,
        "review_status": "consensus_reviewed",
        "consensus_review_round": "safety_gold_consensus_v1",
        "reviewer_decision_required": "AGREE",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"manifest written: {MANIFEST}")


if __name__ == "__main__":
    freeze()