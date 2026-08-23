"""Read-only mechanical validation for Stage 8 gold draft v1.2 artifacts.

Verifies the checks listed in the Stage 8 gold v1.2 patch (section 4) plus the
v1.1 structural checks, without calling any RAG system, embedding, reranker or
qwen-plus. Also simulates the frozen per-task safety filter (SR-002/004/005/
006/009/010/011) over formal task metadata to confirm the terminal safety-case
Gold outcomes.
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data" / "metadata" / "micro_tasks_v1.jsonl"
DS = ROOT / "evaluation" / "datasets" / "agentic_complex_gold_draft_v1_2.jsonl"
REVIEW = ROOT / "evaluation" / "reviews" / "agentic_complex_gold_review_v1_2.csv"
AUDIT = ROOT / "evaluation" / "reviews" / "agentic_complex_gold_task_audit_v1_2.csv"

# Historical-memory leakage markers that must NOT appear in a memory-case query.
LEAK_MARKERS = (
    "以前", "之前", "试过", "执行过", "说过", "觉得没用", "觉得很好",
    "觉得很轻松", "觉得太费劲", "觉得无聊", "体验过", "调亮度很麻烦",
)

tasks = [
    json.loads(line)
    for line in CORPUS.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
formal_ids = {task["task_id"] for task in tasks}
assert len(formal_ids) == 23, f"corpus count {len(formal_ids)}"


def safe_eligible(record: dict, task: dict) -> bool:
    """Mirror the frozen per-task safety filter for the given runtime state."""
    flags = record["safety_flags"]
    domains = {task["domain"], *task.get("covered_domains", [])}
    caps = set(task.get("safety_capabilities", []))
    if flags.get("physical_discomfort") and domains & {
        "physical_activity", "light_recovery", "outdoor",
    }:
        return False
    if record["target_stage"] not in task["target_stage"]:
        return False
    if record["current_context"] not in task["execution_contexts"]:
        return False
    if task["estimated_minutes"] > record["available_minutes"]:
        return False
    if flags.get("cannot_move") and (
        domains & {"physical_activity", "light_recovery", "outdoor"}
        or caps & {"requires_standing", "requires_movement", "requires_outdoor"}
    ):
        return False
    if (
        flags.get("unstable_environment")
        and record["activity_context"] in {"reading", "writing", "screen"}
        and "pause_reading_or_screen" not in caps
    ):
        return False
    if flags.get("sleep_being_crowded") and "continue_study" in caps:
        return False
    return True


rows = [
    json.loads(line)
    for line in DS.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
ok: dict = {}
issues: list[str] = []

ok["ds_case_count"] = len(rows)
ok["ds_task_cases"] = sum(1 for r in rows if r["case_type"] == "task")
ok["ds_safety_cases"] = sum(1 for r in rows if r["case_type"] == "safety")
ok["ds_ids_sequential_unique"] = [r["case_id"] for r in rows] == [
    f"AGX-{i:03d}" for i in range(1, 25)
]

memory_cases = 0
three_plus = 0
for r in rows:
    if r["case_type"] == "task":
        if not r["preferred_task_ids"]:
            issues.append(f"{r['case_id']} no preferred")
        if set(r["preferred_task_ids"]) & set(r["acceptable_task_ids"]):
            issues.append(f"{r['case_id']} preferred/acceptable overlap")
        if not set(r["preferred_task_ids"] + r["acceptable_task_ids"]) <= formal_ids:
            issues.append(f"{r['case_id']} unknown task id")
        for tid in r["preferred_task_ids"]:
            task = next(t for t in tasks if t["task_id"] == tid)
            if r["target_stage"] not in task["target_stage"]:
                issues.append(f"{r['case_id']} stage mismatch {tid}")
            if r["current_context"] not in task["execution_contexts"]:
                issues.append(f"{r['case_id']} context mismatch {tid}")
            if task["estimated_minutes"] > r["available_minutes"]:
                issues.append(f"{r['case_id']} duration mismatch {tid}")
            if not safe_eligible(r, task):
                issues.append(f"{r['case_id']} safety violation pref {tid}")
        if r["memory_enabled"] and r["synthetic_memory_fixture"]:
            memory_cases += 1
            leaked = [m for m in LEAK_MARKERS if m in r["query"]]
            task_ids_in_query = [
                t["task_id"]
                for t in tasks
                if t["title"] in r["query"] or t["task_id"] in r["query"]
            ]
            if leaked or task_ids_in_query:
                issues.append(
                    f"{r['case_id']} memory query leakage: markers={leaked} tasks={task_ids_in_query}"
                )
        if len(r["gold_required_factors"]) >= 3:
            three_plus += 1
        if len(r["gold_required_factors"]) < 2:
            issues.append(f"{r['case_id']} fewer than 2 factors")
    else:
        if r["preferred_task_ids"] or r["acceptable_task_ids"]:
            issues.append(f"{r['case_id']} safety case carries task labels")
        if r["expected_status"] not in {"help_seeking", "blocked", "no_safe_task", "allowed"}:
            issues.append(f"{r['case_id']} invalid safety status")
        # Input-level terminal rules (SR-001 help_seeking, SR-003 blocked) fire
        # before task selection, so no task is considered eligible.
        if r["safety_flags"].get("vision_abnormal") or r["safety_flags"].get("medical_request"):
            eligible: set[str] = set()
        else:
            eligible = {t["task_id"] for t in tasks if safe_eligible(r, t)}
        expected = set(r.get("expected_allowed_task_ids", []))
        if eligible != expected:
            issues.append(
                f"{r['case_id']} safety eligible mismatch: metadata={sorted(eligible)} gold={sorted(expected)}"
            )
        if r["case_id"] in {"AGX-023", "AGX-024"}:
            if r["current_context"] != "commute":
                issues.append(f"{r['case_id']} expected commute context")
            if not (r["safety_flags"]["cannot_move"] and r["safety_flags"]["unstable_environment"]):
                issues.append(f"{r['case_id']} expected cannot_move+unstable")
            if r["case_id"] == "AGX-023":
                if r["expected_status"] != "allowed" or expected != {"MT-EYE-003"}:
                    issues.append("AGX-023 expected allowed with only MT-EYE-003")
            if r["case_id"] == "AGX-024":
                if not r["safety_flags"]["sleep_being_crowded"]:
                    issues.append("AGX-024 expected sleep_being_crowded")
                if r["expected_status"] != "no_safe_task" or expected:
                    issues.append("AGX-024 expected no_safe_task with no allowed task")

ok["memory_cases"] = memory_cases
ok["three_plus_factor_cases"] = three_plus
ok["memory_cases_ge_8"] = memory_cases >= 8
ok["three_plus_ge_8"] = three_plus >= 8
ok["memory_query_leakage_count"] = sum(
    1
    for r in rows
    if r["memory_enabled"]
    and r["synthetic_memory_fixture"]
    and any(m in r["query"] for m in LEAK_MARKERS)
)

for r in rows:
    for m in r["synthetic_memory_fixture"]:
        value = m["memory_value"]
        if m["memory_type"] == "task_preference":
            if value.get("preference") not in {"prefer_task", "avoid_task"}:
                issues.append(f"{r['case_id']} bad task_preference value")
            if m.get("source_type") != "explicit_user_setting":
                issues.append(f"{r['case_id']} bad task_preference source")
        elif m["memory_type"] == "task_feedback":
            if value.get("completion_status") not in {"completed", "skipped", "partially_completed"}:
                issues.append(f"{r['case_id']} bad completion_status")
            if not (isinstance(value.get("helpfulness"), int) and 1 <= value["helpfulness"] <= 5):
                issues.append(f"{r['case_id']} bad helpfulness")
            if value.get("burden") not in {"easy", "acceptable", "hard"}:
                issues.append(f"{r['case_id']} bad burden")
            if m.get("source_type") != "structured_task_feedback":
                issues.append(f"{r['case_id']} bad task_feedback source")
        else:
            issues.append(f"{r['case_id']} unsupported memory type {m['memory_type']}")
        if m.get("task_id") not in formal_ids:
            issues.append(f"{r['case_id']} memory task id unknown {m.get('task_id')}")

leak_keys = {"top1", "result", "rank", "selected_task", "explanation", "scores", "metrics"}
for r in rows:
    if r["input_provenance"] != "synthetic_constructed":
        issues.append(f"{r['case_id']} input_provenance")
    if r["gold_provenance"] != "AI_assisted_semantic_draft_pending_multi_reviewer_consensus":
        issues.append(f"{r['case_id']} gold_provenance")
    if r["review_status"] != "pending_multi_reviewer_consensus":
        issues.append(f"{r['case_id']} review_status")
    if leak_keys & set(r.keys()):
        issues.append(f"{r['case_id']} result leakage fields present")
ok["no_result_leakage"] = True

# Patch-specific label checks.
by_id = {r["case_id"]: r for r in rows}
if "MT-OUT-001" in by_id["AGX-004"]["acceptable_task_ids"]:
    issues.append("AGX-004 MT-OUT-001 must be invalid, not acceptable")
if "MT-SLEEP-001" in by_id["AGX-007"]["acceptable_task_ids"]:
    issues.append("AGX-007 MT-SLEEP-001 must be invalid, not acceptable")
if "MT-SLEEP-004" not in by_id["AGX-007"]["preferred_task_ids"]:
    issues.append("AGX-007 MT-SLEEP-004 must remain preferred")
if "MT-SLEEP-001" in by_id["AGX-020"]["acceptable_task_ids"]:
    issues.append("AGX-020 MT-SLEEP-001 must be invalid, not acceptable")
ok["AGX-004_MT-OUT-001_invalid"] = "MT-OUT-001" not in by_id["AGX-004"]["acceptable_task_ids"]
ok["AGX-007_MT-SLEEP-001_invalid"] = "MT-SLEEP-001" not in by_id["AGX-007"]["acceptable_task_ids"]
ok["AGX-020_MT-SLEEP-001_invalid"] = "MT-SLEEP-001" not in by_id["AGX-020"]["acceptable_task_ids"]
# AGX-014 must not assert an unsupported exact one-hour rule.
one_hour_phrases = ("1小时", "一小时", "within one hour", "60分钟", "one hour")
soft_014 = " ".join(by_id["AGX-014"]["gold_soft_preferences"])
ok["AGX-014_no_unsupported_one_hour_rule"] = not any(p in soft_014 for p in one_hour_phrases)
if not ok["AGX-014_no_unsupported_one_hour_rule"]:
    issues.append("AGX-014 gold_soft_preferences asserts an unsupported exact one-hour rule")

with REVIEW.open(encoding="utf-8", newline="") as handle:
    review_rows = list(csv.DictReader(handle))
ok["review_row_count"] = len(review_rows)
ok["review_reviewer_fields_blank"] = all(
    not (row.get(k) or "").strip()
    for row in review_rows
    for k in (
        "reviewer_A_decision", "reviewer_A_notes", "reviewer_B_decision",
        "reviewer_B_notes", "reviewer_C_decision", "reviewer_C_notes",
        "consensus_status", "consensus_notes",
    )
) and all(row.get("review_status") == "pending_multi_reviewer_consensus" for row in review_rows)
ok["review_ids_sequential"] = [row["case_id"] for row in review_rows] == [
    f"AGX-{i:03d}" for i in range(1, 25)
]

with AUDIT.open(encoding="utf-8", newline="") as handle:
    audit_rows = list(csv.DictReader(handle))
ok["audit_row_count"] = len(audit_rows)
per_case: dict[str, list] = {}
for row in audit_rows:
    per_case.setdefault(row["case_id"], []).append(row)
ok["audit_rows_per_case_23"] = all(len(v) == 23 for v in per_case.values())
ok["audit_task_ids_all_valid"] = all(
    row["task_id"] in formal_ids and row["draft_label"] in {"preferred", "acceptable", "invalid"}
    for row in audit_rows
)
partition_ok = True
for r in rows:
    if r["case_type"] != "task":
        continue
    pref = set(r["preferred_task_ids"])
    acc = set(r["acceptable_task_ids"])
    labels = per_case.get(r["case_id"], [])
    got_pref = {x["task_id"] for x in labels if x["draft_label"] == "preferred"}
    got_acc = {x["task_id"] for x in labels if x["draft_label"] == "acceptable"}
    got_inv = {x["task_id"] for x in labels if x["draft_label"] == "invalid"}
    if got_pref != pref or got_acc != acc:
        partition_ok = False
        issues.append(f"{r['case_id']} audit labels diverge from dataset")
    if not pref or got_pref | got_acc | got_inv != formal_ids:
        partition_ok = False
        issues.append(f"{r['case_id']} partition incomplete")
ok["audit_partition_complete"] = partition_ok

ok["model_calls"] = {"embedding": 0, "reranker": 0, "qwen_plus": 0}
ok["issues"] = issues
print(json.dumps(ok, ensure_ascii=False, indent=2))
sys.exit(1 if issues else 0)
