"""Backend Gate B1: same-run Top-3 recommendation exposure tests.

Verifies the narrow frozen-core authorization: existing ranking and Safety
semantics are untouched, rank 1 identity is preserved (old selected_task ==
new tasks[0]), ranks 2+ reuse the exact same evidence grounding gate, no extra
LLM / retrieval runs, and each surfaced task gets an independent
recommendation_id usable by the B2 events endpoint.
"""

from fastapi.testclient import TestClient


def _request(**overrides):
    from weilv.basic_rag import BasicRagRequest

    request = BasicRagRequest(
        query="我写作业快一个小时了，现在有10分钟休息。",
        target_stage="junior_high",
        current_context="home",
        available_minutes=10,
    )
    from dataclasses import replace

    return replace(request, **overrides)


def _task(task_id, minutes):
    return {
        "task_id": task_id,
        "title": f"title-{task_id}",
        "instruction": f"instruction-{task_id}",
        "evidence_chunk_ids": [f"KC-{task_id}"],
        "covered_domains": ["sedentary"],
        "estimated_minutes": minutes,
    }


def _evidence_for(task):
    return [
        {
            "chunk_id": f"KC-{task['task_id']}",
            "document_id": "SRC-1",
            "source_locator": "source:L1",
            "source_url": "https://example.test",
        }
    ]


def _basic_state(tasks):
    return {
        "result": None,
        "query_embedding": [0.1] * 1024,
        "knowledge": [],
        "safe_result": {"matched_rule_ids": [], "reason_codes": []},
        "reranked_tasks": tasks,
    }


def _run_basic(monkeypatch, tasks, evidence=None):
    from weilv import basic_rag

    monkeypatch.setattr(basic_rag, "_run_basic_pipeline", lambda *_a, **_k: _basic_state(tasks))
    monkeypatch.setattr(
        basic_rag,
        "load_task_evidence",
        lambda _client, task, _index: (evidence or _evidence_for)(task),
    )
    monkeypatch.setattr(basic_rag, "load_formal_task_identities", lambda *_a: tasks)
    monkeypatch.setattr(basic_rag, "explain_selected_task", lambda *_a, **_k: "安全解释")
    return basic_rag.run_basic_rag(_request(), object(), "key")


def test_rank1_regression_selected_task_equals_tasks0_and_returns_three(monkeypatch):
    tasks = [_task("A", 5), _task("B", 10), _task("C", 15)]

    result = _run_basic(monkeypatch, tasks)

    assert result["status"] == "allowed"
    assert result["selected_task"]["task_id"] == "A"
    assert [item["task_id"] for item in result["tasks"]] == ["A", "B", "C"]
    first = result["tasks"][0]
    assert first["task_id"] == result["selected_task"]["task_id"]
    assert first["title"] == result["selected_task"]["title"]
    assert first["instruction"] == result["selected_task"]["instruction"]
    assert first["estimated_minutes"] == result["selected_task"]["estimated_minutes"]
    # minimal display contract: no ranking internals / raw query / embeddings
    assert set(first) == {
        "task_id",
        "title",
        "instruction",
        "estimated_minutes",
        "covered_domains",
        "sources",
    }
    # candidate ids remain unique
    assert len({item["task_id"] for item in result["tasks"]}) == 3


def test_only_two_candidates_returns_two_without_fabrication(monkeypatch):
    result = _run_basic(monkeypatch, [_task("A", 5), _task("B", 10)])

    assert [item["task_id"] for item in result["tasks"]] == ["A", "B"]


def test_rank2_evidence_invalid_is_skipped_without_reordering(monkeypatch):
    tasks = [_task("A", 5), _task("B", 10), _task("C", 15)]

    def evidence(task):
        if task["task_id"] == "B":
            return []
        return _evidence_for(task)

    result = _run_basic(monkeypatch, tasks, evidence=evidence)

    assert [item["task_id"] for item in result["tasks"]] == ["A", "C"]


def test_rank1_evidence_invalid_preserves_existing_no_safe_task_semantics(monkeypatch):
    tasks = [_task("A", 5), _task("B", 10)]

    def evidence(task):
        if task["task_id"] == "A":
            return []
        return _evidence_for(task)

    result = _run_basic(monkeypatch, tasks, evidence=evidence)

    assert result["status"] == "no_safe_task"
    assert result["selected_task"] is None
    assert "tasks" not in result
    assert result["reason_codes"] == ["selected_task_evidence_invalid"]


