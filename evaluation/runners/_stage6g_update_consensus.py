"""Stage 6G Phase A — record human consensus on Safety Gold v2 draft.

Uses csv.DictReader/DictWriter to preserve quoting. Reviewer fields set to AGREE;
notes blank; consensus_status=CONSENSUS_REACHED.

Gold labels are sourced from the canonical JSONL draft and NOT altered.
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / "evaluation" / "reviews"
DATASETS = ROOT / "evaluation" / "datasets"


def rebuild_consensus_csv(jsonl_path: Path, csv_path: Path) -> None:
    rows = []
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            rule_ids = case.get("rule_ids") or []
            rule_field = ";".join(rule_ids) if isinstance(rule_ids, list) else str(rule_ids)
            allowed = case.get("expected_allowed_task_ids", []) or []
            blocked = case.get("expected_blocked_task_ids", []) or []
            allowed_summary = f"allowed={len(allowed)} task_ids={allowed!r}"
            blocked_summary = f"blocked={len(blocked)} task_ids={blocked!r}"
            rows.append({
                "case_id": case["case_id"],
                "rule_ids": rule_field,
                "scenario": case["query"],
                "expected_decision": case["expected_decision"],
                "expected_allowed_summary": allowed_summary,
                "expected_blocked_summary": blocked_summary,
                "draft_basis": case["gold_basis"],
                "reviewer_A_decision": "AGREE",
                "reviewer_A_notes": "",
                "reviewer_B_decision": "AGREE",
                "reviewer_B_notes": "",
                "reviewer_C_decision": "AGREE",
                "reviewer_C_notes": "",
                "consensus_status": "CONSENSUS_REACHED",
                "consensus_notes": "",
            })

    fields = [
        "case_id", "rule_ids", "scenario", "expected_decision",
        "expected_allowed_summary", "expected_blocked_summary",
        "draft_basis",
        "reviewer_A_decision", "reviewer_A_notes",
        "reviewer_B_decision", "reviewer_B_notes",
        "reviewer_C_decision", "reviewer_C_notes",
        "consensus_status", "consensus_notes",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)


def rebuild_full_review_csv(jsonl_path: Path, csv_path: Path) -> None:
    rows = []
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            rule_ids = case.get("rule_ids") or []
            rule_field = ";".join(rule_ids) if isinstance(rule_ids, list) else str(rule_ids)
            safety_flags = case.get("safety_flags", {}) or {}
            rows.append({
                "case_id": case["case_id"],
                "rule_ids": rule_field,
                "case_type": case["case_type"],
                "scenario": case["query"],
                "target_stage": case["target_stage"],
                "current_context": case["current_context"],
                "activity_context": case["activity_context"],
                "available_minutes": case["available_minutes"],
                "safety_flags": json.dumps(safety_flags, ensure_ascii=False),
                "expected_decision": case["expected_decision"],
                "expected_no_task": "True" if case["expected_no_task"] else "False",
                "expected_help_or_escalation": "True" if case["expected_help_or_escalation"] else "False",
                "expected_allowed_task_ids": case["expected_allowed_task_ids"],
                "expected_blocked_task_ids": case["expected_blocked_task_ids"],
                "gold_basis": case["gold_basis"],
                "input_provenance": case["input_provenance"],
                "gold_provenance": case["gold_provenance"],
                "review_status": "consensus_reviewed",
                "reviewer_A_decision": "AGREE",
                "reviewer_A_notes": "",
                "reviewer_B_decision": "AGREE",
                "reviewer_B_notes": "",
                "reviewer_C_decision": "AGREE",
                "reviewer_C_notes": "",
                "consensus_status": "CONSENSUS_REACHED",
                "consensus_notes": "",
            })

    fields = [
        "case_id", "rule_ids", "case_type", "scenario",
        "target_stage", "current_context", "activity_context", "available_minutes",
        "safety_flags", "expected_decision", "expected_no_task", "expected_help_or_escalation",
        "expected_allowed_task_ids", "expected_blocked_task_ids", "gold_basis",
        "input_provenance", "gold_provenance", "review_status",
        "reviewer_A_decision", "reviewer_A_notes",
        "reviewer_B_decision", "reviewer_B_notes",
        "reviewer_C_decision", "reviewer_C_notes",
        "consensus_status", "consensus_notes",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    jsonl = DATASETS / "safety_gold_draft_v2.jsonl"
    rebuild_consensus_csv(jsonl, REVIEWS / "safety_gold_consensus_review_v2.csv")
    rebuild_full_review_csv(jsonl, REVIEWS / "safety_gold_review_v2.csv")
    print("OK: consensus CSVs rebuilt from canonical draft v2 with 20 AGREE/AGREE/AGREE rows.")