"""Minimal Stage 5 FastAPI application over the frozen Python core."""

import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from elasticsearch import ApiError, Elasticsearch
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from weilv.agentic_rag import run_agentic_rag
from weilv.api.memory_queries import query_user_memories
from weilv.api.schemas import (
    AgenticRecommendationResponse,
    MemoryDeleteResponse,
    MemoryListResponse,
    ProfileRequest,
    ProfileResponse,
    QuestionnaireAnswerRequest,
    QuestionnaireResponse,
    QuestionnaireSchemaResponse,
    RecommendationRequest,
    RecommendationResponse,
    TaskEventRequest,
    TaskEventResponse,
    TaskFeedbackRequest,
    TaskFeedbackResponse,
    WeeklyResponse,
)
from weilv.api.task_events import append_task_event
from weilv.api.weekly_queries import aggregate_weekly
from weilv.basic_rag import BasicRagRequest
from weilv.elasticsearch_indices import ensure_stage_one_indices, ensure_user_memory_indices
from weilv.feedback_loop import (
    build_feedback_memory_candidate,
    compute_confidence,
    get_feedback_memory_value,
)
from weilv.interaction_logs import (
    create_recommendation_log,
    get_recommendation_log,
    update_recommendation_feedback,
)
from weilv.personal_memory_retrieval import embed_memory
from weilv.personal_rag import run_personal_rag
from weilv.questionnaire import (
    get_questionnaire,
    questionnaire_schema,
    save_questionnaire,
    skip_questionnaire,
)
from weilv.retrieval_slice import _env_value, load_api_key
from weilv.user_memory import (
    UserMemoryCandidate,
    UserProfile,
    build_memory_id,
    create_memory,
    forget_memory,
    get_user_profile,
    update_memory,
    upsert_user_profile,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@asynccontextmanager
async def lifespan(application: FastAPI):
    env_file = PROJECT_ROOT / ".env"
    es_url = _env_value("ELASTICSEARCH_URL", env_file) or "http://127.0.0.1:9200"
    application.state.es_client = Elasticsearch(es_url, request_timeout=30)
    try:
        ensure_stage_one_indices(application.state.es_client)
        ensure_user_memory_indices(application.state.es_client)
        try:
            application.state.api_key = load_api_key(env_file)
        except RuntimeError:
            application.state.api_key = None
        yield
    finally:
        application.state.es_client.close()


app = FastAPI(title="Weilv API", version="1.0.0", lifespan=lifespan)
origins = [
    value.strip()
    for value in os.getenv("WEILV_CORS_ORIGINS", "http://localhost:5173").split(",")
    if value.strip() and value.strip() != "*"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _dependency(request: Request, name: str):
    value = getattr(request.app.state, name, None)
    if value is None:
        raise HTTPException(status_code=503, detail="api_not_configured")
    return value


@app.post(
    "/api/v1/recommendations",
    response_model=RecommendationResponse,
)
def recommendations(payload: RecommendationRequest, request: Request):
    rag_request = BasicRagRequest(**payload.model_dump(exclude={"user_id"}))
    try:
        result = run_personal_rag(
            rag_request,
            payload.user_id,
            _dependency(request, "es_client"),
            _dependency(request, "api_key"),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    result = dict(result)
    result.update(recommendation_id=None, feedback_available=False)
    if result.get("status") != "allowed" or not result.get("selected_task"):
        return result

    recommendation_id = str(uuid4())
    session = {
        "recommendation_id": recommendation_id,
        "user_id": payload.user_id,
        "status": result["status"],
        "selected_task_id": result["selected_task"]["task_id"],
        "target_stage": payload.target_stage,
        "current_context": payload.current_context,
        "activity_context": payload.activity_context,
        "available_minutes": payload.available_minutes,
        "created_at": datetime.now(UTC).isoformat(),
        "feedback": None,
        "feedback_updated_at": None,
        "memory_persisted": False,
    }
    try:
        create_recommendation_log(_dependency(request, "es_client"), session)
    except (ApiError, RuntimeError, ValueError):
        return result
    result.update(recommendation_id=recommendation_id, feedback_available=True)
    return result


@app.post(
    "/api/v1/recommend/agentic",
    response_model=AgenticRecommendationResponse,
)
def agentic_recommendation(payload: RecommendationRequest, request: Request):
    rag_request = BasicRagRequest(**payload.model_dump(exclude={"user_id"}))
    try:
        result = run_agentic_rag(
            rag_request,
            payload.user_id,
            _dependency(request, "es_client"),
            _dependency(request, "api_key"),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    result = dict(result)
    result.update(recommendation_id=None, feedback_available=False)
    if result.get("status") != "allowed" or not result.get("selected_task"):
        return result

    recommendation_id = str(uuid4())
    diagnostics = result["diagnostics"]
    session = {
        "recommendation_id": recommendation_id,
        "user_id": payload.user_id,
        "status": result["status"],
        "selected_task_id": result["selected_task"]["task_id"],
        "target_stage": payload.target_stage,
        "current_context": payload.current_context,
        "activity_context": payload.activity_context,
        "available_minutes": payload.available_minutes,
        "agentic": True,
        "factor_count": diagnostics["factor_count"],
        "memory_hit": diagnostics["memory_hit_count"] > 0,
        "model_call_counts": diagnostics["model_calls"],
        "created_at": datetime.now(UTC).isoformat(),
        "feedback": None,
        "feedback_updated_at": None,
        "memory_persisted": False,
    }
    try:
        create_recommendation_log(_dependency(request, "es_client"), session)
    except (ApiError, RuntimeError, ValueError):
        return result
    result.update(recommendation_id=recommendation_id, feedback_available=True)
    return result


@app.put("/api/v1/users/{user_id}/profile", response_model=ProfileResponse)
def put_profile(user_id: str, payload: ProfileRequest, request: Request):
    client = _dependency(request, "es_client")
    try:
        existing = get_user_profile(client, user_id)
        now = datetime.now(UTC).isoformat()
        profile = UserProfile(
            user_id=user_id,
            target_stage=payload.target_stage,
            memory_enabled=payload.memory_enabled,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        upsert_user_profile(client, profile)
        return asdict(profile)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error


@app.get("/api/v1/users/{user_id}/profile", response_model=ProfileResponse)
def read_profile(user_id: str, request: Request):
    try:
        profile = get_user_profile(_dependency(request, "es_client"), user_id)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    if profile is None:
        raise HTTPException(status_code=404, detail="profile_not_found")
    return asdict(profile)


@app.get("/api/v1/questionnaire", response_model=QuestionnaireSchemaResponse)
def read_questionnaire_schema(request: Request):
    return questionnaire_schema()


@app.get("/api/v1/users/{user_id}/questionnaire", response_model=QuestionnaireResponse)
def read_user_questionnaire(user_id: str, request: Request):
    try:
        return get_questionnaire(_dependency(request, "es_client"), user_id)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error


@app.put("/api/v1/users/{user_id}/questionnaire", response_model=QuestionnaireResponse)
def put_user_questionnaire(
    user_id: str, payload: QuestionnaireAnswerRequest, request: Request
):
    try:
        result = save_questionnaire(
            _dependency(request, "es_client"),
            user_id,
            payload.answers,
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    if result["status"] == "rejected":
        raise HTTPException(status_code=422, detail=result["reason_codes"][0])
    return result


@app.post("/api/v1/users/{user_id}/questionnaire/skip", response_model=QuestionnaireResponse)
def skip_user_questionnaire(user_id: str, request: Request):
    try:
        result = skip_questionnaire(_dependency(request, "es_client"), user_id)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    if result["status"] == "rejected":
        raise HTTPException(status_code=422, detail=result["reason_codes"][0])
    return result


def persist_task_feedback_memory(
    client,
    profile: UserProfile,
    candidate: UserMemoryCandidate,
    api_key: str | None,
) -> dict[str, bool]:
    memory_id = build_memory_id(candidate)
    candidate = UserMemoryCandidate(**{**asdict(candidate), "memory_id": memory_id})
    result = create_memory(client, profile, candidate, {candidate.task_id})
    if result["status"] == "already_exists":
        result = update_memory(client, profile, candidate, {candidate.task_id})
    memory_persisted = result["status"] in {"created", "updated"}
    embedding_ready = False
    if memory_persisted and api_key:
        try:
            embedding_ready = embed_memory(client, profile.user_id, memory_id, api_key)[
                "status"
            ] == "embedded"
        except (ApiError, RuntimeError, ValueError):
            embedding_ready = False
    return {
        "memory_persisted": memory_persisted,
        "memory_embedding_ready": embedding_ready,
    }


@app.post(
    "/api/v1/users/{user_id}/recommendations/{recommendation_id}/feedback",
    response_model=TaskFeedbackResponse,
)
def submit_task_feedback(
    user_id: str,
    recommendation_id: str,
    payload: TaskFeedbackRequest,
    request: Request,
):
    client = _dependency(request, "es_client")
    try:
        session = get_recommendation_log(client, user_id, recommendation_id)
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    if session is None or not session.get("selected_task_id"):
        raise HTTPException(status_code=404, detail="recommendation_not_found")

    now = datetime.now(UTC).isoformat()
    feedback = payload.model_dump()
    memory_persisted = False
    memory_id = None
    confidence = None
    try:
        profile = get_user_profile(client, user_id)
        task_id = session["selected_task_id"]
        if profile is not None and profile.memory_enabled:
            previous = get_feedback_memory_value(client, user_id, task_id)
            confidence = compute_confidence(previous, feedback["usefulness"])
            candidate = build_feedback_memory_candidate(
                user_id, task_id, feedback, confidence, now
            )
            memory_id = build_memory_id(candidate)
            memory_persisted = persist_task_feedback_memory(
                client,
                profile,
                candidate,
                getattr(request.app.state, "api_key", None),
            )["memory_persisted"]
            if not memory_persisted:
                memory_id = None
                confidence = None
        update_recommendation_feedback(
            client,
            recommendation_id,
            feedback,
            now,
            memory_persisted,
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    return {
        "status": "recorded",
        "recommendation_id": recommendation_id,
        "task_id": task_id,
        "memory_persisted": memory_persisted,
        "memory_id": memory_id,
        "confidence": confidence,
    }


@app.post(
    "/api/v1/users/{user_id}/recommendations/{recommendation_id}/events",
    response_model=TaskEventResponse,
)
def record_task_event(
    user_id: str,
    recommendation_id: str,
    payload: TaskEventRequest,
    request: Request,
):
    client = _dependency(request, "es_client")
    try:
        session = get_recommendation_log(client, user_id, recommendation_id)
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    if session is None or not session.get("selected_task_id"):
        raise HTTPException(status_code=404, detail="recommendation_not_found")

    now = datetime.now(UTC).isoformat()
    event = {"action": payload.action, "recorded_at": now}
    try:
        append_task_event(client, session, event)
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    return {
        "status": "recorded",
        "recommendation_id": recommendation_id,
        "task_id": session["selected_task_id"],
        "action": payload.action,
        "recorded_at": now,
    }


@app.get("/api/v1/users/{user_id}/memories", response_model=MemoryListResponse)
def read_user_memories(user_id: str, request: Request):
    client = _dependency(request, "es_client")
    try:
        memories = query_user_memories(client, user_id)
        profile = get_user_profile(client, user_id)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    return {
        "user_id": user_id,
        "memory_enabled": bool(profile and profile.memory_enabled),
        "memories": memories,
    }


@app.post(
    "/api/v1/users/{user_id}/memories/{memory_id}/delete",
    response_model=MemoryDeleteResponse,
)
def delete_user_memory(user_id: str, memory_id: str, request: Request):
    client = _dependency(request, "es_client")
    try:
        result = forget_memory(client, user_id, memory_id)
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    if result["status"] != "forgotten":
        raise HTTPException(status_code=404, detail="memory_not_found")
    return result


@app.get("/api/v1/users/{user_id}/weekly", response_model=WeeklyResponse)
def read_user_weekly(
    user_id: str,
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
):
    today = datetime.now(UTC).date()
    start = start_date or today - timedelta(days=6)
    end = end_date or today
    if start > end:
        raise HTTPException(status_code=422, detail="invalid_date_range")
    try:
        return aggregate_weekly(_dependency(request, "es_client"), user_id, start, end)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
