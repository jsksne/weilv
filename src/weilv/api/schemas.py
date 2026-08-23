"""HTTP request and response contracts for the Stage 5 API."""

from typing import Any, Literal

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


class RecommendationResponse(BaseModel):
    status: str
    selected_task: dict[str, Any] | None = None
    explanation: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    context_sources: list[dict[str, Any]] | None = None
    matched_rule_ids: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    explanation_guard: dict[str, Any] | None = None
    personalization: dict[str, Any] | None = None
    recommendation_id: str | None = None
    feedback_available: bool = False


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
