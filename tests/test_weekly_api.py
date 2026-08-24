"""Weekly read-only aggregation API tests (Backend Gate B5).

Aggregation is deterministic-only: interaction logs + B2 task action events +
formal task metadata. No LLM / RAG / Memory / Feedback involvement; missing
task durations are never guessed.
"""

from fastapi.testclient import TestClient

CONTROLLED_TASKS = [
    {"task_id": "MT-BREAK-001", "title": "远眺休息", "estimated_minutes": 10},
    {"task_id": "MT-SED-001", "title": "静态拉伸", "estimated_minutes": 5},
]


def _log(recommendation_id, task_id, events, user_id="user-001"):
    return {
        "recommendation_id": recommendation_id,
        "user_id": user_id,
        "status": "allowed",
        "selected_task_id": task_id,
        "created_at": "2026-08-20T09:00:00+00:00",
        "task_events": events,
    }


class FakeElasticsearch:
    def __init__(self, logs):
        self.logs = logs
        self.searches = []

    def search(self, **kwargs):
        self.searches.append(kwargs)
        term = kwargs["query"]["bool"]["filter"][0]["term"]
        field, value = next(iter(term.items()))
        hits = [{"_source": log} for log in self.logs if log.get(field) == value]
        return {"hits": {"hits": hits}}


def _weekly_client(monkeypatch, *, logs=()):
    from weilv.api import app as api
    from weilv.api import weekly_queries

    es = FakeElasticsearch(list(logs))
    monkeypatch.setattr(weekly_queries, "load_formal_micro_tasks", lambda: list(CONTROLLED_TASKS))
    api.app.state.es_client = es
    return TestClient(api.app), es


def _weekly_url(start, end):
    return f"/api/v1/users/user-001/weekly?start_date={start}&end_date={end}"


def test_weekly_aggregates_daily_minutes_counts_and_adjustments(monkeypatch):
    logs = [
        _log(
            "rec-1",
            "MT-BREAK-001",
            [
                {"action": "started", "recorded_at": "2026-08-20T09:00:00+00:00"},
                {"action": "completed", "recorded_at": "2026-08-20T09:10:00+00:00"},
            ],
        ),
        _log(
            "rec-2",
            "MT-SED-001",
            [
                {"action": "started", "recorded_at": "2026-08-21T09:00:00+00:00"},
                {"action": "skipped", "recorded_at": "2026-08-21T09:05:00+00:00"},
            ],
        ),
        _log(
            "rec-3",
            "MT-BREAK-001",
            [
                {"action": "replaced", "recorded_at": "2026-08-22T08:00:00+00:00"},
                {"action": "restored", "recorded_at": "2026-08-22T08:30:00+00:00"},
            ],
        ),
        _log(
            "rec-4",
            "MT-SED-001",
            [
                {"action": "completed", "recorded_at": "2026-08-22T10:00:00+00:00"},
                {"action": "partially_completed", "recorded_at": "2026-08-22T10:05:00+00:00"},
            ],
        ),
    ]
    client, es = _weekly_client(monkeypatch, logs=logs)

    response = client.get(_weekly_url("2026-08-20", "2026-08-26"))

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "user-001"
    assert body["start_date"] == "2026-08-20" and body["end_date"] == "2026-08-26"
    assert body["minutes_policy"] == "official_estimated_minutes_only"
    assert len(body["days"]) == 7
    by_date = {day["date"]: day for day in body["days"]}
    assert by_date["2026-08-20"]["completed_minutes"] == 10
    assert by_date["2026-08-20"]["action_counts"]["completed"] == 1
    assert by_date["2026-08-21"]["action_counts"]["skipped"] == 1
    assert by_date["2026-08-21"]["completed_minutes"] == 0
    assert by_date["2026-08-22"]["completed_minutes"] == 5  # only completed, not partial
    assert by_date["2026-08-22"]["action_counts"]["replaced"] == 1
    assert by_date["2026-08-22"]["action_counts"]["restored"] == 1
    assert by_date["2026-08-22"]["action_counts"]["partially_completed"] == 1
    assert by_date["2026-08-23"]["action_counts"] == {
        "started": 0,
        "completed": 0,
        "partially_completed": 0,
        "skipped": 0,
        "replaced": 0,
        "restored": 0,
    }
    assert body["totals"]["completed_minutes"] == 15
    assert body["totals"]["action_counts"]["completed"] == 2
    assert body["totals"]["action_counts"]["started"] == 2
    assert body["totals"]["action_counts"]["skipped"] == 1
    assert body["totals"]["action_counts"]["replaced"] == 1
    assert body["totals"]["action_counts"]["restored"] == 1
    # task action history: all six-actions semantics present, sorted by time
    assert [event["action"] for event in body["events"]] == [
        "started",
        "completed",
        "started",
        "skipped",
        "replaced",
        "restored",
        "completed",
        "partially_completed",
    ]
    # adjustment timeline is the replaced/restored subset
    assert [event["action"] for event in body["adjustments"]] == ["replaced", "restored"]
    assert body["adjustments"][0]["title"] == "远眺休息"
    # ownership enforced by the user_id term filter
    assert es.searches[0]["query"]["bool"]["filter"][0]["term"] == {"user_id": "user-001"}


