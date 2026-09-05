"""Schedule minimal CRUD + recommendation fact plumbing (日程与易启动 spec)."""

from fastapi.testclient import TestClient


class FakeIndices:
    def exists(self, *, index):
        return False

    def create(self, **kwargs):
        pass


class FakeScheduleClient:
    """In-memory stand-in for ES: enough surface for the schedule endpoints."""

    def __init__(self):
        self.docs = {}
        self.seq = 0

    def create(self, *, index, id, document):
        self.docs[id] = dict(document)

    def get(self, *, index, id):
        if id not in self.docs:
            from elasticsearch import NotFoundError

            raise NotFoundError(404, "not_found")
        return {"_source": dict(self.docs[id])}

    def update(self, *, index, id, doc, refresh=None):
        self.docs[id].update(doc)

    def delete(self, *, index, id, refresh=None):
        self.docs.pop(id, None)

    def search(self, *, index, size, query, sort=None):
        filters = query["bool"]["filter"]
        user_term = next(f["term"]["user_id"] for f in filters if "term" in f and "user_id" in f["term"])
        start = next(f["range"]["start_date"]["lte"] for f in filters if "range" in f and "start_date" in f["range"])
        end = next(f["range"]["end_date"]["gte"] for f in filters if "range" in f and "end_date" in f["range"])
        hits = [
            {"_source": dict(doc)}
            for doc in self.docs.values()
            if doc["user_id"] == user_term
            and doc["start_date"] <= start
            and doc["end_date"] >= end
        ]
        return {"hits": {"hits": hits}}


def _client(monkeypatch):
    from weilv.api import app as api

    es = FakeScheduleClient()
    api.app.state.es_client = es
    api.app.state.api_key = "server-key"
    return TestClient(api.app), es


def _event(**changes):
    payload = {
        "name": "期中考试",
        "start_date": "2026-09-08",
        "end_date": "2026-09-09",
        "kind": "exam",
        "busy_level": "busy",
    }
    payload.update(changes)
    return payload


def test_schedule_crud_roundtrip_and_user_isolation(monkeypatch):
    client, es = _client(monkeypatch)

    created = client.post("/api/v1/users/u-1/schedule", json=_event())
    assert created.status_code == 200
    event_id = created.json()["event_id"]
    assert created.json()["kind"] == "exam"

    listed = client.get("/api/v1/users/u-1/schedule", params={"from": "2026-09-08", "to": "2026-09-08"})
    assert [item["event_id"] for item in listed.json()["events"]] == [event_id]

    other = client.get("/api/v1/users/u-2/schedule", params={"from": "2026-09-08", "to": "2026-09-08"})
    assert other.json()["events"] == []

    updated = client.put(
        f"/api/v1/users/u-1/schedule/{event_id}",
        json=_event(name="期中考试周", end_date="2026-09-10"),
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "期中考试周"

    deleted = client.delete(f"/api/v1/users/u-1/schedule/{event_id}")
    assert deleted.status_code == 200
    assert client.get("/api/v1/users/u-1/schedule", params={"from": "2026-09-08", "to": "2026-09-09"}).json()["events"] == []


def test_schedule_rejects_inverted_date_range_and_invalid_kind(monkeypatch):
    client, _ = _client(monkeypatch)

    assert client.post("/api/v1/users/u-1/schedule", json=_event(end_date="2026-09-01")).status_code == 422
    assert client.post("/api/v1/users/u-1/schedule", json=_event(kind="birthday")).status_code == 422


def test_schedule_update_and_delete_404_for_missing_or_foreign(monkeypatch):
    client, es = _client(monkeypatch)
    created = client.post("/api/v1/users/u-1/schedule", json=_event()).json()
    es.docs[created["event_id"]]["user_id"] = "u-other"

    assert client.put(f"/api/v1/users/u-1/schedule/{created['event_id']}", json=_event()).status_code == 404
    assert client.delete(f"/api/v1/users/u-1/schedule/{created['event_id']}").status_code == 404


def test_schedule_facts_for_day_expose_only_structured_fields(monkeypatch):
    from datetime import date

    from weilv.api import schedule_queries

    client = FakeScheduleClient()
    monkeypatch.setattr(
        schedule_queries,
        "list_schedule_events",
        lambda *_args, **_kwargs: [
            {
                "event_id": "e1",
                "user_id": "u-1",
                "name": "数学期中考试",
                "start_date": "2026-09-08",
                "end_date": "2026-09-09",
                "kind": "exam",
                "busy_level": "busy",
            },
            {"event_id": "e2", "user_id": "u-1", "name": "假期", "kind": "holiday"},
        ],
    )

    facts = schedule_queries.schedule_facts_for_day(client, "u-1", date(2026, 9, 8))

    assert facts == [
        {"kind": "exam", "busy_level": "busy"},
        {"kind": "holiday"},
    ]
    assert all("name" not in fact for fact in facts)


def test_recommendation_request_accepts_schedule_facts_and_easy_start():
    from weilv.api.schemas import RecommendationRequest

    request = RecommendationRequest(
        user_id="u-1",
        query="现在不想动",
        target_stage="junior_high",
        current_context="home",
        schedule_events=[{"kind": "exam", "busy_level": "busy"}],
        prefer_easy_start=True,
    )

    assert request.schedule_events[0].kind == "exam"
    assert request.prefer_easy_start is True


def test_easy_start_reorders_within_safe_candidates_without_refiltering():
    from weilv.basic_rag import apply_easy_start_ordering

    tasks = [
        {"task_id": "LONG", "estimated_minutes": 25},
        {"task_id": "TINY", "estimated_minutes": 1},
        {"task_id": "MID", "estimated_minutes": 5},
    ]

    ordered = apply_easy_start_ordering(tasks)

    assert [task["task_id"] for task in ordered] == ["TINY", "MID", "LONG"]
    assert set(task["task_id"] for task in ordered) == {"LONG", "TINY", "MID"}
