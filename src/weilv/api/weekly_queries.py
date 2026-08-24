"""Read-only Weekly aggregation over interaction logs and formal task metadata.

Aggregation uses only deterministic in-repo sources: interaction logs, B2 task
action events and the formal micro-task metadata (``load_formal_micro_tasks``).
No LLM, RAG, Memory or user-health inference is involved. Completed minutes
come only from official ``estimated_minutes``; missing durations are excluded,
never guessed.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any, get_args

from weilv.api.schemas import TaskAction
from weilv.interaction_logs import INTERACTION_LOG_INDEX
from weilv.micro_tasks import load_formal_micro_tasks

TASK_ACTIONS = tuple(get_args(TaskAction))
ADJUSTMENT_ACTIONS = ("replaced", "restored")
MINUTES_POLICY = "official_estimated_minutes_only"
WEEKLY_LOG_SIZE = 2000


def aggregate_weekly(client, user_id: str, start: date, end: date) -> dict[str, Any]:
    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC)

    response = client.search(
        index=INTERACTION_LOG_INDEX,
        size=WEEKLY_LOG_SIZE,
        query={"bool": {"filter": [{"term": {"user_id": user_id}}]}},
    )
    tasks = {task["task_id"]: task for task in load_formal_micro_tasks()}

    events = []
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        task_id = source.get("selected_task_id")
        for event in source.get("task_events") or []:
            action = event.get("action")
            recorded_at = event.get("recorded_at")
            if action not in TASK_ACTIONS or not recorded_at:
                continue
            try:
                event_dt = datetime.fromisoformat(recorded_at)
            except ValueError:
                continue
            if start_dt <= event_dt < end_dt:
                events.append(
                    {
                        "recommendation_id": source.get("recommendation_id"),
                        "task_id": task_id,
                        "title": tasks.get(task_id, {}).get("title"),
                        "action": action,
                        "recorded_at": recorded_at,
                        "_dt": event_dt.astimezone(UTC),
                        "_minutes": tasks.get(task_id, {}).get("estimated_minutes"),
                    }
                )

    events.sort(key=lambda event: event["_dt"])

    totals = {action: 0 for action in TASK_ACTIONS}
    total_minutes = 0
    day_count = (end - start).days + 1
    days = []
    for offset in range(day_count):
        day = start + timedelta(days=offset)
        counts = {action: 0 for action in TASK_ACTIONS}
        day_minutes = 0
        for event in events:
            if event["_dt"].date() != day:
                continue
            counts[event["action"]] += 1
            if event["action"] == "completed" and event["_minutes"] is not None:
                day_minutes += event["_minutes"]
        for action, count in counts.items():
            totals[action] += count
        total_minutes += day_minutes
        days.append(
            {
                "date": day.isoformat(),
                "completed_minutes": day_minutes,
                "action_counts": counts,
            }
        )

    visible = [
        {key: value for key, value in event.items() if not key.startswith("_")} for event in events
    ]
    return {
        "user_id": user_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "minutes_policy": MINUTES_POLICY,
        "days": days,
        "totals": {"completed_minutes": total_minutes, "action_counts": totals},
        "events": visible,
        "adjustments": [event for event in visible if event["action"] in ADJUSTMENT_ACTIONS],
    }