def test_help_seeking_and_no_safe_task_return_no_tasks(monkeypatch):
    from weilv import basic_rag

    blocked = {
        "status": "help_seeking",
        "selected_task": None,
        "explanation": None,
        "sources": [],
        "matched_rule_ids": ["SR-001"],
        "reason_codes": ["vision_abnormal_help_seeking"],
    }
    no_safe = {
        "status": "no_safe_task",
        "selected_task": None,
        "explanation": None,
        "sources": [],
        "matched_rule_ids": ["SR-012"],
        "reason_codes": ["no_safe_whitelist_task"],
    }
    for blocked_result in (blocked, no_safe):
        monkeypatch.setattr(
            basic_rag,
            "_run_basic_pipeline",
            lambda *_a, blocked_result=blocked_result, **_k: {"result": blocked_result},
        )
        result = basic_rag.run_basic_rag(_request(), object(), "key")

        assert result["status"] in {"help_seeking", "no_safe_task"}
        assert result["selected_task"] is None
        assert "tasks" not in result


def test_three_surfaced_tasks_still_call_explanation_once(monkeypatch):
    from weilv import basic_rag

    tasks = [_task("A", 5), _task("B", 10), _task("C", 15)]
    explanation_calls = []
    monkeypatch.setattr(basic_rag, "_run_basic_pipeline", lambda *_a, **_k: _basic_state(tasks))
    monkeypatch.setattr(
        basic_rag, "load_task_evidence", lambda _client, task, _index: _evidence_for(task)
    )
    monkeypatch.setattr(basic_rag, "load_formal_task_identities", lambda *_a: tasks)
    monkeypatch.setattr(
        basic_rag,
        "explain_selected_task",
        lambda *_a, **_k: explanation_calls.append(1) or "安全解释",
    )

    result = basic_rag.run_basic_rag(_request(), object(), "key")

    assert result["status"] == "allowed"
    assert len(result["tasks"]) == 3
    assert len(explanation_calls) == 1


def test_surfacing_adds_no_retrieval_or_embedding_calls(monkeypatch):
    from weilv import basic_rag

    tasks = [_task("A", 5), _task("B", 10), _task("C", 15)]

    def forbidden(*_args, **_kwargs):
        raise AssertionError("surfacing must not re-run retrieval or models")

    monkeypatch.setattr(basic_rag, "_run_basic_pipeline", lambda *_a, **_k: _basic_state(tasks))
    monkeypatch.setattr(
        basic_rag, "load_task_evidence", lambda _client, task, _index: _evidence_for(task)
    )
    monkeypatch.setattr(basic_rag, "load_formal_task_identities", lambda *_a: tasks)
    monkeypatch.setattr(basic_rag, "explain_selected_task", lambda *_a, **_k: "安全解释")
    monkeypatch.setattr(basic_rag, "embed_texts", forbidden)
    monkeypatch.setattr(basic_rag, "rerank_texts", forbidden)
    monkeypatch.setattr(basic_rag, "bm25_search", forbidden)
    monkeypatch.setattr(basic_rag, "vector_search", forbidden)

    result = basic_rag.run_basic_rag(_request(), object(), "key")

    assert result["status"] == "allowed"
    assert len(result["tasks"]) == 3


def test_personal_top3_preserves_personalized_order_and_rank1_identity(monkeypatch):
    from weilv import basic_rag, personal_rag
    from weilv.user_memory import UserProfile

    tasks = [_task("A", 5), _task("B", 10), _task("C", 15)]
    memory = {
        "memory_id": "prefer-C",
        "memory_type": "task_preference",
        "task_id": "C",
        "memory_key": "prefer_task",
        "memory_value": {"preference": "prefer_task"},
    }
    monkeypatch.setattr(personal_rag, "_run_basic_pipeline", lambda *_a, **_k: _basic_state(tasks))
    monkeypatch.setattr(
        personal_rag,
        "get_user_profile",
        lambda *_a: UserProfile("user", "junior_high", True, "created", "updated"),
    )
    monkeypatch.setattr(personal_rag, "retrieve_personal_memories", lambda *_a, **_k: [memory])
    monkeypatch.setattr(
        personal_rag,
        "_finalize_selected_task",
        lambda _req, task, *_a, **_k: {
            "status": "allowed",
            "selected_task": task,
            "explanation": "e",
            "sources": _evidence_for(task),
        },
    )
    monkeypatch.setattr(
        basic_rag, "load_task_evidence", lambda _client, task, _index: _evidence_for(task)
    )

    result = personal_rag.run_personal_rag(_request(), "user", object(), "key")

    assert result["selected_task"]["task_id"] == "C"
    assert [item["task_id"] for item in result["tasks"]] == ["C", "A", "B"]
    assert result["tasks"][0]["task_id"] == result["selected_task"]["task_id"]


