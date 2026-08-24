from datetime import UTC, datetime
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


def _patch_log_index(monkeypatch, prefix):
    from weilv import interaction_logs
    from weilv.api import weekly_queries

    index = f"{prefix}interaction_logs_v1"
    monkeypatch.setattr(interaction_logs, "INTERACTION_LOG_INDEX", index)
    monkeypatch.setattr(weekly_queries, "INTERACTION_LOG_INDEX", index)
    return index


@pytest.mark.integration
def test_weekly_aggregation_over_real_interaction_logs(monkeypatch):
    from weilv.api import app as api

    client = _client_or_skip()
    prefix = f"weilv_weekly_{uuid4().hex}_"
    log_index = _patch_log_index(monkeypatch, prefix)
    monkeypatch.setattr(
        api,
        "run_personal_rag",
        lambda *_args, **_kwargs: {
            "status": "allowed",
            "selected_task": {"task_id": "MT-BREAK-001", "instruction": "正式指令"},
            "explanation": "解释",
            "sources": [{"chunk_id": "KC-1"}],
            "matched_rule_ids": [],
            "reason_codes": [],
        },
    )
    user_id = "poc-weekly-user"
    try:
        api.app.state.es_client = client
        api.app.state.api_key = None
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
        events = http.post(
            f"/api/v1/users/{user_id}/recommendations/{recommendation_id}/events",
            json={"action": "started"},
        )
        completed = http.post(
            f"/api/v1/users/{user_id}/recommendations/{recommendation_id}/events",
            json={"action": "completed"},
        )
        recorded_at = completed.json()["recorded_at"]
        day = datetime.fromisoformat(recorded_at).astimezone(UTC).date().isoformat()
        weekly = http.get(f"/api/v1/users/{user_id}/weekly?start_date={day}&end_date={day}")

        assert recommendation.status_code == events.status_code == completed.status_code == 200
        assert weekly.status_code == 200
        body = weekly.json()
        assert body["totals"]["action_counts"]["started"] == 1
        assert body["totals"]["action_counts"]["completed"] == 1
        # MT-BREAK-001 official estimated_minutes = 10 (formal metadata, not guessed)
        assert body["totals"]["completed_minutes"] == 10
        assert body["events"][0]["title"] == "连续读写后的远眺休息"
        assert "query" not in client.get(index=log_index, id=recommendation_id)["_source"]
    finally:
        if client.indices.exists(index=log_index):
            client.indices.delete(index=log_index)
        client.close()
