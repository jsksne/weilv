"""Memory list / delete API tests (Backend Gate B4).

List is a read-only query adapter; delete delegates to forget_memory().
No new Memory writes, no feedback / RAG involvement.
"""

from fastapi.testclient import TestClient

from weilv.user_memory import UserProfile

MEMORY_DOC = {
    "memory_id": "UM-1",
    "user_id": "user-001",
    "memory_type": "task_feedback",
    "source_type": "structured_task_feedback",
    "task_id": "MT-SED-001",
    "domain": None,
    "memory_key": "",
    "memory_value": {
        "completion_status": "completed",
        "helpfulness": 5,
        "burden": "easy",
        "confidence": 1,
    },
    "created_at": "2026-08-20T10:00:00+00:00",
    "updated_at": "2026-08-20T10:00:00+00:00",
    "retrieval_text": "type=task_feedback task=MT-SED-001 completion=completed",
    "active": True,
    "review_status": "valid",
    "embedding": [0.1, 0.2],
    "raw_query": "must-not-leak",
}


class FakeElasticsearch:
    def __init__(self, memories):
        self.documents = {m["memory_id"]: dict(m) for m in memories}
        self.searches = []

    def search(self, **kwargs):
        self.searches.append(kwargs)
        term = kwargs["query"]["bool"]["filter"][0]["term"]
        field, value = next(iter(term.items()))
        hits = [
            {"_source": source} for source in self.documents.values() if source.get(field) == value
        ]
        return {"hits": {"hits": hits}}


def _memory_client(monkeypatch, *, profile_enabled=True, memories=()):
    from weilv.api import app as api

    profile = (
        UserProfile("user-001", "junior_high", profile_enabled, "created", "updated")
        if profile_enabled is not None
        else None
    )
    es = FakeElasticsearch(memories)
    monkeypatch.setattr(api, "get_user_profile", lambda _client, user_id: profile)
    api.app.state.es_client = es
    return TestClient(api.app), es


def test_memory_list_returns_only_ui_fields_for_own_memories(monkeypatch):
    client, es = _memory_client(
        monkeypatch,
        memories=[
            MEMORY_DOC,
            {
                **MEMORY_DOC,
                "memory_id": "UM-2",
                "user_id": "user-002",
                "memory_type": "user_constraint",
            },
        ],
    )

    response = client.get("/api/v1/users/user-001/memories")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "user-001"
    assert body["memory_enabled"] is True
    assert [item["memory_id"] for item in body["memories"]] == ["UM-1"]
    item = body["memories"][0]
    assert set(item) == {"memory_id", "memory_type", "summary", "created_at", "updated_at"}
    assert "已完成" in item["summary"]
    assert "帮助度：5/5" in item["summary"]
    # sensitive / internal fields must never reach the response
    for forbidden in ("embedding", "retrieval_text", "memory_value", "raw_query", "active"):
        assert forbidden not in item and forbidden not in body
    # ownership enforced server-side by the user_id term filter
    assert es.searches[0]["query"]["bool"]["filter"][0]["term"] == {"user_id": "user-001"}
    assert es.searches[0]["source_excludes"] == ["embedding", "retrieval_text"]


def test_memory_list_reports_consent_state_without_enabling_memory(monkeypatch):
    for enabled in (False, None):
        client, _ = _memory_client(monkeypatch, profile_enabled=enabled)

        response = client.get("/api/v1/users/user-001/memories")

        assert response.status_code == 200
        assert response.json()["memory_enabled"] is False
        assert response.json()["memories"] == []


def test_memory_list_touches_no_writes(monkeypatch):
    from weilv.api import app as api

    calls = {"memory_writes": [], "feedback": [], "rag": []}
    client, _ = _memory_client(monkeypatch, memories=[MEMORY_DOC])
    monkeypatch.setattr(api, "create_memory", lambda *_a, **_k: calls["memory_writes"].append(1))
    monkeypatch.setattr(api, "update_memory", lambda *_a, **_k: calls["memory_writes"].append(1))
    monkeypatch.setattr(api, "forget_memory", lambda *_a, **_k: calls["memory_writes"].append(1))
    monkeypatch.setattr(
        api, "persist_task_feedback_memory", lambda *_a, **_k: calls["feedback"].append(1)
    )
    monkeypatch.setattr(api, "run_personal_rag", lambda *_a, **_k: calls["rag"].append(1))
    monkeypatch.setattr(api, "run_agentic_rag", lambda *_a, **_k: calls["rag"].append(1))

    response = client.get("/api/v1/users/user-001/memories")

    assert response.status_code == 200
    assert calls == {"memory_writes": [], "feedback": [], "rag": []}


def _delete_client(monkeypatch):
    from weilv.api import app as api

    owner_of = {"mem-1": "user-001", "mem-2": "user-002"}
    delete_calls = []
    monkeypatch.setattr(
        api,
        "forget_memory",
        lambda _client, user_id, memory_id: (
            delete_calls.append((user_id, memory_id))
            or (
                {"status": "forgotten", "memory_id": memory_id}
                if owner_of.get(memory_id) == user_id
                else (
                    {
                        "status": "rejected",
                        "memory_id": memory_id,
                        "reason_code": "memory_owner_mismatch",
                    }
                    if memory_id in owner_of
                    else {"status": "not_found", "memory_id": memory_id}
                )
            )
        ),
    )
    api.app.state.es_client = object()
    return TestClient(api.app), delete_calls


def test_delete_own_memory_succeeds_via_forget_memory(monkeypatch):
    client, delete_calls = _delete_client(monkeypatch)

    response = client.post("/api/v1/users/user-001/memories/mem-1/delete")

    assert response.status_code == 200
    assert response.json() == {"status": "forgotten", "memory_id": "mem-1"}
    assert delete_calls == [("user-001", "mem-1")]


def test_delete_missing_memory_returns_404(monkeypatch):
    client, delete_calls = _delete_client(monkeypatch)

    response = client.post("/api/v1/users/user-001/memories/missing/delete")

    assert response.status_code == 404
    assert response.json() == {"detail": "memory_not_found"}
    assert delete_calls == [("user-001", "missing")]


def test_delete_another_users_memory_is_rejected_as_404(monkeypatch):
    client, delete_calls = _delete_client(monkeypatch)

    response = client.post("/api/v1/users/user-001/memories/mem-2/delete")

    assert response.status_code == 404
    assert response.json() == {"detail": "memory_not_found"}
    assert delete_calls == [("user-001", "mem-2")]
