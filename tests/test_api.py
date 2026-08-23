import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from weilv.user_memory import UserProfile

ALLOWED_RESULT = {
    "status": "allowed",
    "selected_task": {"task_id": "MT-SED-001", "instruction": "正式指令"},
    "explanation": "解释",
    "sources": [{"chunk_id": "KC-1"}],
    "context_sources": [{"chunk_id": "KC-2"}],
    "matched_rule_ids": [],
    "reason_codes": [],
    "explanation_guard": {"passed": True, "fallback_used": False, "reason_codes": []},
    "personalization": {
        "memory_used": True,
        "memory_ids": ["UM-1"],
        "base_task_rank": 2,
        "personalization_delta": 3,
        "adjusted_rank": -1,
        "reason_codes": ["preferred_task"],
    },
}


class StartupIndices:
    def __init__(self):
        self.created = []

    def exists(self, *, index):
        return False

    def create(self, **kwargs):
        self.created.append(kwargs)


class StartupElasticsearch:
    def __init__(self):
        self.indices = StartupIndices()
        self.closed = False

    def close(self):
        self.closed = True


def test_lifespan_creates_all_formal_product_indices_before_serving(monkeypatch):
    from weilv.api import app as api

    client = StartupElasticsearch()
    monkeypatch.setattr(api, "Elasticsearch", lambda *_args, **_kwargs: client)
    monkeypatch.setattr(api, "load_api_key", lambda _env_file: "server-key")
    application = FastAPI()

    async def run_lifespan():
        async with api.lifespan(application):
            assert {call["index"] for call in client.indices.created} == {
                "source_documents_v1",
                "health_knowledge_v1",
                "micro_tasks_v1",
                "user_profiles_v1",
                "user_memory_v1",
                "interaction_logs_v1",
                "user_questionnaire_v1",
            }
            memory_call = next(
                call for call in client.indices.created if call["index"] == "user_memory_v1"
            )
            assert memory_call["mappings"]["properties"]["embedding"] == {
                "type": "dense_vector",
                "dims": 1024,
                "index": True,
                "similarity": "cosine",
            }

    asyncio.run(run_lifespan())
    assert client.closed is True


def _recommendation_payload(**changes):
    payload = {
        "user_id": "user-001",
        "query": "我写作业快一个小时了，现在有10分钟休息。",
        "target_stage": "junior_high",
        "current_context": "home",
        "activity_context": "writing",
        "available_minutes": 10,
        "vision_abnormal": False,
        "physical_discomfort": False,
        "medical_request": False,
        "cannot_move": False,
        "unstable_environment": False,
        "sleep_being_crowded": False,
    }
    payload.update(changes)
    return payload


def _client(monkeypatch, *, rag_result=ALLOWED_RESULT):
    from weilv.api import app as api

    calls = []
    log_calls = []
    monkeypatch.setattr(
        api,
        "run_personal_rag",
        lambda *args, **kwargs: calls.append((args, kwargs)) or rag_result,
    )
    monkeypatch.setattr(
        api,
        "create_recommendation_log",
        lambda *args, **kwargs: log_calls.append((args, kwargs)),
        raising=False,
    )
    api.app.state.es_client = object()
    api.app.state.api_key = "server-only-key"
    return TestClient(api.app), calls, log_calls


