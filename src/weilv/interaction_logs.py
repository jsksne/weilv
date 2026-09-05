"""Minimal recommendation-session persistence in interaction_logs_v1."""

from typing import Any

from elasticsearch import NotFoundError

INTERACTION_LOG_INDEX = "interaction_logs_v1"

TODAY_LOG_SIZE = 50


def create_recommendation_log(client, session: dict[str, Any]) -> None:
    client.create(
        index=INTERACTION_LOG_INDEX,
        id=session["recommendation_id"],
        document=session,
    )


def list_recommendation_logs_for_day(
    client, user_id: str, start_at: str, end_at: str
) -> list[dict[str, Any]]:
    """List one user's recommendation sessions created in [start_at, end_at)."""
    response = client.search(
        index=INTERACTION_LOG_INDEX,
        size=TODAY_LOG_SIZE,
        query={
            "bool": {
                "filter": [
                    {"term": {"user_id": user_id}},
                    {"range": {"created_at": {"gte": start_at, "lt": end_at}}},
                ]
            }
        },
        sort=[{"created_at": {"order": "asc"}}],
    )
    return [hit["_source"] for hit in response["hits"]["hits"]]


def get_recommendation_log(
    client, user_id: str, recommendation_id: str
) -> dict[str, Any] | None:
    try:
        source = client.get(index=INTERACTION_LOG_INDEX, id=recommendation_id)["_source"]
    except NotFoundError:
        return None
    if source.get("user_id") != user_id:
        return None
    return source


def update_recommendation_feedback(
    client,
    recommendation_id: str,
    feedback: dict[str, Any],
    feedback_updated_at: str,
    memory_persisted: bool,
) -> None:
    client.update(
        index=INTERACTION_LOG_INDEX,
        id=recommendation_id,
        doc={
            "feedback": feedback,
            "feedback_updated_at": feedback_updated_at,
            "memory_persisted": memory_persisted,
        },
    )
