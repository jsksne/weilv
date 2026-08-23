"""Stage 10B feedback loop: feedback -> structured task_feedback memory.

The feedback loop writes only into the existing User Memory system through the
frozen persistence gate.  It never fabricates preference records, never touches
Safety / Evidence / Output Guard, and never changes the Personal RAG ranking
weights: usefulness and difficulty are mapped onto the fields the frozen
ranking already reads (helpfulness, burden), and accumulated confidence rides
along as metadata on the single per-task task_feedback document.
"""

from typing import Any

from elasticsearch import NotFoundError

from weilv.user_memory import (
    USER_MEMORY_INDEX,
    UserMemoryCandidate,
    build_memory_id,
)

USEFULNESS_VALUES = {"helpful", "neutral", "not_helpful"}
DIFFICULTY_VALUES = {"easy", "suitable", "difficult"}
CONFIDENCE_MIN = 1
CONFIDENCE_MAX = 10

_HELPFULNESS_BY_USEFULNESS = {"helpful": 5, "neutral": 3, "not_helpful": 2}
_BURDEN_BY_DIFFICULTY = {"easy": "easy", "suitable": "acceptable", "difficult": "hard"}


def map_usefulness(usefulness: str) -> int:
    """Map the 3-level usefulness onto the frozen 1..5 helpfulness field."""
    if usefulness not in USEFULNESS_VALUES:
        raise ValueError("invalid usefulness")
    return _HELPFULNESS_BY_USEFULNESS[usefulness]


def map_difficulty(difficulty: str) -> str:
    """Map the 3-level difficulty onto the frozen burden field."""
    if difficulty not in DIFFICULTY_VALUES:
        raise ValueError("invalid difficulty")
    return _BURDEN_BY_DIFFICULTY[difficulty]


def _polarity(usefulness: str) -> int:
    if usefulness == "helpful":
        return 1
    if usefulness == "not_helpful":
        return -1
    return 0


def _previous_polarity(previous_value: dict[str, Any] | None) -> int:
    helpfulness = previous_value.get("helpfulness") if previous_value else None
    if isinstance(helpfulness, int) and helpfulness >= 4:
        return 1
    if isinstance(helpfulness, int) and helpfulness <= 2:
        return -1
    return 0


def compute_confidence(
    previous_value: dict[str, Any] | None,
    usefulness: str,
) -> int:
    """Confidence accumulation: 1 on first feedback, +1 on repeated consistent
    feedback (capped at 10), -1 on contradictory feedback (floored at 1), and
    unchanged when either signal is neutral."""
    if usefulness not in USEFULNESS_VALUES:
        raise ValueError("invalid usefulness")
    if not previous_value:
        return CONFIDENCE_MIN
    confidence = previous_value.get("confidence")
    if not isinstance(confidence, int) or not CONFIDENCE_MIN <= confidence <= CONFIDENCE_MAX:
        confidence = CONFIDENCE_MIN
    new_polarity = _polarity(usefulness)
    if new_polarity == 0 or _previous_polarity(previous_value) == 0:
        return confidence
    if new_polarity == _previous_polarity(previous_value):
        return min(confidence + 1, CONFIDENCE_MAX)
    return max(confidence - 1, CONFIDENCE_MIN)


def build_feedback_memory_value(
    completion_status: str,
    usefulness: str,
    difficulty: str,
    confidence: int,
) -> dict[str, Any]:
    return {
        "completion_status": completion_status,
        "helpfulness": map_usefulness(usefulness),
        "burden": map_difficulty(difficulty),
        "confidence": confidence,
    }


def get_feedback_memory_value(
    client, user_id: str, task_id: str
) -> dict[str, Any] | None:
    probe = UserMemoryCandidate(
        memory_id="",
        user_id=user_id,
        memory_type="task_feedback",
        source_type="structured_task_feedback",
        task_id=task_id,
        domain=None,
        memory_key="task_feedback",
        memory_value={},
        created_at="",
        updated_at="",
    )
    memory_id = build_memory_id(probe)
    try:
        source = client.get(index=USER_MEMORY_INDEX, id=memory_id)["_source"]
    except NotFoundError:
        return None
    if source.get("user_id") != user_id:
        return None
    return source.get("memory_value")


def build_feedback_memory_candidate(
    user_id: str,
    task_id: str,
    feedback: dict[str, Any],
    confidence: int,
    now: str,
) -> UserMemoryCandidate:
    return UserMemoryCandidate(
        memory_id="",
        user_id=user_id,
        memory_type="task_feedback",
        source_type="structured_task_feedback",
        task_id=task_id,
        domain=None,
        memory_key="task_feedback",
        memory_value=build_feedback_memory_value(
            feedback["completion_status"],
            feedback["usefulness"],
            feedback["difficulty"],
            confidence,
        ),
        created_at=now,
        updated_at=now,
    )