def test_health_returns_ok_without_checking_external_services(monkeypatch):
    from weilv.api import app as api

    monkeypatch.setattr(api, "Elasticsearch", lambda *_args, **_kwargs: StartupElasticsearch())
    monkeypatch.setattr(api, "load_api_key", lambda _env_file: "server-key")

    with TestClient(api.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recommendation_calls_core_once_and_preserves_frozen_result(monkeypatch):
    client, calls, log_calls = _client(monkeypatch)

    response = client.post("/api/v1/recommendations", json=_recommendation_payload())

    assert response.status_code == 200
    assert {key: response.json()[key] for key in ALLOWED_RESULT} == ALLOWED_RESULT
    assert response.json()["recommendation_id"]
    assert response.json()["feedback_available"] is True
    assert len(calls) == 1
    request, user_id, es_client, api_key = calls[0][0]
    assert user_id == "user-001"
    assert request.activity_context == "writing"
    assert es_client is client.app.state.es_client
    assert api_key == "server-only-key"
    assert len(log_calls) == 1
    session = log_calls[0][0][1]
    assert session["selected_task_id"] == "MT-SED-001"
    assert session["user_id"] == "user-001"
    assert "query" not in session
    assert "explanation" not in session


def test_help_seeking_is_a_normal_http_200_business_response(monkeypatch):
    result = {
        "status": "help_seeking",
        "selected_task": None,
        "explanation": None,
        "sources": [],
        "matched_rule_ids": ["SR-001"],
        "reason_codes": ["vision_abnormal_help_seeking"],
    }
    client, _, log_calls = _client(monkeypatch, rag_result=result)

    response = client.post(
        "/api/v1/recommendations",
        json=_recommendation_payload(vision_abnormal=True),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "help_seeking"
    assert response.json()["selected_task"] is None
    assert response.json()["recommendation_id"] is None
    assert response.json()["feedback_available"] is False
    assert log_calls == []


def test_recommendation_schema_rejects_invalid_enums_api_key_and_extra_fields(monkeypatch):
    client, calls, _ = _client(monkeypatch)

    for changes in (
        {"target_stage": "middle_school"},
        {"current_context": "classroom2"},
        {"activity_context": "gaming"},
        {"api_key": "must-not-enter-request"},
    ):
        response = client.post(
            "/api/v1/recommendations", json=_recommendation_payload(**changes)
        )
        assert response.status_code == 422

    assert calls == []


def test_profile_put_and_get_use_minimal_contract(monkeypatch):
    from weilv.api import app as api

    stored = {}
    monkeypatch.setattr(
        api,
        "upsert_user_profile",
        lambda _client, profile: stored.update({profile.user_id: profile}),
    )
    monkeypatch.setattr(api, "get_user_profile", lambda _client, user_id: stored.get(user_id))
    api.app.state.es_client = object()
    client = TestClient(api.app)

    put = client.put(
        "/api/v1/users/user-001/profile",
        json={"target_stage": "junior_high", "memory_enabled": True},
    )
    get = client.get("/api/v1/users/user-001/profile")

    assert put.status_code == get.status_code == 200
    assert get.json()["user_id"] == "user-001"
    assert get.json()["target_stage"] == "junior_high"
    assert get.json()["memory_enabled"] is True
    assert get.json()["created_at"]
    assert get.json()["updated_at"]


def test_profile_rejects_legacy_stage_and_private_extra_fields(monkeypatch):
    from weilv.api import app as api

    api.app.state.es_client = object()
    client = TestClient(api.app)

    for payload in (
        {"target_stage": "middle_school", "memory_enabled": True},
        {"target_stage": "junior_high", "memory_enabled": True, "school_name": "private"},
    ):
        assert client.put("/api/v1/users/user-001/profile", json=payload).status_code == 422


def test_dependency_failure_returns_sanitized_server_error(monkeypatch):
    from weilv.api import app as api

    secret = "secret-key-that-must-not-leak"
    monkeypatch.setattr(
        api,
        "run_personal_rag",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(secret)),
    )
    api.app.state.es_client = object()
    api.app.state.api_key = "server-only-key"
    client = TestClient(api.app, raise_server_exceptions=False)

    response = client.post("/api/v1/recommendations", json=_recommendation_payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "dependency_service_unavailable"}
    assert secret not in response.text


def test_cors_allows_only_configured_origin_without_wildcard_credentials(monkeypatch):
    client, _, _ = _client(monkeypatch)

    allowed = client.options(
        "/api/v1/recommendations",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    denied = client.options(
        "/api/v1/recommendations",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert allowed.headers.get("access-control-allow-credentials") != "true"
    assert "access-control-allow-origin" not in denied.headers


def test_recommendation_rejects_client_supplied_recommendation_id(monkeypatch):
    client, calls, _ = _client(monkeypatch)

    response = client.post(
        "/api/v1/recommendations",
        json=_recommendation_payload(recommendation_id="client-controlled"),
    )

    assert response.status_code == 422
    assert calls == []


def test_interaction_log_failure_keeps_safe_recommendation_but_disables_feedback(monkeypatch):
    from weilv.api import app as api

    client, _, _ = _client(monkeypatch)
    monkeypatch.setattr(
        api,
        "create_recommendation_log",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("log unavailable")),
    )

    response = client.post("/api/v1/recommendations", json=_recommendation_payload())

    assert response.status_code == 200
    assert response.json()["selected_task"]["task_id"] == "MT-SED-001"
    assert response.json()["recommendation_id"] is None
    assert response.json()["feedback_available"] is False


def _feedback_client(monkeypatch, *, profile_enabled=True, session_user="user-001"):
    from weilv.api import app as api

    session = {
        "recommendation_id": "rec-001",
        "user_id": session_user,
        "status": "allowed",
        "selected_task_id": "MT-SED-001",
    }
    profile = (
        UserProfile("user-001", "junior_high", profile_enabled, "created", "updated")
        if profile_enabled is not None
        else None
    )
    memory_calls = []
    log_updates = []
    monkeypatch.setattr(
        api,
        "get_recommendation_log",
        lambda _client, user_id, recommendation_id: (
            session
            if user_id == session_user and recommendation_id == session["recommendation_id"]
            else None
        ),
        raising=False,
    )
    monkeypatch.setattr(api, "get_user_profile", lambda *_args: profile)
    monkeypatch.setattr(
        api,
        "get_feedback_memory_value",
        lambda *_args, **_kwargs: None,
        raising=False,
    )
    monkeypatch.setattr(
        api,
        "persist_task_feedback_memory",
        lambda *args, **kwargs: memory_calls.append((args, kwargs))
        or {"memory_persisted": True, "memory_embedding_ready": True},
        raising=False,
    )
    monkeypatch.setattr(
        api,
        "update_recommendation_feedback",
        lambda *args, **kwargs: log_updates.append((args, kwargs)),
        raising=False,
    )
    api.app.state.es_client = object()
    api.app.state.api_key = "server-key"
    return TestClient(api.app), memory_calls, log_updates


def _feedback_payload(**changes):
    payload = {
        "completion_status": "completed",
        "usefulness": "helpful",
        "difficulty": "easy",
        "reason": "",
    }
    payload.update(changes)
    return payload


def test_structured_feedback_records_server_task_and_persists_memory(monkeypatch):
    client, memory_calls, log_updates = _feedback_client(monkeypatch)

    response = client.post(
        "/api/v1/users/user-001/recommendations/rec-001/feedback",
        json=_feedback_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "recorded"
    assert body["recommendation_id"] == "rec-001"
    assert body["task_id"] == "MT-SED-001"
    assert body["memory_persisted"] is True
    assert body["memory_id"]
    assert body["confidence"] == 1
    assert len(memory_calls) == 1
    candidate = memory_calls[0][0][2]
    assert candidate.memory_type == "task_feedback"
    assert candidate.source_type == "structured_task_feedback"
    assert candidate.task_id == "MT-SED-001"
    assert candidate.memory_value == {
        "completion_status": "completed",
        "helpfulness": 5,
        "burden": "easy",
        "confidence": 1,
    }
    assert log_updates[0][0][2] == _feedback_payload()


def test_feedback_schema_forbids_memory_controls_and_invalid_values(monkeypatch):
    client, memory_calls, log_updates = _feedback_client(monkeypatch)

    for changes in (
        {"task_id": "MT-OTHER"},
        {"memory_type": "task_preference"},
        {"memory_value": {}},
        {"api_key": "client-key"},
        {"usefulness": "amazing"},
        {"difficulty": "impossible"},
        {"reason": "x" * 101},
    ):
        response = client.post(
            "/api/v1/users/user-001/recommendations/rec-001/feedback",
            json=_feedback_payload(**changes),
        )
        assert response.status_code == 422

    assert memory_calls == log_updates == []


def test_missing_and_cross_user_recommendations_both_return_404(monkeypatch):
    client, _, _ = _feedback_client(monkeypatch, session_user="user-B")

    cross_user = client.post(
        "/api/v1/users/user-001/recommendations/rec-001/feedback",
        json=_feedback_payload(),
    )
    missing = client.post(
        "/api/v1/users/user-001/recommendations/missing/feedback",
        json=_feedback_payload(),
    )

    assert cross_user.status_code == missing.status_code == 404
    assert cross_user.json() == missing.json() == {"detail": "recommendation_not_found"}


def test_feedback_records_without_memory_when_disabled_or_profile_missing(monkeypatch):
    for enabled in (False, None):
        client, memory_calls, log_updates = _feedback_client(
            monkeypatch, profile_enabled=enabled
        )

        response = client.post(
            "/api/v1/users/user-001/recommendations/rec-001/feedback",
            json=_feedback_payload(),
        )

        assert response.status_code == 200
        assert response.json()["memory_persisted"] is False
        assert memory_calls == []
        assert log_updates[-1][0][4] is False
