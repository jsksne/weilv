"""Today read-back endpoint: same-day recommendation sessions restore
saved task snapshots, task action events and feedback (spec F4)."""

from fastapi.testclient import TestClient


def _today_client(monkeypatch, *, logs):
    from weilv.api import app as api
    from weilv.api import today_queries

    monkeypatch.setattr(
        today_queries,
        "list_recommendation_logs_for_day",
        lambda _client, user_id, start_at, end_at: logs,
    )
    monkeypatch.setattr(
        today_queries,
        "load_formal_micro_tasks",
        lambda: [
            {
                "task_id": "MT-SED-001",
                "title": "正式站姿任务",
                "instruction": "正式指令",
                "estimated_minutes": 5,
                "covered_domains": ["sedentary"],
            }
        ],
    )
    api.app.state.es_client = object()
    api.app.state.api_key = "server-key"
    return TestClient(api.app)


def test_today_restores_saved_sessions_with_actions_and_feedback(monkeypatch):
    logs = [
        {
            "recommendation_id": "rec-1",
            "user_id": "user-001",
            "status": "allowed",
            "selected_task_id": "MT-SED-001",
            "task": {
                "task_id": "MT-SED-001",
                "title": "站起来伸展",
                "instruction": "照做即可",
                "estimated_minutes": 5,
                "covered_domains": ["sedentary"],
                "sources": [],
            },
            "created_at": "2026-09-05T01:00:00+00:00",
            "task_events": [
                {"action": "started", "recorded_at": "2026-09-05T01:01:00+00:00"},
                {"action": "completed", "recorded_at": "2026-09-05T01:02:00+00:00"},
            ],
            "feedback": None,
        }
    ]
    client = _today_client(monkeypatch, logs=logs)

    response = client.get("/api/v1/users/user-001/today")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "user-001"
    assert len(body["sessions"]) == 1
    session = body["sessions"][0]
    assert session["recommendation_id"] == "rec-1"
    assert session["task_id"] == "MT-SED-001"
    assert session["title"] == "站起来伸展"
    assert session["instruction"] == "照做即可"
    assert session["estimated_minutes"] == 5
    assert [event["action"] for event in session["actions"]] == ["started", "completed"]
    assert session["feedback"] is None


def test_today_falls_back_to_formal_metadata_and_skips_unrestorable(monkeypatch):
    logs = [
        {
            "recommendation_id": "rec-old",
            "user_id": "user-001",
            "selected_task_id": "MT-SED-001",
            "created_at": "2026-09-05T02:00:00+00:00",
        },
        {
            "recommendation_id": "rec-broken",
            "user_id": "user-001",
            "selected_task_id": "MT-GONE",
            "created_at": "2026-09-05T03:00:00+00:00",
        },
    ]
    client = _today_client(monkeypatch, logs=logs)

    body = client.get("/api/v1/users/user-001/today").json()

    assert [session["recommendation_id"] for session in body["sessions"]] == ["rec-old"]
    assert body["sessions"][0]["title"] == "正式站姿任务"
    assert body["sessions"][0]["estimated_minutes"] == 5


def test_today_date_param_uses_utc_day_boundaries(monkeypatch):
    from weilv.api import app as api
    from weilv.api import today_queries

    seen = {}

    def fake_list(_client, user_id, start_at, end_at):
        seen["range"] = (user_id, start_at, end_at)
        return []

    monkeypatch.setattr(today_queries, "list_recommendation_logs_for_day", fake_list)
    monkeypatch.setattr(today_queries, "load_formal_micro_tasks", lambda: [])
    api.app.state.es_client = object()
    api.app.state.api_key = "server-key"
    client = TestClient(api.app)

    response = client.get("/api/v1/users/user-001/today", params={"date": "2026-09-01"})

    assert response.status_code == 200
    user_id, start_at, end_at = seen["range"]
    assert user_id == "user-001"
    assert start_at.startswith("2026-09-01T00:00:00")
    assert end_at.startswith("2026-09-02T00:00:00")


def test_today_rejects_invalid_date_param(monkeypatch):
    client = _today_client(monkeypatch, logs=[])

    response = client.get("/api/v1/users/user-001/today", params={"date": "not-a-date"})

    assert response.status_code == 422


def test_recommendation_log_stores_restorable_task_snapshot(monkeypatch):
    from weilv.api import app as api

    rag_result = {
        "status": "allowed",
        "selected_task": {
            "task_id": "MT-SED-001",
            "title": "站起来伸展",
            "instruction": "照做即可",
            "estimated_minutes": 5,
            "covered_domains": ["sedentary"],
        },
        "explanation": "解释",
        "sources": [],
        "matched_rule_ids": [],
        "reason_codes": [],
    }
    log_calls = []
    monkeypatch.setattr(api, "run_personal_rag", lambda *args, **kwargs: rag_result)
    monkeypatch.setattr(
        api,
        "create_recommendation_log",
        lambda *args, **kwargs: log_calls.append(args[1]),
        raising=False,
    )
    api.app.state.es_client = object()
    api.app.state.api_key = "server-key"
    client = TestClient(api.app)

    response = client.post(
        "/api/v1/recommendations",
        json={
            "user_id": "user-001",
            "query": "推荐一个微任务",
            "target_stage": "junior_high",
            "current_context": "home",
        },
    )

    assert response.status_code == 200
    assert len(log_calls) == 1
    snapshot = log_calls[0]["task"]
    assert snapshot["task_id"] == "MT-SED-001"
    assert snapshot["title"] == "站起来伸展"
    assert snapshot["estimated_minutes"] == 5
