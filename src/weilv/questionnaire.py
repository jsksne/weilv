"""Stage 10A cold-start questionnaire: schema, memory mapping, and persistence.

The questionnaire initializes the existing User Memory system only. It never
creates a second personalization engine, never fabricates task_feedback
history, and never changes the Safety / Evidence / Output Guard contracts.
Every generated memory is stamped ``source_type="questionnaire_cold_start"``
so it can be told apart from later behavioral feedback.
"""

from dataclasses import asdict
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from elasticsearch import ApiError, NotFoundError

from weilv.micro_tasks import load_formal_micro_tasks
from weilv.personal_memory_retrieval import embed_memory
from weilv.user_memory import (
    UserMemoryCandidate,
    UserProfile,
    build_memory_id,
    create_memory,
    get_user_profile,
    update_memory,
)

QUESTIONNAIRE_VERSION = "v1"
QUESTIONNAIRE_INDEX = "user_questionnaire_v1"
QUESTIONNAIRE_SOURCE = "questionnaire_cold_start"

COMPLETION_STATES = {"not_started", "partially_completed", "completed", "skipped"}

# question_id -> mapping from answer value to generated memory instructions.
# task_preference entries are (preference, (task_id, ...)) with task_ids from
# the formal 23-task corpus only; context/user_constraint entries are
# (memory_type, memory_value).
_REST_PREFERENCE: dict[str, tuple[tuple[str, object], ...]] = {
    "quiet_rest": (("prefer_task", ("MT-BREAK-003",)),),
    "far_view": (("prefer_task", ("MT-BREAK-001", "MT-BREAK-002")),),
    "light_activity": (("prefer_task", ("MT-REC-001", "MT-REC-002")),),
    "outdoor": (("prefer_task", ("MT-OUT-001",)),),
    "depends": (),
}

_ANNOYING_REMINDERS: dict[str, tuple[tuple[str, object], ...]] = {
    "activity": (
        (
            "avoid_task",
            ("MT-REC-001", "MT-REC-002", "MT-SED-001", "MT-SED-002", "MT-BREAK-004"),
        ),
    ),
    "stop_phone": (("avoid_task", ("MT-SLEEP-001",)),),
    "long_rest": (("avoid_task", ("MT-BREAK-001", "MT-BREAK-002", "MT-BREAK-003")),),
    "interrupt_study": (
        (
            "avoid_task",
            (
                "MT-BREAK-001",
                "MT-BREAK-002",
                "MT-BREAK-003",
                "MT-SED-001",
                "MT-OUT-001",
                "MT-REC-001",
                "MT-REC-002",
            ),
        ),
    ),
    "none": (),
}

_MAIN_CONTEXT: dict[str, tuple[tuple[str, object], ...]] = {
    "home": (("context_preference", {"preferred_context": "home"}),),
    "school": (("context_preference", {"preferred_context": "school"}),),
    "both": (),
}

_LEAVE_SEAT: dict[str, tuple[tuple[str, object], ...]] = {
    "not_allowed": (("avoid_task", ("MT-BREAK-004", "MT-SED-001")),),
    "allowed": (),
    "sometimes": (),
}

_BREAK_MINUTES: dict[str, tuple[tuple[str, object], ...]] = {
    "under_5": (("user_constraint", {"preferred_max_task_minutes": 5}),),
    "5_10": (("user_constraint", {"preferred_max_task_minutes": 10}),),
    "10_20": (("user_constraint", {"preferred_max_task_minutes": 20}),),
    "over_20": (("user_constraint", {"preferred_max_task_minutes": 30}),),
    "varies": (),
}


def _question(question_id, title, description, option_type, options, required):
    return {
        "question_id": question_id,
        "title": title,
        "description": description,
        "option_type": option_type,
        "required": required,
        "options": [{"value": value, "label": label} for value, label in options],
    }


