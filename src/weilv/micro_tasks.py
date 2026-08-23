"""Formal MicroTask loading and retrieval text shared by promotion and indexing."""

import json
from pathlib import Path

FORMAL_TASKS_PATH = Path(__file__).resolve().parents[2] / "data/metadata/micro_tasks_v1.jsonl"


def load_formal_micro_tasks(path: Path = FORMAL_TASKS_PATH) -> list[dict]:
    tasks = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    task_ids = [task["task_id"] for task in tasks]
    if len(tasks) != 23 or len(task_ids) != len(set(task_ids)):
        raise RuntimeError("expected exactly 23 unique formal micro-tasks")
    if {task["review_status"] for task in tasks} != {"content_reviewed"}:
        raise RuntimeError("formal micro-tasks must be content_reviewed")
    return tasks


def embedding_text(task: dict) -> str:
    parts = (
        task["title"],
        task["instruction"],
        task["trigger"],
        task["domain"],
        *task["covered_domains"],
        *task["context_tags"],
        *task["execution_contexts"],
    )
    return "\n".join(parts)
