"""Read-only Today session listing over interaction logs.

Restores one user's same-day recommendation sessions so the Today list can
show saved tasks/actions instead of generating a fresh batch on every load.
Task display fields come from the snapshot stored with the recommendation
log; sessions created before snapshots existed fall back to the formal
micro-task metadata. Sessions whose content cannot be faithfully restored
are skipped, never guessed.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from weilv.interaction_logs import list_recommendation_logs_for_day
from weilv.micro_tasks import load_formal_micro_tasks


def list_today_sessions(client, user_id: str, day: date) -> dict[str, Any]:
    start_dt = datetime.combine(day, time.min, tzinfo=UTC)
    end_dt = start_dt + timedelta(days=1)
    logs = list_recommendation_logs_for_day(
        client,
        user_id,
        start_dt.isoformat(),
        end_dt.isoformat(),
    )
    formal = {task["task_id"]: task for task in load_formal_micro_tasks()}

    sessions = []
    for source in logs:
        task_id = source.get("selected_task_id")
        snapshot = source.get("task") or {}
        formal_task = formal.get(task_id, {})
        title = snapshot.get("title") or formal_task.get("title")
        instruction = snapshot.get("instruction") or formal_task.get("instruction")
        estimated_minutes = snapshot.get("estimated_minutes")
        if estimated_minutes is None:
            estimated_minutes = formal_task.get("estimated_minutes")
        if not task_id or not title or not instruction or estimated_minutes is None:
            continue
        sessions.append(
            {
                "recommendation_id": source.get("recommendation_id") or "",
                "task_id": task_id,
                "title": title,
                "instruction": instruction,
                "estimated_minutes": estimated_minutes,
                "covered_domains": snapshot.get("covered_domains")
                or formal_task.get("covered_domains")
                or [],
                "sources": snapshot.get("sources") or [],
                "agentic": bool(source.get("agentic")),
                "created_at": source.get("created_at") or "",
                "actions": [
                    {
                        "action": event.get("action"),
                        "recorded_at": event.get("recorded_at"),
                    }
                    for event in source.get("task_events") or []
                    if event.get("action") and event.get("recorded_at")
                ],
                "feedback": source.get("feedback"),
            }
        )
    return {"user_id": user_id, "date": day.isoformat(), "sessions": sessions}
