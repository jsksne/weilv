from dataclasses import replace
from uuid import uuid4

import pytest
from elasticsearch import Elasticsearch


@pytest.mark.integration
def test_real_elasticsearch_persists_updates_and_forgets_user_memory(monkeypatch):
    from weilv import user_memory
    from weilv.elasticsearch_indices import ensure_user_memory_indices

    client = Elasticsearch("http://127.0.0.1:9200", request_timeout=30)
    if not client.ping():
        client.close()
        pytest.skip("local Elasticsearch is not running")

    prefix = f"weilv_user_memory_test_{uuid4().hex}_"
    profile_index = f"{prefix}user_profiles_v1"
    memory_index = f"{prefix}user_memory_v1"
    monkeypatch.setattr(user_memory, "USER_PROFILE_INDEX", profile_index)
    monkeypatch.setattr(user_memory, "USER_MEMORY_INDEX", memory_index)
    profile = user_memory.UserProfile(
        user_id="usr_integration_001",
        target_stage="junior_high",
        memory_enabled=True,
        created_at="2026-08-13T10:00:00+08:00",
        updated_at="2026-08-13T10:00:00+08:00",
    )
    candidate = user_memory.UserMemoryCandidate(
        memory_id="ignored",
        user_id=profile.user_id,
        memory_type="task_feedback",
        source_type="structured_task_feedback",
        task_id="MT-SED-001",
        domain="sedentary",
        memory_key="task_feedback",
        memory_value={
            "completion_status": "completed",
            "helpfulness": 3,
            "burden": "acceptable",
        },
        created_at="2026-08-13T10:01:00+08:00",
        updated_at="2026-08-13T10:01:00+08:00",
    )

    try:
        ensure_user_memory_indices(client, prefix)
        user_memory.upsert_user_profile(client, profile)
        created = user_memory.create_memory(client, profile, candidate, {"MT-SED-001"})
        memory_id = created["memory_id"]
        updated = user_memory.update_memory(
            client,
            profile,
            replace(
                candidate,
                memory_id=memory_id,
                memory_value={**candidate.memory_value, "helpfulness": 5},
                updated_at="2026-08-13T11:00:00+08:00",
            ),
            {"MT-SED-001"},
        )

        assert user_memory.get_user_profile(client, profile.user_id) == profile
        assert created["status"] == "created"
        assert updated == {"status": "updated", "memory_id": memory_id}
        assert user_memory.get_memory(client, profile.user_id, memory_id)["embedding"] == []
        assert user_memory.forget_memory(client, profile.user_id, memory_id)["status"] == "forgotten"
        assert user_memory.get_memory(client, profile.user_id, memory_id) is None
    finally:
        for index_name in (profile_index, memory_index):
            if client.indices.exists(index=index_name):
                client.indices.delete(index=index_name)
        client.close()