def test_weekly_partial_range_only_includes_events_in_window(monkeypatch):
    logs = [
        _log(
            "rec-1",
            "MT-BREAK-001",
            [
                {"action": "started", "recorded_at": "2026-08-19T09:00:00+00:00"},
                {"action": "completed", "recorded_at": "2026-08-20T09:00:00+00:00"},
            ],
        ),
    ]
    client, _ = _weekly_client(monkeypatch, logs=logs)

    response = client.get(_weekly_url("2026-08-20", "2026-08-20"))

    assert response.status_code == 200
    body = response.json()
    assert len(body["days"]) == 1
    assert body["days"][0]["completed_minutes"] == 10
    assert body["totals"]["action_counts"]["started"] == 0
    assert body["totals"]["action_counts"]["completed"] == 1


def test_weekly_empty_range_returns_zeroed_days(monkeypatch):
    client, _ = _weekly_client(
        monkeypatch,
        logs=[
            _log(
                "rec-1",
                "MT-BREAK-001",
                [{"action": "completed", "recorded_at": "2026-08-10T09:00:00+00:00"}],
            )
        ],
    )

    response = client.get(_weekly_url("2026-08-20", "2026-08-26"))

    assert response.status_code == 200
    body = response.json()
    assert body["events"] == [] and body["adjustments"] == []
    assert body["totals"] == {
        "completed_minutes": 0,
        "action_counts": {
            action: 0
            for action in (
                "started",
                "completed",
                "partially_completed",
                "skipped",
                "replaced",
                "restored",
            )
        },
    }
    assert all(day["completed_minutes"] == 0 for day in body["days"])


def test_weekly_missing_duration_is_excluded_not_guessed(monkeypatch):
    logs = [
        _log(
            "rec-1",
            "MT-UNKNOWN",
            [{"action": "completed", "recorded_at": "2026-08-20T09:00:00+00:00"}],
        ),
    ]
    client, _ = _weekly_client(monkeypatch, logs=logs)

    response = client.get(_weekly_url("2026-08-20", "2026-08-26"))

    assert response.status_code == 200
    body = response.json()
    assert body["days"][0]["completed_minutes"] == 0
    assert body["totals"]["completed_minutes"] == 0
    assert body["totals"]["action_counts"]["completed"] == 1
    assert body["events"][0]["title"] is None


def test_weekly_cross_user_isolation(monkeypatch):
    logs = [
        _log(
            "rec-1",
            "MT-BREAK-001",
            [{"action": "completed", "recorded_at": "2026-08-20T09:00:00+00:00"}],
            user_id="user-002",
        ),
        _log(
            "rec-2",
            "MT-BREAK-001",
            [{"action": "started", "recorded_at": "2026-08-20T09:00:00+00:00"}],
            user_id="user-001",
        ),
    ]
    client, _ = _weekly_client(monkeypatch, logs=logs)

    response = client.get(_weekly_url("2026-08-20", "2026-08-26"))

    assert response.status_code == 200
    body = response.json()
    assert body["totals"]["action_counts"]["completed"] == 0
    assert body["totals"]["action_counts"]["started"] == 1


def test_weekly_invalid_date_range_returns_422(monkeypatch):
    client, _ = _weekly_client(monkeypatch)

    response = client.get(_weekly_url("2026-08-26", "2026-08-20"))

    assert response.status_code == 422


def test_weekly_is_read_only_and_touches_no_llm_feedback_memory_rag(monkeypatch):
    from weilv.api import app as api

    calls = {"llm": [], "feedback": [], "memory": [], "rag": []}
    client, _ = _weekly_client(
        monkeypatch,
        logs=[
            _log(
                "rec-1",
                "MT-BREAK-001",
                [{"action": "completed", "recorded_at": "2026-08-20T09:00:00+00:00"}],
            )
        ],
    )
    monkeypatch.setattr(api, "run_personal_rag", lambda *_a, **_k: calls["rag"].append(1))
    monkeypatch.setattr(api, "run_agentic_rag", lambda *_a, **_k: calls["rag"].append(1))
    monkeypatch.setattr(
        api, "persist_task_feedback_memory", lambda *_a, **_k: calls["feedback"].append(1)
    )
    monkeypatch.setattr(api, "create_memory", lambda *_a, **_k: calls["memory"].append(1))
    monkeypatch.setattr(api, "update_memory", lambda *_a, **_k: calls["memory"].append(1))

    response = client.get(_weekly_url("2026-08-20", "2026-08-26"))

    assert response.status_code == 200
    assert calls == {"llm": [], "feedback": [], "memory": [], "rag": []}
