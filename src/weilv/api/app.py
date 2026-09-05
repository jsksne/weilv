"""Minimal Stage 5 FastAPI application over the frozen Python core."""

import json
import os
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from elasticsearch import ApiError, Elasticsearch
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from weilv.agentic_rag import run_agentic_rag
from weilv.api.agentic_trace import (
    NODE_STAGE,
    STAGE_LABELS,
    iter_agentic_graph_events,
    public_stage_result,
    sanitize_final_response,
    translate_graph_event,
)
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
    ScheduleDeleteResponse,
    ScheduleEventRequest,
    ScheduleEventResponse,
    ScheduleListResponse,
    TaskEventRequest,
    TaskEventResponse,
    TaskFeedbackRequest,
    TaskFeedbackResponse,
    TodaySessionsResponse,
    WeeklyResponse,
)
from weilv.api.schedule_queries import (
    create_schedule_event,
    delete_schedule_event,
    get_schedule_event,
    list_schedule_events,
    update_schedule_event,
)
from weilv.api.task_events import append_task_event
from weilv.api.today_queries import list_today_sessions
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
from weilv.retrieval_slice import create_elasticsearch_client, load_api_key
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
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(application: FastAPI):
    env_file = PROJECT_ROOT / ".env"
    application.state.es_client = create_elasticsearch_client(
        env_file,
        client_factory=Elasticsearch,
    )
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


def _task_snapshot(task: dict, fallback: dict | None = None) -> dict:
    """Display fields kept with the interaction log so the day's tasks can be
    faithfully restored later even if the formal library changes."""
    merged = {**(fallback or {}), **task}
    return {
        "task_id": merged["task_id"],
        "title": merged.get("title") or "",
        "instruction": merged.get("instruction") or "",
        "estimated_minutes": merged.get("estimated_minutes"),
        "covered_domains": list(merged.get("covered_domains") or []),
        "sources": list(merged.get("sources") or []),
    }


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

    client = _dependency(request, "es_client")
    tasks = result.get("tasks")
    if tasks is None:
        tasks = [
            {"recommendation_id": str(uuid4()), "task_id": result["selected_task"]["task_id"]}
        ]
    else:
        for task in tasks:
            task["recommendation_id"] = str(uuid4())
    now = datetime.now(UTC).isoformat()
    try:
        for task in tasks:
            create_recommendation_log(
                client,
                {
                    "recommendation_id": task["recommendation_id"],
                    "user_id": payload.user_id,
                    "status": result["status"],
                    "selected_task_id": task["task_id"],
                    "task": _task_snapshot(task, result.get("selected_task")),
                    "target_stage": payload.target_stage,
                    "current_context": payload.current_context,
                    "activity_context": payload.activity_context,
                    "available_minutes": payload.available_minutes,
                    "created_at": now,
                    "feedback": None,
                    "feedback_updated_at": None,
                    "memory_persisted": False,
                },
            )
    except (ApiError, RuntimeError, ValueError):
        for task in tasks:
            task["recommendation_id"] = None
        return result
    result["recommendation_id"] = tasks[0]["recommendation_id"]
    result["feedback_available"] = True
    return result


