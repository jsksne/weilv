"""HTTP request and response contracts for the Stage 5 API."""

from typing import Any, Literal

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from weilv.feedback_loop import DIFFICULTY_VALUES, USEFULNESS_VALUES
from weilv.user_memory import COMPLETION_STATUSES

TargetStage = Literal["primary_upper", "junior_high", "senior_high"]
CurrentContext = Literal[
    "home", "school", "study_space", "commute", "bedroom", "outdoor", "unknown"
]
ActivityContext = Literal["reading", "writing", "screen", "other", "unknown"]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


ScheduleKind = Literal["exam", "holiday", "plan"]


class ScheduleEventRequest(StrictRequest):
    """User schedule event (spec: 日程最小实现).

    ``name`` is user data: stored verbatim, never indexed, never sent to any
    model prompt. Only structured facts (kind/busy_level) enter the
    recommendation path.
    """

    name: str = Field(min_length=1, max_length=60)
    start_date: date
    end_date: date
    kind: ScheduleKind
    busy_level: Literal["busy", "some", "free"] | None = None

    @field_validator("end_date")
    @classmethod
    def validate_range(cls, value: date, info):
        start = info.data.get("start_date")
        if start is not None and value < start:
            raise ValueError("end_date_before_start_date")
        return value


class ScheduleEventResponse(BaseModel):
    event_id: str
    name: str
    start_date: date
    end_date: date
    kind: ScheduleKind
    busy_level: Literal["busy", "some", "free"] | None = None
    created_at: str
    updated_at: str


class ScheduleListResponse(BaseModel):
    user_id: str
    events: list[ScheduleEventResponse] = Field(default_factory=list)


class ScheduleDeleteResponse(BaseModel):
    status: str
    event_id: str


class ScheduleEventFact(BaseModel):
    """Structured fact about a schedule event; names are never included."""

    kind: ScheduleKind
    busy_level: Literal["busy", "some", "free"] | None = None


class ConversationTurn(BaseModel):
    """One prior in-session turn carried for continuity (spec F1).

    History only informs understanding of the CURRENT request; it never
    becomes Memory and never bypasses safety filtering.
    """

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class RecommendationRequest(StrictRequest):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    target_stage: TargetStage
    current_context: CurrentContext
    activity_context: ActivityContext = "unknown"
    available_minutes: int | None = Field(default=None, ge=1)
    vision_abnormal: bool = False
    physical_discomfort: bool = False
    medical_request: bool = False
    cannot_move: bool = False
    unstable_environment: bool = False
    sleep_being_crowded: bool = False
    conversation_history: list[ConversationTurn] = Field(
        default_factory=list,
        max_length=12,
    )
    """Structured facts of today's schedule events (names excluded)."""
    schedule_events: list[ScheduleEventFact] = Field(
        default_factory=list,
        max_length=10,
    )
    """易启动偏好：用户表达“不想动/轻一点”后在安全候选内优先短任务。"""
    prefer_easy_start: bool = False


class SurfacedTask(BaseModel):
    """Minimal display contract for one same-run surfaced recommendation task."""

    recommendation_id: str | None = None
    task_id: str
    title: str
    instruction: str
    estimated_minutes: int
    sources: list[dict[str, Any]] = Field(default_factory=list)


class PublicRagFactor(BaseModel):
    factor_id: str
    subquery: str
    evidence_need: str
    domain_hint: str | None = None


class PublicRagKnowledgeChunk(BaseModel):
    factor_id: str
    chunk_id: str
    source_locator: str
    source_url: str | None = None
    excerpt: str


class PublicRagTrace(BaseModel):
    analysis_fallback: bool = False
    factors: list[PublicRagFactor] = Field(default_factory=list)
    knowledge_chunks: list[PublicRagKnowledgeChunk] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    status: str
    selected_task: dict[str, Any] | None = None
    explanation: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    context_sources: list[dict[str, Any]] | None = None
    public_rag: PublicRagTrace | None = None
    matched_rule_ids: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    explanation_guard: dict[str, Any] | None = None
    personalization: dict[str, Any] | None = None
    recommendation_id: str | None = None
    feedback_available: bool = False
    tasks: list[SurfacedTask] | None = None


