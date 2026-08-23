from fastapi.testclient import TestClient


def _payload():
    return {
        "user_id": "agentic-user-001",
        "query": "连续写作业后只剩5分钟，快到睡觉时间，也不想活动",
        "target_stage": "junior_high",
        "current_context": "home",
        "activity_context": "writing",
        "available_minutes": 5,
        "vision_abnormal": False,
        "physical_discomfort": False,
        "medical_request": False,
        "cannot_move": False,
        "unstable_environment": False,
        "sleep_being_crowded": True,
    }


def test_agentic_endpoint_is_separate_compatible_and_logs_no_health_text(monkeypatch):
    from weilv.api import app as api

    result = {
        "status": "allowed",
        "selected_task": {"task_id": "MT-SED-001", "instruction": "正式指令"},
        "explanation": "解释",
        "sources": [{"chunk_id": "KC-1"}],
        "context_sources": [{"chunk_id": "KC-2"}],
        "matched_rule_ids": [],
        "reason_codes": [],
        "explanation_guard": {"passed": True, "fallback_used": False, "reason_codes": []},
        "agentic": True,
        "diagnostics": {
            "factor_count": 3,
            "factor_domains": ["study_break", "sleep", None],
            "analysis_fallback": False,
            "memory_hit_count": 0,
            "selected_task_id": "MT-SED-001",
            "model_calls": {"decomposition": 1, "explanation": 1},
        },
    }
    core_calls = []
    log_calls = []
    monkeypatch.setattr(
        api,
        "run_agentic_rag",
        lambda *args, **kwargs: core_calls.append((args, kwargs)) or result,
        raising=False,
    )
    monkeypatch.setattr(
        api,
        "create_recommendation_log",
        lambda *args, **kwargs: log_calls.append((args, kwargs)),
    )
    api.app.state.es_client = object()
    api.app.state.api_key = "server-key"

    response = TestClient(api.app).post("/api/v1/recommend/agentic", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["agentic"] is True
    assert body["diagnostics"] == result["diagnostics"]
    assert body["recommendation_id"]
    assert body["feedback_available"] is True
    assert len(core_calls) == 1
    request, user_id, es_client, api_key = core_calls[0][0]
    assert request.query == _payload()["query"]
    assert (user_id, es_client, api_key) == (
        "agentic-user-001",
        TestClient(api.app).app.state.es_client,
        "server-key",
    )
    session = log_calls[0][0][1]
    assert session["agentic"] is True
    assert session["factor_count"] == 3
    assert session["memory_hit"] is False
    assert "query" not in session
    assert "factors" not in session
    assert "memory" not in session

