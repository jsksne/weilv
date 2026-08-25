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


def _patch_log_index(monkeypatch, client, prefix):
    from weilv.elasticsearch_indices import get_user_memory_index_definitions
    from weilv import interaction_logs
    from weilv.api import task_events

    index = f"{prefix}interaction_logs_v1"
    client.indices.create(
        index=index,
        settings={"number_of_shards": 1, "number_of_replicas": 0},
        mappings=get_user_memory_index_definitions()["interaction_logs_v1"]["mappings"],
    )
    monkeypatch.setattr(interaction_logs, "INTERACTION_LOG_INDEX", index)
    monkeypatch.setattr(task_events, "INTERACTION_LOG_INDEX", index)
    return index


@pytest.mark.integration
def test_task_action_event_persisted_in_real_interaction_log(monkeypatch):
    from weilv.api import app as api

    client = _client_or_skip()
    prefix = f"weilv_task_events_{uuid4().hex}_"
    log_index = _patch_log_index(monkeypatch, client, prefix)
    monkeypatch.setattr(
        api,
        "run_personal_rag",
        lambda *_args, **_kwargs: {
            "status": "allowed",
            "selected_task": {"task_id": "MT-SED-001", "instruction": "正式指令"},
            "explanation": "解释",
            "sources": [{"chunk_id": "KC-1"}],
            "matched_rule_ids": [],
            "reason_codes": [],
        },
    )
    user_id = "poc-task-events-user"
    try:
        api.app.state.es_client = client
        api.app.state.api_key = "test-api-key"
        http = TestClient(api.app)
        recommendation = http.post(
            "/api/v1/recommendations",
            json={
                "user_id": user_id,
                "query": "我写作业快一个小时了，现在有10分钟休息。",
                "target_stage": "junior_high",
                "current_context": "home",
                "activity_context": "writing",
                "available_minutes": 10,
            },
        )
        recommendation_id = recommendation.json()["recommendation_id"]
        event = http.post(
            f"/api/v1/users/{user_id}/recommendations/{recommendation_id}/events",
            json={"action": "completed"},
        )

        assert recommendation.status_code == event.status_code == 200
        assert event.json()["action"] == "completed"
        assert event.json()["task_id"] == "MT-SED-001"
        source = client.get(index=log_index, id=recommendation_id)["_source"]
        assert source["task_events"][0]["action"] == "completed"
        assert "query" not in source
        assert "usefulness" not in source and "difficulty" not in source
    finally:
        if client.indices.exists(index=log_index):
            client.indices.delete(index=log_index)
        client.close()
