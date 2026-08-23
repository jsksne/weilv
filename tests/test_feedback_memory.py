from dataclasses import replace


class FakeMemoryClient:
    def __init__(self):
        self.documents = {}
        self.update_calls = []

    def create(self, *, index, id, document, refresh=None):
        from elasticsearch import ConflictError

        key = (index, id)
        if key in self.documents:
            raise ConflictError("conflict", meta=None, body=None)
        self.documents[key] = dict(document)

    def get(self, *, index, id):
        from elasticsearch import NotFoundError

        try:
            return {"_source": dict(self.documents[(index, id)])}
        except KeyError as error:
            raise NotFoundError("missing", meta=None, body=None) from error

    def index(self, *, index, id, document, refresh=None):
        self.documents[(index, id)] = dict(document)

    def update(self, *, index, id, doc, refresh=None):
        self.update_calls.append((index, id, doc))
        self.documents[(index, id)].update(doc)


def _profile():
    from weilv.user_memory import UserProfile

    return UserProfile("user-A", "junior_high", True, "created", "updated")


def _candidate(**changes):
    from weilv.user_memory import UserMemoryCandidate

    candidate = UserMemoryCandidate(
        "",
        "user-A",
        "task_feedback",
        "structured_task_feedback",
        "MT-SED-001",
        None,
        "task_feedback",
        {"completion_status": "completed", "helpfulness": 5, "burden": "easy"},
        "2026-08-13T10:00:00+08:00",
        "2026-08-13T10:00:00+08:00",
    )
    return replace(candidate, **changes)


def test_same_task_feedback_updates_one_deterministic_memory(monkeypatch):
    from weilv.api import app as api
    from weilv.user_memory import USER_MEMORY_INDEX

    client = FakeMemoryClient()
    monkeypatch.setattr(
        api,
        "embed_memory",
        lambda *_args, **_kwargs: {"status": "embedded"},
    )

    first = api.persist_task_feedback_memory(client, _profile(), _candidate(), "key")
    second = api.persist_task_feedback_memory(
        client,
        _profile(),
        _candidate(
            memory_value={
                "completion_status": "skipped",
                "helpfulness": 2,
                "burden": "hard",
            },
            updated_at="2026-08-13T11:00:00+08:00",
        ),
        "key",
    )

    memories = [key for key in client.documents if key[0] == USER_MEMORY_INDEX]
    assert first == second == {"memory_persisted": True, "memory_embedding_ready": True}
    assert len(memories) == 1
    assert client.documents[memories[0]]["memory_value"]["completion_status"] == "skipped"


def test_embedding_failure_does_not_undo_valid_feedback_memory(monkeypatch):
    from weilv.api import app as api

    client = FakeMemoryClient()
    monkeypatch.setattr(
        api,
        "embed_memory",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("model down")),
    )

    result = api.persist_task_feedback_memory(client, _profile(), _candidate(), "key")

    assert result == {"memory_persisted": True, "memory_embedding_ready": False}
    assert len(client.documents) == 1