def _agentic_recommendation_session(
    payload: RecommendationRequest,
    result: dict,
    recommendation_id: str,
) -> dict:
    """Shared interaction-log session for a real Agentic execution."""
    diagnostics = result["diagnostics"]
    return {
        "recommendation_id": recommendation_id,
        "user_id": payload.user_id,
        "status": result["status"],
        "selected_task_id": result["selected_task"]["task_id"],
        "task": {
            **_task_snapshot(result["selected_task"]),
            "sources": list(result.get("sources") or []),
        },
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


def _ndjson_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


async def _agentic_stream_generator(
    payload: RecommendationRequest,
    client,
    api_key: str,
):
    """Yield sanitized public trace events for one real Agentic execution."""
    start = time.monotonic()
    sequence = 0

    def event_payload(
        stage: str,
        status: str,
        result: dict | None = None,
        stage_result: dict | None = None,
        label: str | None = None,
    ) -> dict:
        nonlocal sequence
        sequence += 1
        event: dict = {
            "stage": stage,
            "status": status,
            "label": label or STAGE_LABELS[stage],
            "sequence": sequence,
            "timestamp_ms": int((time.monotonic() - start) * 1000),
        }
        if result is not None:
            event["result"] = result
        if stage_result is not None:
            event["stage_result"] = stage_result
        return event

    yield _ndjson_line(event_payload("accepted", "active"))
    result = None
    started_nodes: set[str] = set()
    completed_nodes: set[str] = set()
    graph_state: dict = {}
    try:
        async for event in iter_agentic_graph_events(
            BasicRagRequest(**payload.model_dump(exclude={"user_id"})),
            payload.user_id,
            client,
            api_key,
        ):
            node = (event.get("metadata") or {}).get("langgraph_node")
            event_name = event.get("event")
            if event_name == "on_chain_end":
                output = (event.get("data") or {}).get("output") or {}
                if isinstance(output, dict):
                    if output.get("result") is not None:
                        result = output["result"]
                    if node and node not in completed_nodes:
                        completed_nodes.add(node)
                        graph_state.update(output)
                        stage = NODE_STAGE.get(node)
                        if stage in {"analysis", "retrieval"}:
                            stage_result = public_stage_result(stage, graph_state)
                            if stage_result is not None:
                                done_label = {
                                    "analysis": "已完成分析",
                                    "retrieval": "已完成检索",
                                }[stage]
                                yield _ndjson_line(
                                    event_payload(
                                        stage,
                                        "complete",
                                        stage_result=stage_result,
                                        label=done_label,
                                    )
                                )
                continue
            if node and event_name == "on_chain_start":
                # astream_events 会对同一节点重复发出 on_chain_start；
                # 粗粒度 trace 每个阶段只出现一次。
                if node in started_nodes:
                    continue
                started_nodes.add(node)
                public = translate_graph_event(event)
                if public:
                    yield _ndjson_line(
                        event_payload(public["stage"], public["status"])
                    )
    except Exception:
        yield _ndjson_line(event_payload("error", "error"))
        return
    if result is None:
        yield _ndjson_line(event_payload("error", "error"))
        return

    sanitized = sanitize_final_response(result)
    sanitized["recommendation_id"] = None
    sanitized["feedback_available"] = False
    if result.get("status") == "allowed" and result.get("selected_task"):
        recommendation_id = str(uuid4())
        try:
            create_recommendation_log(
                client,
                _agentic_recommendation_session(payload, result, recommendation_id),
            )
            sanitized["recommendation_id"] = recommendation_id
            sanitized["feedback_available"] = True
        except (ApiError, RuntimeError, ValueError):
            pass
    yield _ndjson_line(event_payload("completed", "complete", sanitized))


@app.post("/api/v1/recommend/agentic/stream")
async def agentic_recommendation_stream(payload: RecommendationRequest, request: Request):
    """B3: NDJSON stream of real, sanitized Agentic execution stages.

    Runs the Agentic pipeline exactly once (same graph and semantics as
    ``/api/v1/recommend/agentic``); the final answer comes from that same
    execution.  Only public coarse stages are exposed.
    """
    client = _dependency(request, "es_client")
    api_key = _dependency(request, "api_key")
    return StreamingResponse(
        _agentic_stream_generator(payload, client, api_key),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    session = _agentic_recommendation_session(payload, result, recommendation_id)
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


@app.get("/api/v1/users/{user_id}/schedule", response_model=ScheduleListResponse)
def read_user_schedule(
    user_id: str,
    request: Request,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
):
    """List the user's schedule events overlapping [from, to] (default: 14 days)."""
    today = datetime.now(UTC).date()
    overlap_start = from_date or today
    overlap_end = to_date or today + timedelta(days=13)
    if overlap_start > overlap_end:
        raise HTTPException(status_code=422, detail="invalid_date_range")
    try:
        events = list_schedule_events(_dependency(request, "es_client"), user_id, overlap_start, overlap_end)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    return {
        "user_id": user_id,
        "events": [
            ScheduleEventResponse(
                event_id=event["event_id"],
                name=event["name"],
                start_date=event["start_date"],
                end_date=event["end_date"],
                kind=event["kind"],
                busy_level=event.get("busy_level"),
                created_at=event.get("created_at") or "",
                updated_at=event.get("updated_at") or "",
            )
            for event in events
        ],
    }


@app.post("/api/v1/users/{user_id}/schedule", response_model=ScheduleEventResponse)
def create_user_schedule_event(
    user_id: str,
    payload: ScheduleEventRequest,
    request: Request,
):
    client = _dependency(request, "es_client")
    try:
        document = create_schedule_event(client, user_id, payload.model_dump())
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    return ScheduleEventResponse(
        event_id=document["event_id"],
        name=document["name"],
        start_date=document["start_date"],
        end_date=document["end_date"],
        kind=document["kind"],
        busy_level=document.get("busy_level"),
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )


@app.put("/api/v1/users/{user_id}/schedule/{event_id}", response_model=ScheduleEventResponse)
def update_user_schedule_event(
    user_id: str,
    event_id: str,
    payload: ScheduleEventRequest,
    request: Request,
):
    client = _dependency(request, "es_client")
    try:
        document = update_schedule_event(client, user_id, event_id, payload.model_dump())
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    if document is None:
        raise HTTPException(status_code=404, detail="schedule_event_not_found")
    return ScheduleEventResponse(
        event_id=document["event_id"],
        name=document["name"],
        start_date=document["start_date"],
        end_date=document["end_date"],
        kind=document["kind"],
        busy_level=document.get("busy_level"),
        created_at=document.get("created_at") or "",
        updated_at=document.get("updated_at") or "",
    )


@app.delete("/api/v1/users/{user_id}/schedule/{event_id}", response_model=ScheduleDeleteResponse)
def delete_user_schedule_event(user_id: str, event_id: str, request: Request):
    client = _dependency(request, "es_client")
    try:
        deleted = delete_schedule_event(client, user_id, event_id)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error
    if not deleted:
        raise HTTPException(status_code=404, detail="schedule_event_not_found")
    return ScheduleDeleteResponse(status="deleted", event_id=event_id)


@app.get("/api/v1/users/{user_id}/today", response_model=TodaySessionsResponse)
def read_user_today(
    user_id: str,
    request: Request,
    day: date | None = Query(default=None, alias="date"),
):
    """Restore the user's same-day recommendation sessions (read-only).

    Date convention matches the weekly aggregation: UTC day boundaries.
    """
    selected_day = day or datetime.now(UTC).date()
    try:
        return list_today_sessions(_dependency(request, "es_client"), user_id, selected_day)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail="dependency_service_unavailable") from error


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


if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{path:path}", include_in_schema=False)
    def serve_frontend(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not_found")
        requested = FRONTEND_DIST / path
        if path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(FRONTEND_DIST / "index.html")
