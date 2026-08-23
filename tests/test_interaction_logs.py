from elasticsearch import NotFoundError


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

    def update(self, *, index, id, doc):
        self.documents[(index, id)].update(doc)


def test_session_is_minimal_user_scoped_and_feedback_update_is_idempotent():
    from weilv.interaction_logs import (
        create_recommendation_log,
        get_recommendation_log,
        update_recommendation_feedback,
    )

    client = FakeClient()
    session = {
        "recommendation_id": "rec-1",
        "user_id": "user-A",
        "status": "allowed",
        "selected_task_id": "MT-SED-001",
        "target_stage": "junior_high",
        "current_context": "home",
        "activity_context": "writing",
        "available_minutes": 10,
        "created_at": "2026-08-13T10:00:00+08:00",
        "feedback": None,
        "feedback_updated_at": None,
        "memory_persisted": False,
    }
    create_recommendation_log(client, session)

    assert get_recommendation_log(client, "user-A", "rec-1") == session
    assert get_recommendation_log(client, "user-B", "rec-1") is None
    assert get_recommendation_log(client, "user-A", "missing") is None
    assert "query" not in session
    assert "explanation" not in session

    first = {"completion_status": "completed", "helpfulness": 5, "burden": "easy"}
    second = {"completion_status": "skipped", "helpfulness": 2, "burden": "hard"}
    update_recommendation_feedback(client, "rec-1", first, "updated-1", True)
    update_recommendation_feedback(client, "rec-1", second, "updated-2", True)

    stored = get_recommendation_log(client, "user-A", "rec-1")
    assert stored["feedback"] == second
    assert stored["feedback_updated_at"] == "updated-2"
    assert len(client.documents) == 1
