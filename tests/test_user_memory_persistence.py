from dataclasses import replace

VALID_TASK_IDS = {"MT-SED-001", "MT-SED-002"}


class FakeElasticsearch:
    def __init__(self):
        self.documents = {}
        self.write_calls = []

    def index(self, *, index, id, document, refresh=None):
        self.write_calls.append(("index", index, id, refresh))
        self.documents[(index, id)] = dict(document)

    def create(self, *, index, id, document, refresh=None):
        from elasticsearch import ConflictError

        self.write_calls.append(("create", index, id, refresh))
        key = (index, id)
        if key in self.documents:
            raise ConflictError("conflict", meta=None, body=None)
        self.documents[key] = dict(document)

    def get(self, *, index, id):
        from elasticsearch import NotFoundError

        try:
            return {"_source": dict(self.documents[(index, id)])}
        except KeyError as error:
            raise NotFoundError("not found", meta=None, body=None) from error

    def delete(self, *, index, id):
        del self.documents[(index, id)]


def _profile(memory_enabled=True, user_id="usr_anon_001"):
    from weilv.user_memory import UserProfile

    return UserProfile(
        user_id=user_id,
        target_stage="junior_high",
        memory_enabled=memory_enabled,
        created_at="2026-08-13T10:00:00+08:00",
        updated_at="2026-08-13T10:00:00+08:00",
    )


def _candidate(**changes):
    from weilv.user_memory import UserMemoryCandidate

    values = {
        "memory_id": "ignored-input-id",
        "user_id": "usr_anon_001",
        "memory_type": "task_feedback",
        "source_type": "structured_task_feedback",
        "task_id": "MT-SED-001",
        "domain": "sedentary",
        "memory_key": "task_feedback",
        "memory_value": {
            "completion_status": "completed",
            "helpfulness": 3,
            "burden": "acceptable",
        },
        "created_at": "2026-08-13T10:01:00+08:00",
        "updated_at": "2026-08-13T10:01:00+08:00",
    }
    values.update(changes)
    return UserMemoryCandidate(**values)


def test_profile_can_be_upserted_and_loaded_with_only_frozen_fields():
    from weilv.user_memory import get_user_profile, upsert_user_profile

    client = FakeElasticsearch()
    profile = _profile()

    assert upsert_user_profile(client, profile) == {"status": "updated", "user_id": profile.user_id}
    assert get_user_profile(client, profile.user_id) == profile
    assert set(client.documents[("user_profiles_v1", profile.user_id)]) == {
        "user_id",
        "target_stage",
        "memory_enabled",
        "created_at",
        "updated_at",
    }


def test_create_is_validated_persisted_and_idempotent():
    from weilv.user_memory import create_memory

    client = FakeElasticsearch()
    profile = _profile()
    candidate = _candidate()

    created = create_memory(client, profile, candidate, VALID_TASK_IDS)
    duplicate = create_memory(client, profile, candidate, VALID_TASK_IDS)

    assert created["status"] == "created"
    assert duplicate == {"status": "already_exists", "memory_id": created["memory_id"]}
    assert len([key for key in client.documents if key[0] == "user_memory_v1"]) == 1
    stored = client.documents[("user_memory_v1", created["memory_id"])]
    assert stored["active"] is True
    assert stored["review_status"] == "valid"
    assert "embedding" not in stored
    assert stored["retrieval_text"].endswith("helpfulness=3")


def test_create_and_update_wait_until_memory_is_search_visible():
    from weilv.user_memory import create_memory, update_memory

    client = FakeElasticsearch()
    profile = _profile()
    memory_id = create_memory(client, profile, _candidate(), VALID_TASK_IDS)["memory_id"]
    update_memory(client, profile, _candidate(memory_id=memory_id), VALID_TASK_IDS)

    memory_writes = [call for call in client.write_calls if call[1] == "user_memory_v1"]
    assert [call[3] for call in memory_writes] == ["wait_for", "wait_for"]


def test_disabled_memory_rejects_create_without_writing():
    from weilv.user_memory import create_memory

    client = FakeElasticsearch()

    assert create_memory(client, _profile(False), _candidate(), VALID_TASK_IDS) == {
        "status": "rejected",
        "reason_code": "memory_disabled",
    }
    assert not client.documents


