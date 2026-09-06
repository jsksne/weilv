"""Stage 4 v0.1 user-memory contracts and deterministic validation."""

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any

from elasticsearch import ConflictError, NotFoundError

USER_PROFILE_INDEX = "user_profiles_v1"
USER_MEMORY_INDEX = "user_memory_v1"

MEMORY_TYPES = {
    "task_feedback",
    "task_preference",
    "context_preference",
    "user_constraint",
}
SOURCE_TYPES = {
    "explicit_user_setting",
    "structured_task_feedback",
    "questionnaire_cold_start",
}
FORBIDDEN_PERSISTENCE_FIELDS = {
    "vision_abnormal",
    "physical_discomfort",
    "medical_request",
    "unstable_environment",
    "sleep_being_crowded",
    "diagnosis",
    "disease",
    "medication",
    "treatment_record",
    "height",
    "weight",
    "mental_health_detail",
    "medical_history",
    "query",
    "raw_query",
    "chat_text",
    "raw_chat",
}

COMPLETION_STATUSES = {"completed", "skipped", "partially_completed"}
BURDEN_LEVELS = {"easy", "acceptable", "hard"}
TARGET_STAGES = {"primary_upper", "junior_high", "senior_high"}
CONTEXT_VALUES = {"home", "school", "study_space", "commute", "bedroom", "outdoor"}
MEMORY_VALUE_FIELDS = {
    "task_feedback": {"completion_status", "helpfulness", "burden", "confidence"},
    "task_preference": {"preference"},
    "context_preference": {
        "preferred_context",
        "avoid_context",
        "school_device_unavailable",
    },
    "user_constraint": {"preferred_max_task_minutes", "school_device_unavailable"},
}


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    target_stage: str
    memory_enabled: bool
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if self.target_stage not in TARGET_STAGES:
            raise ValueError("unsupported target_stage")


@dataclass(frozen=True)
class UserMemoryCandidate:
    memory_id: str
    user_id: str
    memory_type: str
    source_type: str
    task_id: str | None
    domain: str | None
    memory_key: str
    memory_value: dict[str, Any]
    created_at: str
    updated_at: str
    retrieval_text: str = ""
    active: bool = True
    review_status: str = "valid"
    embedding: list[float] = field(default_factory=list)


