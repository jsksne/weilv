"""Deterministic Stage 1 safety rules over caller-supplied structured facts."""

import json
from pathlib import Path

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "data/metadata/safety_rules_v0.1.json"
PRIORITY_ORDER = {"critical": 0, "high": 1, "normal": 2}
STATUSES = {"allowed", "blocked", "help_seeking", "no_safe_task"}
SAFETY_CAPABILITIES = {
    "pause_reading_or_screen",
    "requires_standing",
    "requires_movement",
    "requires_outdoor",
    "continue_study",
}


def load_safety_rules(path: Path = DEFAULT_RULES_PATH) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise ValueError("unsupported safety rule schema_version")
    rules = [rule for rule in payload["rules"] if rule["enabled"]]
    return sorted(rules, key=lambda rule: (PRIORITY_ORDER[rule["priority"]], rule["rule_id"]))


def _result(status: str, matches: list[tuple[str, str]]) -> dict:
    if status not in STATUSES:
        raise ValueError(f"unsupported safety status: {status}")
    return {
        "status": status,
        "matched_rule_ids": [rule_id for rule_id, _ in matches],
        "reason_codes": [reason for _, reason in matches],
    }


def _ordered(matches: list[tuple[str, str]], rules: list[dict]) -> list[tuple[str, str]]:
    positions = {rule["rule_id"]: position for position, rule in enumerate(rules)}
    return sorted(matches, key=lambda match: positions[match[0]])


def evaluate_input_risk(context: dict, rules: list[dict] | None = None) -> dict:
    rules = rules or load_safety_rules()
    matches = []
    if context.get("vision_abnormal"):
        matches.append(("SR-001", "vision_abnormal_help_seeking"))
    if context.get("physical_discomfort"):
        matches.append(("SR-002", "physical_discomfort"))
    if context.get("medical_request"):
        matches.append(("SR-003", "medical_request"))
    matches = _ordered(matches, rules)
    if any(rule_id == "SR-001" for rule_id, _ in matches):
        return _result("help_seeking", matches)
    if any(rule_id == "SR-003" for rule_id, _ in matches):
        return _result("blocked", matches)
    return _result("allowed", matches)


def filter_task_by_safety(task: dict, context: dict, rules: list[dict] | None = None) -> dict:
    rules = rules or load_safety_rules()
    matches = []
    domains = {task["domain"], *task.get("covered_domains", [])}
    capabilities = set(task.get("safety_capabilities", []))
    task_id = task["task_id"]

    if context.get("physical_discomfort") and domains & {
        "physical_activity",
        "light_recovery",
        "outdoor",
    }:
        matches.append(("SR-002", "physical_discomfort_blocks_activity"))
    if context.get("target_stage") and context["target_stage"] not in task["target_stage"]:
        matches.append(("SR-004", "target_stage_mismatch"))
    if context.get("current_context") and context["current_context"] not in task[
        "execution_contexts"
    ]:
        matches.append(("SR-005", "execution_context_mismatch"))
    if context.get("available_minutes") is not None and context["available_minutes"] < task[
        "estimated_minutes"
    ]:
        matches.append(("SR-006", "available_minutes_insufficient"))
    if task_id in context.get("matched_contraindication_task_ids", []):
        matches.append(("SR-007", "contraindication_matched"))
    if task_id in context.get("matched_stop_condition_task_ids", []):
        matches.append(("SR-008", "stop_condition_matched"))
    if context.get("cannot_move") and (
        domains & {"physical_activity", "light_recovery", "outdoor"}
        or capabilities & {"requires_standing", "requires_movement", "requires_outdoor"}
    ):
        matches.append(("SR-009", "movement_currently_unavailable"))
    if context.get("unstable_reading_or_screen") and "pause_reading_or_screen" not in capabilities:
        matches.append(("SR-010", "unstable_context_complex_task_blocked"))
    if context.get("sleep_displaced_by_study") and "continue_study" in capabilities:
        matches.append(("SR-011", "sleep_displaced_by_study"))

    matches = _ordered(matches, rules)
    return _result("blocked" if matches else "allowed", matches)


def select_safe_tasks(
    tasks: list[dict], context: dict, rules: list[dict] | None = None
) -> dict:
    rules = rules or load_safety_rules()
    input_result = evaluate_input_risk(context, rules)
    if input_result["status"] != "allowed":
        return {**input_result, "tasks": []}

    safe_tasks = []
    matches = list(zip(input_result["matched_rule_ids"], input_result["reason_codes"]))
    for task in tasks:
        task_result = filter_task_by_safety(task, context, rules)
        if task_result["status"] == "allowed":
            safe_tasks.append(task)
        else:
            matches.extend(zip(task_result["matched_rule_ids"], task_result["reason_codes"]))
    matches = _ordered(
        list({rule_id: (rule_id, reason) for rule_id, reason in matches}.values()),
        rules,
    )
    if not safe_tasks:
        matches.append(("SR-012", "no_safe_whitelist_task"))
        matches = _ordered(matches, rules)
        return {**_result("no_safe_task", matches), "tasks": []}
    return {**_result("allowed", matches), "tasks": safe_tasks}
