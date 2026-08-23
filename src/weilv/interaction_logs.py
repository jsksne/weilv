"""Minimal recommendation-session persistence in interaction_logs_v1."""

from typing import Any

from elasticsearch import NotFoundError

INTERACTION_LOG_INDEX = "interaction_logs_v1"


def create_recommendation_log(client, session: dict[str, Any]) -> None:
    client.create(
        index=INTERACTION_LOG_INDEX,
        id=session["recommendation_id"],
        document=session,
    )


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
