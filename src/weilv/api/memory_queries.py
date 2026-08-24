"""Read-only Memory list adapter over user_memory_v1.

List queries are read-only. Deletion delegates to the existing
``forget_memory()``; this module never writes or mutates Memory directly.
No second Memory write path is created here.
"""

from typing import Any

from weilv.user_memory import USER_MEMORY_INDEX

MEMORY_LIST_SIZE = 100


def query_user_memories(client, user_id: str) -> list[dict[str, Any]]:
    response = client.search(
        index=USER_MEMORY_INDEX,
        size=MEMORY_LIST_SIZE,
        query={"bool": {"filter": [{"term": {"user_id": user_id}}]}},
        sort=[{"updated_at": {"order": "desc"}}],
        source_excludes=["embedding", "retrieval_text"],
    )
    return [_memory_view(hit["_source"]) for hit in response["hits"]["hits"]]


def _memory_view(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "memory_id": source["memory_id"],
        "memory_type": source["memory_type"],
        "summary": _memory_summary(source),
        "created_at": source["created_at"],
        "updated_at": source["updated_at"],
    }


def _memory_summary(source: dict[str, Any]) -> str:
    """Deterministic user-friendly summary from approved memory fields only."""
    memory_type = source["memory_type"]
    value = source.get("memory_value") or {}
    if memory_type == "task_feedback":
        status = {
            "completed": "已完成",
            "partially_completed": "部分完成",
            "skipped": "已跳过",
        }.get(value.get("completion_status", ""), value.get("completion_status", ""))
        burden = {
            "easy": "轻松",
            "acceptable": "可接受",
            "hard": "较难",
        }.get(value.get("burden", ""), "")
        parts = [f"完成情况：{status}"]
        if burden:
            parts.append(f"负担：{burden}")
        if value.get("helpfulness") is not None:
            parts.append(f"帮助度：{value['helpfulness']}/5")
        return "，".join(parts)
    if memory_type == "task_preference":
        return "偏好此任务" if value.get("preference") == "prefer_task" else "希望避开此任务"
    if memory_type == "context_preference":
        parts = []
        if value.get("preferred_context"):
            parts.append(f"偏好环境：{value['preferred_context']}")
        if value.get("avoid_context"):
            parts.append(f"避免环境：{value['avoid_context']}")
        if value.get("school_device_unavailable"):
            parts.append("校内设备不可用")
        return "；".join(parts) or memory_type
    if memory_type == "user_constraint":
        parts = []
        if value.get("preferred_max_task_minutes") is not None:
            parts.append(f"单次任务不超过 {value['preferred_max_task_minutes']} 分钟")
        if value.get("school_device_unavailable"):
            parts.append("校内设备不可用")
        return "；".join(parts) or memory_type
    return memory_type
