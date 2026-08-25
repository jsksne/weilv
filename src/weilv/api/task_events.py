"""Task action event recording on the existing interaction log.

Task action events faithfully record user actions (started, completed,
partially_completed, skipped, replaced, restored). They are NOT Feedback:
they carry no usefulness / difficulty / reason, and they never produce Memory.
"""

from typing import Any

from weilv.interaction_logs import INTERACTION_LOG_INDEX


def append_task_event(client, session: dict[str, Any], event: dict[str, Any]) -> None:
    """Append one action event to the recommendation's interaction log."""
    events = list(session.get("task_events") or []) + [event]
    client.update(
        index=INTERACTION_LOG_INDEX,
        id=session["recommendation_id"],
        doc={"task_events": events},
        refresh="wait_for",
    )
