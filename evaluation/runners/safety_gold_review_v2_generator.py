"""Stage 6F-E: regenerate safety gold v2 review CSVs from the draft JSONL.

Reviewer decision fields are intentionally left EMPTY; no consensus is marked.
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEWERS = [
    "reviewer_A_decision", "reviewer_A_notes",
    "reviewer_B_decision", "reviewer_B_notes",
    "reviewer_C_decision", "reviewer_C_notes",
    "consensus_status", "consensus_notes",
]

cases = [
    json.loads(line)
    for line in (ROOT / "evaluation/datasets/safety_gold_draft_v2.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
]

rows = [
    {
        "case_id": c["case_id"],
        "rule_ids": ";".join(c["rule_ids"]),
        "case_type": c["case_type"],
        "scenario": c["query"],
        "target_stage": c["target_stage"],
        "current_context": c["current_context"],
        "activity_context": c["activity_context"],
        "available_minutes": c["available_minutes"],
        "safety_flags": json.dumps(c["safety_flags"], ensure_ascii=False),
        "expected_decision": c["expected_decision"],
        "expected_no_task": c["expected_no_task"],
        "expected_help_or_escalation": c["expected_help_or_escalation"],
        "expected_allowed_task_ids": json.dumps(c["expected_allowed_task_ids"], ensure_ascii=False),
        "expected_blocked_task_ids": json.dumps(c["expected_blocked_task_ids"], ensure_ascii=False),
        "gold_basis": c["gold_basis"],
        "input_provenance": c["input_provenance"],
        "gold_provenance": c["gold_provenance"],
        "review_status": c["review_status"],
    }
    for c in cases
]
with (ROOT / "evaluation/reviews/safety_gold_review_v2.csv").open(
    "w", encoding="utf-8-sig", newline=""
) as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]) + REVIEWERS)
    writer.writeheader()
    writer.writerows(rows)

crows = [
    {
        "case_id": c["case_id"],
        "rule_ids": ";".join(c["rule_ids"]),
        "scenario": c["query"],
        "expected_decision": c["expected_decision"],
        "expected_allowed_summary": (
            f"allowed={len(c['expected_allowed_task_ids'])} task_ids={c['expected_allowed_task_ids']}"
        ),
        "expected_blocked_summary": (
            f"blocked={len(c['expected_blocked_task_ids'])} task_ids={c['expected_blocked_task_ids']}"
        ),
        "draft_basis": c["gold_basis"],
    }
    for c in cases
]
with (ROOT / "evaluation/reviews/safety_gold_consensus_review_v2.csv").open(
    "w", encoding="utf-8-sig", newline=""
) as handle:
    writer = csv.DictWriter(handle, fieldnames=list(crows[0]) + REVIEWERS)
    writer.writeheader()
    writer.writerows(crows)

print("review rows", len(rows), "consensus rows", len(crows))
