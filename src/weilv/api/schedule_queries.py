"""User schedule events (spec: 日程最小实现).

Each record is one dated event (exam / holiday / plan) with an optional
busy level. Names are user data: stored verbatim but never indexed and
never forwarded to any model prompt — only structured kind/busy_level
facts reach the recommendation path. No timezones, no recurrence, no
external calendar connections.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from elasticsearch import NotFoundError

SCHEDULE_INDEX = "user_schedule_v1"
SCHEDULE_LIST_SIZE = 100


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def create_schedule_event(client, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    now = _now_iso()
    event_id = str(uuid4())
    document = {
        "event_id": event_id,
        "user_id": user_id,
        "name": payload["name"],
        "start_date": payload["start_date"].isoformat(),
        "end_date": payload["end_date"].isoformat(),
        "kind": payload["kind"],
        "busy_level": payload.get("busy_level"),
        "created_at": now,
        "updated_at": now,
    }
    client.create(index=SCHEDULE_INDEX, id=event_id, document=document)
    return document


def update_schedule_event(
    client, user_id: str, event_id: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    existing = get_schedule_event(client, user_id, event_id)
    if existing is None:
        return None
    updated = {
        "name": payload["name"],
        "start_date": payload["start_date"].isoformat(),
        "end_date": payload["end_date"].isoformat(),
        "kind": payload["kind"],
        "busy_level": payload.get("busy_level"),
        "updated_at": _now_iso(),
    }
    client.update(index=SCHEDULE_INDEX, id=event_id, doc=updated, refresh="wait_for")
    return {**existing, **updated}


def delete_schedule_event(client, user_id: str, event_id: str) -> bool:
    existing = get_schedule_event(client, user_id, event_id)
    if existing is None:
        return False
    client.delete(index=SCHEDULE_INDEX, id=event_id, refresh="wait_for")
    return True


def get_schedule_event(client, user_id: str, event_id: str) -> dict[str, Any] | None:
    try:
        source = client.get(index=SCHEDULE_INDEX, id=event_id)["_source"]
    except NotFoundError:
        return None
    if source.get("user_id") != user_id:
        return None
    return source


def list_schedule_events(
    client,
    user_id: str,
    overlap_start: date,
    overlap_end: date,
) -> list[dict[str, Any]]:
    """Events overlapping [overlap_start, overlap_end] (inclusive, date-only)."""
    response = client.search(
        index=SCHEDULE_INDEX,
        size=SCHEDULE_LIST_SIZE,
        query={
            "bool": {
                "filter": [
                    {"term": {"user_id": user_id}},
                    {"range": {"start_date": {"lte": overlap_end.isoformat()}}},
                    {"range": {"end_date": {"gte": overlap_start.isoformat()}}},
                ]
            }
        },
        sort=[{"start_date": {"order": "asc"}}],
    )
    return [hit["_source"] for hit in response["hits"]["hits"]]


def schedule_facts_for_day(client, user_id: str, day: date) -> list[dict[str, str]]:
    """Structured facts for one day; names deliberately excluded."""
    events = list_schedule_events(client, user_id, day, day)
    facts = []
    for event in events:
        fact: dict[str, str] = {"kind": event.get("kind", "plan")}
        if event.get("busy_level"):
            fact["busy_level"] = event["busy_level"]
        facts.append(fact)
    return facts