def test_update_preserves_identity_and_created_at_but_refreshes_derived_fields():
    from weilv.user_memory import create_memory, update_memory

    client = FakeElasticsearch()
    profile = _profile()
    created = create_memory(client, profile, _candidate(), VALID_TASK_IDS)
    memory_id = created["memory_id"]
    client.documents[("user_memory_v1", memory_id)]["embedding"] = [0.5]

    updated_candidate = _candidate(
        memory_id=memory_id,
        memory_value={
            "completion_status": "completed",
            "helpfulness": 5,
            "burden": "easy",
        },
        created_at="should-not-replace-created-at",
        updated_at="2026-08-13T11:00:00+08:00",
        embedding=[0.9],
    )
    result = update_memory(client, profile, updated_candidate, VALID_TASK_IDS)
    stored = client.documents[("user_memory_v1", memory_id)]

    assert result == {"status": "updated", "memory_id": memory_id}
    assert stored["memory_id"] == memory_id
    assert stored["user_id"] == profile.user_id
    assert stored["created_at"] == "2026-08-13T10:01:00+08:00"
    assert stored["updated_at"] == "2026-08-13T11:00:00+08:00"
    assert stored["retrieval_text"].endswith("helpfulness=5")
    assert "embedding" not in stored


def test_update_revalidates_and_does_not_contaminate_existing_memory():
    from weilv.user_memory import create_memory, update_memory

    client = FakeElasticsearch()
    profile = _profile()
    memory_id = create_memory(client, profile, _candidate(), VALID_TASK_IDS)["memory_id"]
    original = dict(client.documents[("user_memory_v1", memory_id)])
    invalid = replace(_candidate(memory_id=memory_id), memory_value={"diagnosis": "x"})

    assert update_memory(client, profile, invalid, VALID_TASK_IDS) == {
        "status": "rejected",
        "memory_id": memory_id,
        "reason_code": "forbidden_persistence_field",
    }
    assert client.documents[("user_memory_v1", memory_id)] == original


def test_cross_user_update_is_rejected():
    from weilv.user_memory import create_memory, update_memory

    client = FakeElasticsearch()
    owner = _profile()
    memory_id = create_memory(client, owner, _candidate(), VALID_TASK_IDS)["memory_id"]
    other = _profile(user_id="usr_anon_002")
    attempted = _candidate(memory_id=memory_id, user_id=other.user_id)

    assert update_memory(client, other, attempted, VALID_TASK_IDS) == {
        "status": "rejected",
        "memory_id": memory_id,
        "reason_code": "memory_owner_mismatch",
    }


def test_disabled_memory_rejects_update():
    from weilv.user_memory import create_memory, update_memory

    client = FakeElasticsearch()
    owner = _profile()
    memory_id = create_memory(client, owner, _candidate(), VALID_TASK_IDS)["memory_id"]

    assert update_memory(
        client, _profile(False), _candidate(memory_id=memory_id), VALID_TASK_IDS
    ) == {
        "status": "rejected",
        "memory_id": memory_id,
        "reason_code": "memory_disabled",
    }


def test_forget_physically_deletes_and_then_returns_not_found():
    from weilv.user_memory import create_memory, forget_memory, get_memory

    client = FakeElasticsearch()
    profile = _profile()
    memory_id = create_memory(client, profile, _candidate(), VALID_TASK_IDS)["memory_id"]

    assert forget_memory(client, profile.user_id, memory_id) == {
        "status": "forgotten",
        "memory_id": memory_id,
    }
    assert get_memory(client, profile.user_id, memory_id) is None
    assert forget_memory(client, profile.user_id, memory_id) == {
        "status": "not_found",
        "memory_id": memory_id,
    }


def test_cross_user_forget_is_rejected_but_disabled_owner_can_forget():
    from weilv.user_memory import create_memory, forget_memory

    client = FakeElasticsearch()
    owner = _profile()
    memory_id = create_memory(client, owner, _candidate(), VALID_TASK_IDS)["memory_id"]

    assert forget_memory(client, "usr_anon_002", memory_id) == {
        "status": "rejected",
        "memory_id": memory_id,
        "reason_code": "memory_owner_mismatch",
    }
    assert forget_memory(client, _profile(False).user_id, memory_id) == {
        "status": "forgotten",
        "memory_id": memory_id,
    }


def test_memory_id_is_deterministic_and_separates_tasks_and_types():
    from weilv.user_memory import build_memory_id

    base = _candidate()
    reordered_value = replace(
        base,
        memory_value={"burden": "acceptable", "helpfulness": 3, "completion_status": "completed"},
    )

    assert build_memory_id(base) == build_memory_id(reordered_value)
    assert build_memory_id(base) != build_memory_id(replace(base, task_id="MT-SED-002"))
    assert build_memory_id(base) != build_memory_id(
        replace(
            base,
            memory_type="task_preference",
            source_type="explicit_user_setting",
            memory_key="prefer_task",
            memory_value={"preference": "prefer_task"},
        )
    )
