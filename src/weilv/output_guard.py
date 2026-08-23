"""Deterministic v0.1 guard for task explanation text."""

import re

MAX_EXPLANATION_LENGTH = 200
UNSUPPORTED_ACTION_TERMS = {
    "深蹲",
    "开合跳",
    "平板支撑",
    "跳绳",
    "跑步",
    "拉伸",
    "颈肩拉伸",
    "康复训练",
    "呼吸训练",
    "冥想",
    "眼部训练",
    "药物",
    "服药",
    "治疗",
    "诊断",
}
QUANTITY_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:分钟|小时|厘米|米|次|天|个)")
TASK_ID_PATTERN = re.compile(r"MT-[A-Z]+-\d{3}")


def validate_explanation_output(
    explanation: str,
    selected_task: dict,
    task_evidence: list[dict],
    formal_tasks: list[dict],
) -> dict[str, bool | list[str]]:
    reasons = []
    selected_id = selected_task["task_id"]
    other_ids = {task["task_id"] for task in formal_tasks if task["task_id"] != selected_id}
    other_titles = {
        task["title"]
        for task in formal_tasks
        if task["task_id"] != selected_id and task.get("title")
    }
    if (set(TASK_ID_PATTERN.findall(explanation)) & other_ids) or any(
        title in explanation for title in other_titles
    ):
        reasons.append("mentions_other_task")

    grounding = "\n".join(
        [selected_task.get("instruction", ""), *(item.get("content", "") for item in task_evidence)]
    )
    if any(term in explanation and term not in grounding for term in UNSUPPORTED_ACTION_TERMS):
        reasons.append("adds_unsupported_action")
    allowed_quantities = set(QUANTITY_PATTERN.findall(grounding))
    if set(QUANTITY_PATTERN.findall(explanation)) - allowed_quantities:
        reasons.append("adds_unsupported_quantity")
    if len(explanation) > MAX_EXPLANATION_LENGTH:
        reasons.append("explanation_too_long")
    return {"passed": not reasons, "reason_codes": reasons}