def questionnaire_schema() -> dict[str, Any]:
    return {
        "questionnaire_id": QUESTIONNAIRE_VERSION,
        "questions": [
            _question(
                "bedtime",
                "平时几点睡觉？",
                "不用很精确，大概时间就行。",
                "single",
                [
                    ("before_2130", "21:30 前"),
                    ("2130_2230", "21:30 – 22:30"),
                    ("2230_2330", "22:30 – 23:30"),
                    ("after_2330", "23:30 后"),
                    ("varies", "不太固定"),
                ],
                required=False,
            ),
            _question(
                "screen_duration",
                "一次连续学习或看屏幕，通常持续多久？",
                "大概估计一下就好。",
                "single",
                [
                    ("under_30", "不到 30 分钟"),
                    ("30_60", "30 – 60 分钟"),
                    ("60_120", "1 – 2 小时"),
                    ("over_120", "2 小时以上"),
                    ("varies", "看情况"),
                ],
                required=False,
            ),
            _question(
                "rest_preference",
                "学习一段时间后有点累了，你更喜欢哪种休息？",
                "选一个最贴近你的。",
                "single",
                [
                    ("quiet_rest", "安静休息一下"),
                    ("far_view", "远眺放松"),
                    ("light_activity", "起身做点轻微活动"),
                    ("outdoor", "到户外待一会儿"),
                    ("depends", "看情况"),
                ],
                required=True,
            ),
            _question(
                "annoying_reminders",
                "哪些提醒会让你觉得有点烦？",
                "可以多选，都没有就选「都不烦」。",
                "multi",
                [
                    ("activity", "「动一动 / 起身活动」"),
                    ("stop_phone", "「放下手机」"),
                    ("long_rest", "「休息 / 远眺」"),
                    ("interrupt_study", "「打断学习」"),
                    ("none", "都不烦"),
                ],
                required=True,
            ),
            _question(
                "main_context",
                "你大多数时候在哪里学习？",
                None,
                "single",
                [
                    ("home", "主要在家"),
                    ("school", "主要在学校"),
                    ("both", "家里和学校都有"),
                ],
                required=True,
            ),
            _question(
                "leave_seat_allowed",
                "上课或自习时，允许离开座位活动吗？",
                None,
                "single",
                [
                    ("allowed", "可以"),
                    ("not_allowed", "不太可以"),
                    ("sometimes", "看情况"),
                ],
                required=True,
            ),
            _question(
                "break_minutes",
                "课间或休息，一般有多长时间？",
                None,
                "single",
                [
                    ("under_5", "不到 5 分钟"),
                    ("5_10", "5 – 10 分钟"),
                    ("10_20", "10 – 20 分钟"),
                    ("over_20", "20 分钟以上"),
                    ("varies", "看情况"),
                ],
                required=True,
            ),
        ],
    }


def _question_definitions() -> dict[str, dict[str, Any]]:
    return {item["question_id"]: item for item in questionnaire_schema()["questions"]}


def invalid_answer_reasons(answers: dict[str, Any]) -> list[str]:
    """Return reason codes for malformed answers; empty list means valid.

    ``missing_required_answers`` alone signals a legitimate partial completion
    (resumable), never a rejection.
    """
    if not isinstance(answers, dict):
        return ["answers_not_object"]
    if not answers:
        return ["answers_empty"]
    definitions = _question_definitions()
    reasons = []
    for question_id, value in answers.items():
        definition = definitions.get(question_id)
        if definition is None:
            reasons.append("unknown_question_id")
            continue
        allowed = {option["value"] for option in definition["options"]}
        if definition["option_type"] == "multi":
            if (
                not isinstance(value, list)
                or not value
                or not set(value) <= allowed
                or ("none" in value and len(value) > 1)
            ):
                reasons.append(f"invalid_{question_id}")
        elif value not in allowed:
            reasons.append(f"invalid_{question_id}")
    if reasons:
        return sorted(set(reasons))
    if not all(
        question_id in answers and answers[question_id]
        for question_id, definition in definitions.items()
        if definition["required"]
    ):
        return ["missing_required_answers"]
    return []


def completion_state_for(answers: dict[str, Any]) -> str:
    reasons = invalid_answer_reasons(answers)
    if reasons == ["missing_required_answers"]:
        return "partially_completed"
    if reasons:
        raise ValueError(reasons[0])
    return "completed"


@lru_cache(maxsize=1)
def _formal_task_domains() -> dict[str, str]:
    return {task["task_id"]: task["domain"] for task in load_formal_micro_tasks()}


def map_answers_to_memories(answers: dict[str, Any]) -> list[UserMemoryCandidate]:
    """Deterministic answers -> memory-candidate mapping (no storage, no models).

    Only defensible mappings to the 23 formal MicroTask IDs are produced.  No
    task_feedback is ever fabricated here.  Partial answer sets map the
    answered subset; malformed values are rejected.
    """
    malformed = [
        reason for reason in invalid_answer_reasons(answers) if reason != "missing_required_answers"
    ]
    if malformed:
        raise ValueError(malformed[0])

    mappings: dict[str, dict[str, tuple[tuple[str, object], ...]]] = {
        "rest_preference": _REST_PREFERENCE,
        "annoying_reminders": _ANNOYING_REMINDERS,
        "main_context": _MAIN_CONTEXT,
        "leave_seat_allowed": _LEAVE_SEAT,
        "break_minutes": _BREAK_MINUTES,
    }
    formal_domains = _formal_task_domains()
    candidates: list[UserMemoryCandidate] = []
    for question_id, answer in answers.items():
        if question_id not in mappings:
            continue
        values = answer if isinstance(answer, list) else [answer]
        for value in values:
            for instruction, payload in mappings[question_id].get(value, ()):
                if instruction in {"prefer_task", "avoid_task"}:
                    for task_id in payload:
                        if task_id not in formal_domains:
                            continue
                        candidates.append(
                            UserMemoryCandidate(
                                memory_id="",
                                user_id="",
                                memory_type="task_preference",
                                source_type=QUESTIONNAIRE_SOURCE,
                                task_id=task_id,
                                domain=formal_domains[task_id],
                                memory_key="task_preference",
                                memory_value={"preference": instruction},
                                created_at="",
                                updated_at="",
                            )
                        )
                else:
                    memory_type, memory_value = instruction, payload
                    candidates.append(
                        UserMemoryCandidate(
                            memory_id="",
                            user_id="",
                            memory_type=memory_type,
                            source_type=QUESTIONNAIRE_SOURCE,
                            task_id=None,
                            domain=None,
                            memory_key=memory_type,
                            memory_value=memory_value,
                            created_at="",
                            updated_at="",
                        )
                    )
    return candidates