def _api_result():
    return {
        "status": "allowed",
        "selected_task": {
            "task_id": "MT-A",
            "title": "t-a",
            "instruction": "i-a",
            "estimated_minutes": 5,
        },
        "explanation": "e",
        "sources": [{"chunk_id": "KC-1"}],
        "context_sources": [],
        "matched_rule_ids": [],
        "reason_codes": [],
        "explanation_guard": {"passed": True, "fallback_used": False, "reason_codes": []},
        "tasks": [
            {
                "task_id": "MT-A",
                "title": "t-a",
                "instruction": "i-a",
                "estimated_minutes": 5,
                "sources": [],
            },
            {
                "task_id": "MT-B",
                "title": "t-b",
                "instruction": "i-b",
                "estimated_minutes": 10,
                "sources": [],
            },
            {
                "task_id": "MT-C",
                "title": "t-c",
                "instruction": "i-c",
                "estimated_minutes": 15,
                "sources": [],
            },
        ],
    }


def _api_payload():
    return {
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


def _b1_api_client(monkeypatch, *, rag_result=None):
    from weilv.api import app as api

    sessions = {}
    log_calls = []
    event_updates = []

    def create_log(*args):
        session = args[1]
        sessions[session["recommendation_id"]] = session
        log_calls.append(session)

    def get_log(_client, user_id, rec_id):
        session = sessions.get(rec_id)
        return session if session and session["user_id"] == user_id else None

    def append_event(_client, session, event):
        event_updates.append((session, event))

    monkeypatch.setattr(
        api, "run_personal_rag", lambda *_a, **_k: dict(rag_result or _api_result())
    )
    monkeypatch.setattr(api, "create_recommendation_log", create_log, raising=False)
    monkeypatch.setattr(api, "get_recommendation_log", get_log, raising=False)
    monkeypatch.setattr(api, "append_task_event", append_event, raising=False)
    api.app.state.es_client = object()
    api.app.state.api_key = "server-key"
    return TestClient(api.app), sessions, log_calls, event_updates


def test_api_three_tasks_get_independent_ids_and_b2_events_target_each(monkeypatch):
    client, _sessions, log_calls, event_updates = _b1_api_client(monkeypatch)

    recommendation = client.post("/api/v1/recommendations", json=_api_payload())

    assert recommendation.status_code == 200
    body = recommendation.json()
    rec_ids = [task["recommendation_id"] for task in body["tasks"]]
    assert len(set(rec_ids)) == 3
    assert body["recommendation_id"] == rec_ids[0]
    assert body["feedback_available"] is True
    assert len(log_calls) == 3
    by_task = {session["selected_task_id"]: session for session in log_calls}
    assert set(by_task) == {"MT-A", "MT-B", "MT-C"}
    assert by_task["MT-A"]["recommendation_id"] == rec_ids[0]

    started = client.post(
        f"/api/v1/users/user-001/recommendations/{rec_ids[1]}/events",
        json={"action": "started"},
    )
    skipped = client.post(
        f"/api/v1/users/user-001/recommendations/{rec_ids[2]}/events",
        json={"action": "skipped"},
    )

    assert started.status_code == skipped.status_code == 200
    assert event_updates[0][0]["selected_task_id"] == "MT-B"
    assert event_updates[0][1]["action"] == "started"
    assert event_updates[1][0]["selected_task_id"] == "MT-C"
    assert event_updates[1][1]["action"] == "skipped"
    assert "task_events" not in by_task["MT-A"]


def test_api_b2_event_on_other_user_rejected_for_surfaced_task(monkeypatch):
    client, _, _, _ = _b1_api_client(monkeypatch)

    recommendation = client.post("/api/v1/recommendations", json=_api_payload())
    rec_ids = [task["recommendation_id"] for task in recommendation.json()["tasks"]]

    cross = client.post(
        f"/api/v1/users/user-002/recommendations/{rec_ids[1]}/events",
        json={"action": "started"},
    )

    assert cross.status_code == 404
    assert cross.json() == {"detail": "recommendation_not_found"}


def test_api_help_seeking_returns_no_tasks_and_no_logs(monkeypatch):
    client, _, log_calls, _ = _b1_api_client(
        monkeypatch,
        rag_result={
            "status": "help_seeking",
            "selected_task": None,
            "explanation": None,
            "sources": [],
            "matched_rule_ids": ["SR-001"],
            "reason_codes": ["vision_abnormal_help_seeking"],
        },
    )

    response = client.post(
        "/api/v1/recommendations",
        json=_api_payload(),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "help_seeking"
    assert response.json()["selected_task"] is None
    assert response.json().get("tasks") is None
    assert log_calls == []


def test_api_log_failure_disables_feedback_for_all_tasks(monkeypatch):
    from weilv.api import app as api

    client, _, _, _ = _b1_api_client(monkeypatch)
    monkeypatch.setattr(
        api,
        "create_recommendation_log",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("log unavailable")),
    )

    response = client.post("/api/v1/recommendations", json=_api_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation_id"] is None
    assert body["feedback_available"] is False
    assert all(task["recommendation_id"] is None for task in body["tasks"])
