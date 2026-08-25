"""Task action event API tests (Backend Gate B2).

Task action events are faithful records of user actions. They must stay
separate from Feedback: no usefulness / difficulty / reason, no Memory
writes, no RAG calls, no re-ranking.
"""

from fastapi.testclient import TestClient

ALL_ACTIONS = (
    "started",
    "completed",
    "partially_completed",
    "skipped",
    "replaced",
    "restored",
)


def _event_client(monkeypatch, *, session_user="user-001"):
    from weilv.api import app as api

    session = {
        "recommendation_id": "rec-001",
        "user_id": session_user,
        "status": "allowed",
        "selected_task_id": "MT-SED-001",
    }
    updates = []
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
    monkeypatch.setattr(
        api,
        "append_task_event",
        lambda _client, session, event: updates.append((session, event)),
        raising=False,
    )
    api.app.state.es_client = object()
    return TestClient(api.app), session, updates


def test_all_six_task_actions_are_recorded_without_feedback_or_memory(monkeypatch):
    client, session, updates = _event_client(monkeypatch)

    for action in ALL_ACTIONS:
        response = client.post(
            "/api/v1/users/user-001/recommendations/rec-001/events",
            json={"action": action},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "recorded"
        assert body["recommendation_id"] == "rec-001"
        assert body["task_id"] == "MT-SED-001"
        assert body["action"] == action
        assert body["recorded_at"]

    assert len(updates) == 6
    for (stored_session, event), action in zip(updates, ALL_ACTIONS):
        assert stored_session is session
        assert event["action"] == action
        assert event["recorded_at"]
        assert set(event) == {"action", "recorded_at"}


def test_event_recording_touches_no_feedback_memory_or_rag(monkeypatch):
    from weilv.api import app as api

    calls = {"feedback": [], "memory": [], "rag": []}
    client, _, _ = _event_client(monkeypatch)
    monkeypatch.setattr(api, "run_personal_rag", lambda *_a, **_k: calls["rag"].append(1))
    monkeypatch.setattr(api, "run_agentic_rag", lambda *_a, **_k: calls["rag"].append(1))
    monkeypatch.setattr(
        api, "persist_task_feedback_memory", lambda *_a, **_k: calls["feedback"].append(1)
    )
    monkeypatch.setattr(api, "create_memory", lambda *_a, **_k: calls["memory"].append(1))
    monkeypatch.setattr(api, "update_memory", lambda *_a, **_k: calls["memory"].append(1))

    response = client.post(
        "/api/v1/users/user-001/recommendations/rec-001/events",
        json={"action": "completed"},
    )

    assert response.status_code == 200
    assert calls == {"feedback": [], "memory": [], "rag": []}


def test_event_schema_rejects_invalid_action_and_feedback_fields(monkeypatch):
    client, _, updates = _event_client(monkeypatch)

    for payload in (
        {"action": "snoozed"},
        {"action": "completed", "usefulness": "helpful"},
        {"action": "completed", "difficulty": "easy"},
        {"action": "completed", "reason": "因为它对我没用"},
        {"action": "completed", "api_key": "client-key"},
    ):
        response = client.post(
            "/api/v1/users/user-001/recommendations/rec-001/events",
            json=payload,
        )
        assert response.status_code == 422

    assert updates == []


def test_event_requires_action_field(monkeypatch):
    client, _, updates = _event_client(monkeypatch)

    response = client.post(
        "/api/v1/users/user-001/recommendations/rec-001/events",
        json={},
    )

    assert response.status_code == 422
    assert updates == []


def test_missing_and_cross_user_recommendations_return_404(monkeypatch):
    client, _, updates = _event_client(monkeypatch, session_user="user-B")

    cross_user = client.post(
        "/api/v1/users/user-001/recommendations/rec-001/events",
        json={"action": "started"},
    )
    missing = client.post(
        "/api/v1/users/user-001/recommendations/missing/events",
        json={"action": "started"},
    )

    assert cross_user.status_code == missing.status_code == 404
    assert cross_user.json() == missing.json() == {"detail": "recommendation_not_found"}
    assert updates == []


def test_duplicate_actions_are_allowed_like_existing_log_semantics(monkeypatch):
    client, _, updates = _event_client(monkeypatch)

    for _ in range(2):
        response = client.post(
            "/api/v1/users/user-001/recommendations/rec-001/events",
            json={"action": "started"},
        )
        assert response.status_code == 200

    assert [event["action"] for _, event in updates] == ["started", "started"]


def test_append_task_event_accumulates_on_interaction_log_without_feedback_fields():
    from elasticsearch import NotFoundError

    from weilv.api.task_events import append_task_event
    from weilv.interaction_logs import create_recommendation_log, get_recommendation_log

    class FakeClient:
        def __init__(self):
            self.documents = {}

        def create(self, *, index, id, document):
            self.documents[(index, id)] = dict(document)

        def get(self, *, index, id):
            try:
                return {"_source": dict(self.documents[(index, id)])}
            except KeyError as error:
                raise NotFoundError("not found", meta=None, body=None) from error

        def update(self, *, index, id, doc, refresh=None):
            self.documents[(index, id)].update(doc)

    client = FakeClient()
    session = {
        "recommendation_id": "rec-1",
        "user_id": "user-A",
        "selected_task_id": "MT-SED-001",
        "feedback": None,
    }
    create_recommendation_log(client, session)

    append_task_event(client, session, {"action": "started", "recorded_at": "t1"})
    append_task_event(
        client,
        get_recommendation_log(client, "user-A", "rec-1"),
        {"action": "completed", "recorded_at": "t2"},
    )

    stored = get_recommendation_log(client, "user-A", "rec-1")
    assert stored["task_events"] == [
        {"action": "started", "recorded_at": "t1"},
        {"action": "completed", "recorded_at": "t2"},
    ]
    assert stored["feedback"] is None
    assert "usefulness" not in stored and "difficulty" not in stored
    assert "memory_persisted" not in stored