def _not_started_record(user_id: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "questionnaire_id": QUESTIONNAIRE_VERSION,
        "completion_state": "not_started",
        "updated_at": None,
        "completed_at": None,
        "answers": {},
        "memory_record_ids": [],
    }


def get_questionnaire(client, user_id: str) -> dict[str, Any]:
    try:
        source = client.get(index=QUESTIONNAIRE_INDEX, id=user_id)["_source"]
    except NotFoundError:
        return _not_started_record(user_id)
    if source.get("user_id") != user_id:
        return _not_started_record(user_id)
    return source


def _upsert_memory(
    client, profile: UserProfile, candidate: UserMemoryCandidate
) -> tuple[str, str]:
    memory_id = build_memory_id(candidate)
    candidate = UserMemoryCandidate(**{**asdict(candidate), "memory_id": memory_id})
    allowed = {candidate.task_id} if candidate.task_id else set()
    result = create_memory(client, profile, candidate, allowed)
    if result["status"] == "already_exists":
        result = update_memory(client, profile, candidate, allowed)
    return result["status"], memory_id


def save_questionnaire(
    client,
    user_id: str,
    answers: dict[str, Any],
    api_key: str | None = None,
) -> dict[str, Any]:
    """Validate, persist questionnaire answers, and initialize memory records.

    Fail-safe: malformed answer sets are rejected without touching storage.
    Already-existing questionnaire memory is upserted in place, so resuming
    from a partial completion is idempotent.

    When ``api_key`` is provided, every persisted memory is embedded right
    after the upsert so vector recall works immediately.  Embedding failures
    never fail the save: the questionnaire record is already durable and the
    next feedback-loop write can re-embed the same memory id.  Callers that
    omit ``api_key`` (offline tests) skip embedding entirely.
    """
    reasons = [
        reason for reason in invalid_answer_reasons(answers) if reason != "missing_required_answers"
    ]
    if reasons:
        return {"status": "rejected", "reason_codes": reasons}

    profile = get_user_profile(client, user_id)
    if profile is None:
        return {"status": "rejected", "reason_codes": ["profile_not_found"]}

    state = completion_state_for(answers)
    now = datetime.now(UTC).isoformat()
    memory_ids: list[str] = []
    for candidate in map_answers_to_memories(answers):
        candidate = UserMemoryCandidate(
            **{
                **asdict(candidate),
                "user_id": user_id,
                "created_at": now,
                "updated_at": now,
            }
        )
        status, memory_id = _upsert_memory(client, profile, candidate)
        if status in {"created", "updated"}:
            memory_ids.append(memory_id)

    memory_ids = list(dict.fromkeys(memory_ids))  # a task can be implied by >1 answer

    record = {
        "user_id": user_id,
        "questionnaire_id": QUESTIONNAIRE_VERSION,
        "completion_state": state,
        "updated_at": now,
        "completed_at": now if state in {"completed", "skipped"} else None,
        "answers": answers,
        "memory_record_ids": memory_ids,
    }
    client.index(index=QUESTIONNAIRE_INDEX, id=user_id, document=record, refresh="wait_for")

    # Vector recall over user_memory_v1 requires the embedding field, and the
    # BM25 fallback does not match Chinese queries against the English
    # retrieval_text of these memories, so memories saved without embedding
    # were effectively unreachable by Personal retrieval.  Embed now, best
    # effort, mirroring the feedback loop in api.app.
    embedded = 0
    if api_key:
        for memory_id in memory_ids:
            try:
                if embed_memory(client, user_id, memory_id, api_key)["status"] == "embedded":
                    embedded += 1
            except (ApiError, RuntimeError, ValueError):
                continue
    return {"status": "saved", "memory_embedding_count": embedded, **record}


def skip_questionnaire(client, user_id: str) -> dict[str, Any]:
    """Mark the questionnaire skipped; no memory is generated and the product
    keeps working through Basic/current-context behavior."""
    profile = get_user_profile(client, user_id)
    if profile is None:
        return {"status": "rejected", "reason_codes": ["profile_not_found"]}
    now = datetime.now(UTC).isoformat()
    record = {
        "user_id": user_id,
        "questionnaire_id": QUESTIONNAIRE_VERSION,
        "completion_state": "skipped",
        "updated_at": now,
        "completed_at": now,
        "answers": {},
        "memory_record_ids": [],
    }
    client.index(index=QUESTIONNAIRE_INDEX, id=user_id, document=record, refresh="wait_for")
    return {"status": "skipped", **record}