def _contains_forbidden_field(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(FORBIDDEN_PERSISTENCE_FIELDS & value.keys()) or any(
            _contains_forbidden_field(item) for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_field(item) for item in value)
    return False


def _validate_memory_value(memory_type: str, value: dict[str, Any]) -> list[str]:
    if set(value) - MEMORY_VALUE_FIELDS[memory_type]:
        return ["memory_value_field_not_allowed"]
    if memory_type == "task_feedback":
        reasons = []
        if value.get("completion_status") not in COMPLETION_STATUSES:
            reasons.append("invalid_completion_status")
        helpfulness = value.get("helpfulness")
        if type(helpfulness) is not int or not 1 <= helpfulness <= 5:
            reasons.append("invalid_helpfulness")
        if value.get("burden") not in BURDEN_LEVELS:
            reasons.append("invalid_burden")
        confidence = value.get("confidence")
        if confidence is not None and (type(confidence) is not int or not 1 <= confidence <= 10):
            reasons.append("invalid_confidence")
        return reasons
    if memory_type == "task_preference":
        return [] if value.get("preference") in {"prefer_task", "avoid_task"} else [
            "invalid_task_preference"
        ]
    if not value:
        return ["invalid_memory_value"]
    if memory_type == "context_preference":
        for key in ("preferred_context", "avoid_context"):
            if key in value and value[key] not in CONTEXT_VALUES:
                return ["invalid_context_preference"]
        if "school_device_unavailable" in value and type(
            value["school_device_unavailable"]
        ) is not bool:
            return ["invalid_school_device_unavailable"]
        return []
    if "preferred_max_task_minutes" in value:
        minutes = value["preferred_max_task_minutes"]
        if type(minutes) is not int or not 1 <= minutes <= 60:
            return ["invalid_preferred_max_task_minutes"]
    if "school_device_unavailable" in value and type(
        value["school_device_unavailable"]
    ) is not bool:
        return ["invalid_school_device_unavailable"]
    return []


def validate_memory_candidate(
    profile: UserProfile,
    candidate: UserMemoryCandidate,
    allowed_task_ids: set[str],
) -> dict[str, bool | list[str]]:
    """Apply the v0.1 persistence gate without storage or model calls."""

    if not profile.memory_enabled:
        return {"valid": False, "reason_codes": ["memory_disabled"]}
    if candidate.source_type not in SOURCE_TYPES:
        return {"valid": False, "reason_codes": ["source_type_not_allowed"]}
    if candidate.memory_type not in MEMORY_TYPES:
        return {"valid": False, "reason_codes": ["memory_type_not_allowed"]}
    if _contains_forbidden_field(candidate.memory_value):
        return {"valid": False, "reason_codes": ["forbidden_persistence_field"]}

    reasons = []
    if candidate.user_id != profile.user_id:
        reasons.append("user_id_mismatch")

    expected_source = (
        "structured_task_feedback"
        if candidate.memory_type == "task_feedback"
        else "explicit_user_setting"
    )
    if candidate.source_type == "questionnaire_cold_start":
        # Questionnaire-initiated preferences are explicit settings, but never
        # behavioral feedback: only non-task_feedback memory types qualify.
        if candidate.memory_type == "task_feedback":
            reasons.append("source_type_mismatch")
    elif candidate.source_type in SOURCE_TYPES and candidate.source_type != expected_source:
        reasons.append("source_type_mismatch")

    if candidate.memory_type in {"task_feedback", "task_preference"} and (
        not candidate.task_id or candidate.task_id not in allowed_task_ids
    ):
        reasons.append("task_id_not_allowed")

    reasons.extend(_validate_memory_value(candidate.memory_type, candidate.memory_value))

    return {"valid": not reasons, "reason_codes": reasons}


def build_retrieval_text(candidate: UserMemoryCandidate) -> str:
    """Build stable retrieval text solely from approved structured fields."""

    if _contains_forbidden_field(candidate.memory_value):
        raise ValueError("forbidden persistence field")
    if candidate.memory_type not in MEMORY_TYPES:
        raise ValueError("unsupported memory type")
    reasons = _validate_memory_value(candidate.memory_type, candidate.memory_value)
    if reasons:
        raise ValueError(reasons[0])

    lines = [f"type={candidate.memory_type}"]
    if candidate.task_id:
        lines.append(f"task={candidate.task_id}")

    if candidate.memory_type == "task_feedback":
        value = candidate.memory_value
        lines.extend(
            [
                f"completion={value.get('completion_status', '')}",
                f"burden={value.get('burden', '')}",
                f"helpfulness={value.get('helpfulness', '')}",
            ]
        )
    else:
        lines.append(f"key={candidate.memory_key}")
        value = json.dumps(
            candidate.memory_value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        lines.append(f"value={value}")

    return "\n".join(lines)


def build_memory_id(candidate: UserMemoryCandidate) -> str:
    """Return the stable identifier for one current personalization state."""

    identity_key = (
        candidate.task_id
        if candidate.memory_type in {"task_feedback", "task_preference"}
        else candidate.memory_key
    )
    identity = json.dumps(
        [candidate.user_id, candidate.memory_type, identity_key],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"UM-{sha256(identity.encode('utf-8')).hexdigest()}"


def upsert_user_profile(client, profile: UserProfile) -> dict[str, str]:
    client.index(index=USER_PROFILE_INDEX, id=profile.user_id, document=asdict(profile))
    return {"status": "updated", "user_id": profile.user_id}


def get_user_profile(client, user_id: str) -> UserProfile | None:
    try:
        source = client.get(index=USER_PROFILE_INDEX, id=user_id)["_source"]
    except NotFoundError:
        return None
    return UserProfile(**source)


def _memory_document(
    candidate: UserMemoryCandidate,
    memory_id: str,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    document = asdict(candidate)
    document.update(
        memory_id=memory_id,
        retrieval_text=build_retrieval_text(candidate),
        created_at=created_at or candidate.created_at,
        active=True,
        review_status="valid",
        embedding=[],
    )
    return document


def _persistable_memory_document(document: dict[str, Any]) -> dict[str, Any]:
    """Omit an empty vector because Elasticsearch dense_vector rejects []."""

    if document["embedding"]:
        return document
    return {key: value for key, value in document.items() if key != "embedding"}


def create_memory(
    client,
    profile: UserProfile,
    candidate: UserMemoryCandidate,
    valid_task_ids: set[str],
) -> dict[str, str]:
    validation = validate_memory_candidate(profile, candidate, valid_task_ids)
    if not validation["valid"]:
        return {"status": "rejected", "reason_code": validation["reason_codes"][0]}

    memory_id = build_memory_id(candidate)
    try:
        client.create(
            index=USER_MEMORY_INDEX,
            id=memory_id,
            document=_persistable_memory_document(_memory_document(candidate, memory_id)),
            refresh="wait_for",
        )
    except ConflictError:
        return {"status": "already_exists", "memory_id": memory_id}
    return {"status": "created", "memory_id": memory_id}


def _get_memory_source(client, memory_id: str) -> dict[str, Any] | None:
    try:
        return client.get(index=USER_MEMORY_INDEX, id=memory_id)["_source"]
    except NotFoundError:
        return None


def get_memory(client, user_id: str, memory_id: str) -> dict[str, Any] | None:
    source = _get_memory_source(client, memory_id)
    if source is None or source["user_id"] != user_id:
        return None
    source.setdefault("embedding", [])
    return source


def update_memory(
    client,
    profile: UserProfile,
    candidate: UserMemoryCandidate,
    valid_task_ids: set[str],
) -> dict[str, str]:
    memory_id = candidate.memory_id
    validation = validate_memory_candidate(profile, candidate, valid_task_ids)
    if not validation["valid"]:
        return {
            "status": "rejected",
            "memory_id": memory_id,
            "reason_code": validation["reason_codes"][0],
        }

    existing = _get_memory_source(client, memory_id)
    if existing is None:
        return {"status": "not_found", "memory_id": memory_id}
    if existing["user_id"] != profile.user_id:
        return {
            "status": "rejected",
            "memory_id": memory_id,
            "reason_code": "memory_owner_mismatch",
        }
    if build_memory_id(candidate) != memory_id:
        return {
            "status": "rejected",
            "memory_id": memory_id,
            "reason_code": "memory_identity_mismatch",
        }

    client.index(
        index=USER_MEMORY_INDEX,
        id=memory_id,
        document=_persistable_memory_document(
            _memory_document(candidate, memory_id, created_at=existing["created_at"])
        ),
        refresh="wait_for",
    )
    return {"status": "updated", "memory_id": memory_id}


MEMORY_HISTORY_SIZE = 200


def list_active_memories(client, user_id: str) -> list[dict[str, Any]]:
    """All active, valid memories for one user, newest update first.

    Personalization scoring must consider every structured memory - not only
    the semantic-retrieval top-K - because a memory that ranks low against
    the current query can still legitimately change a task's order.
    """
    response = client.search(
        index=USER_MEMORY_INDEX,
        size=MEMORY_HISTORY_SIZE,
        query={
            "bool": {
                "filter": [
                    {"term": {"user_id": user_id}},
                    {"term": {"active": True}},
                    {"term": {"review_status": "valid"}},
                ]
            }
        },
        sort=[{"updated_at": {"order": "desc"}}],
    )
    return [hit["_source"] for hit in response["hits"]["hits"]]


def forget_memory(client, user_id: str, memory_id: str) -> dict[str, str]:
    existing = _get_memory_source(client, memory_id)
    if existing is None:
        return {"status": "not_found", "memory_id": memory_id}
    if existing["user_id"] != user_id:
        return {
            "status": "rejected",
            "memory_id": memory_id,
            "reason_code": "memory_owner_mismatch",
        }

    client.delete(index=USER_MEMORY_INDEX, id=memory_id, refresh="wait_for")
    return {"status": "forgotten", "memory_id": memory_id}