class AgenticRecommendationResponse(RecommendationResponse):
    agentic: bool = True
    diagnostics: dict[str, Any]


class ProfileRequest(StrictRequest):
    target_stage: TargetStage
    memory_enabled: bool


class ProfileResponse(BaseModel):
    user_id: str
    target_stage: TargetStage
    memory_enabled: bool
    created_at: str
    updated_at: str


class TaskFeedbackRequest(StrictRequest):
    completion_status: str
    usefulness: str
    difficulty: str
    reason: str = Field(default="", max_length=100)

    @field_validator("completion_status")
    @classmethod
    def validate_completion_status(cls, value: str) -> str:
        if value not in COMPLETION_STATUSES:
            raise ValueError("invalid completion_status")
        return value

    @field_validator("usefulness")
    @classmethod
    def validate_usefulness(cls, value: str) -> str:
        if value not in USEFULNESS_VALUES:
            raise ValueError("invalid usefulness")
        return value

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value: str) -> str:
        if value not in DIFFICULTY_VALUES:
            raise ValueError("invalid difficulty")
        return value


class TaskFeedbackResponse(BaseModel):
    status: str
    recommendation_id: str
    task_id: str
    memory_persisted: bool
    memory_id: str | None = None
    confidence: int | None = None


class QuestionnaireAnswerRequest(StrictRequest):
    answers: dict[str, Any] = Field(default_factory=dict)


class QuestionnaireResponse(BaseModel):
    user_id: str
    questionnaire_id: str
    completion_state: str
    updated_at: str | None = None
    completed_at: str | None = None
    answers: dict[str, Any] = Field(default_factory=dict)
    memory_record_ids: list[str] = Field(default_factory=list)


class QuestionnaireSchemaResponse(BaseModel):
    questionnaire_id: str
    questions: list[dict[str, Any]] = Field(default_factory=list)


TaskAction = Literal[
    "started",
    "completed",
    "partially_completed",
    "skipped",
    "replaced",
    "restored",
]


class TaskEventRequest(StrictRequest):
    action: TaskAction


class TaskEventResponse(BaseModel):
    status: str
    recommendation_id: str
    task_id: str
    action: str
    recorded_at: str


class MemoryItemResponse(BaseModel):
    memory_id: str
    memory_type: str
    summary: str
    created_at: str
    updated_at: str


class MemoryListResponse(BaseModel):
    user_id: str
    memory_enabled: bool
    memories: list[MemoryItemResponse] = Field(default_factory=list)


class MemoryDeleteResponse(BaseModel):
    status: str
    memory_id: str


class TodayActionRecord(BaseModel):
    action: str
    recorded_at: str


class TodaySessionItem(BaseModel):
    """One same-day recommendation session restored for the Today list."""

    recommendation_id: str
    task_id: str
    title: str
    instruction: str
    estimated_minutes: int
    covered_domains: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    agentic: bool = False
    created_at: str
    actions: list[TodayActionRecord] = Field(default_factory=list)
    feedback: dict[str, Any] | None = None


class TodaySessionsResponse(BaseModel):
    user_id: str
    date: str
    sessions: list[TodaySessionItem] = Field(default_factory=list)


class WeeklyEventReport(BaseModel):
    recommendation_id: str
    task_id: str
    title: str | None = None
    action: str
    recorded_at: str


class WeeklyDayReport(BaseModel):
    date: str
    completed_minutes: int
    action_counts: dict[str, int]


class WeeklyTotals(BaseModel):
    completed_minutes: int
    action_counts: dict[str, int]


class WeeklyResponse(BaseModel):
    user_id: str
    start_date: str
    end_date: str
    minutes_policy: str
    days: list[WeeklyDayReport] = Field(default_factory=list)
    totals: WeeklyTotals
    events: list[WeeklyEventReport] = Field(default_factory=list)
    adjustments: list[WeeklyEventReport] = Field(default_factory=list)
