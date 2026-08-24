from uuid import uuid4

import pytest
from elasticsearch import Elasticsearch
from fastapi.testclient import TestClient


def _client_or_skip():
    client = Elasticsearch("http://127.0.0.1:9200", request_timeout=30)
    if not client.ping():
        client.close()
        pytest.skip("local Elasticsearch is not running")
    return client


def _patch_indices(monkeypatch, prefix):
    from weilv import user_memory
    from weilv.api import memory_queries

    profile_index = f"{prefix}user_profiles_v1"
    memory_index = f"{prefix}user_memory_v1"
    monkeypatch.setattr(user_memory, "USER_PROFILE_INDEX", profile_index)
    monkeypatch.setattr(user_memory, "USER_MEMORY_INDEX", memory_index)
    monkeypatch.setattr(memory_queries, "USER_MEMORY_INDEX", memory_index)
    return profile_index, memory_index


@pytest.mark.integration
def test_memory_list_and_delete_flow_with_real_es(monkeypatch):
    from weilv.api import app as api
    from weilv.elasticsearch_indices import ensure_user_memory_indices
    from weilv.user_memory import (
        UserMemoryCandidate,
        UserProfile,
        create_memory,
        upsert_user_profile,
    )

    client = _client_or_skip()
    prefix = f"weilv_memory_api_{uuid4().hex}_"
    indices = _patch_indices(monkeypatch, prefix)
    profile = UserProfile(
        "poc-memory-api-user",
        "junior_high",
        True,
        "2026-08-13T10:00:00+08:00",
        "2026-08-13T10:00:00+08:00",
    )
    candidate = UserMemoryCandidate(
        memory_id="",
        user_id=profile.user_id,
        memory_type="task_feedback",
        source_type="structured_task_feedback",
        task_id="MT-SED-001",
        domain=None,
        memory_key="",
        memory_value={
            "completion_status": "completed",
            "helpfulness": 5,
            "burden": "easy",
            "confidence": 1,
        },
        created_at="2026-08-13T10:00:00+08:00",
        updated_at="2026-08-13T10:00:00+08:00",
    )
    try:
        ensure_user_memory_indices(client, prefix)
        upsert_user_profile(client, profile)
        created = create_memory(client, profile, candidate, {"MT-SED-001"})
        assert created["status"] == "created"
        memory_id = created["memory_id"]
        api.app.state.es_client = client
        api.app.state.api_key = None
        http = TestClient(api.app)

        listed = http.get(f"/api/v1/users/{profile.user_id}/memories")
        deleted = http.post(f"/api/v1/users/{profile.user_id}/memories/{memory_id}/delete")
        listed_after = http.get(f"/api/v1/users/{profile.user_id}/memories")

        assert listed.status_code == deleted.status_code == listed_after.status_code == 200
        assert [item["memory_id"] for item in listed.json()["memories"]] == [memory_id]
        assert listed.json()["memory_enabled"] is True
        assert set(listed.json()["memories"][0]) == {
            "memory_id",
            "memory_type",
            "summary",
            "created_at",
            "updated_at",
        }
        assert deleted.json() == {"status": "forgotten", "memory_id": memory_id}
        assert listed_after.json()["memories"] == []

        gone = http.post(f"/api/v1/users/{profile.user_id}/memories/{memory_id}/delete")
        assert gone.status_code == 404
    finally:
        for index_name in indices:
            if client.indices.exists(index=index_name):
                client.indices.delete(index=index_name)
        client.close()
