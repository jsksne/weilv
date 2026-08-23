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
    from weilv import interaction_logs, personal_memory_retrieval, user_memory

    profile_index = f"{prefix}user_profiles_v1"
    memory_index = f"{prefix}user_memory_v1"
    log_index = f"{prefix}interaction_logs_v1"
    monkeypatch.setattr(user_memory, "USER_PROFILE_INDEX", profile_index)
    monkeypatch.setattr(user_memory, "USER_MEMORY_INDEX", memory_index)
    monkeypatch.setattr(personal_memory_retrieval, "USER_MEMORY_INDEX", memory_index)
    monkeypatch.setattr(interaction_logs, "INTERACTION_LOG_INDEX", log_index)
    return profile_index, memory_index, log_index


def _recommendation_payload(user_id):
    return {
        "user_id": user_id,
        "query": "我写作业快一个小时了，现在有10分钟休息。",
        "target_stage": "junior_high",
        "current_context": "home",
        "activity_context": "writing",
        "available_minutes": 10,
    }


def _feedback_payload():
    return {
        "completion_status": "completed",
        "usefulness": "helpful",
        "difficulty": "easy",
        "reason": "",
    }


@pytest.mark.integration
def test_recommend_feedback_memory_retrieval_flow_with_real_es_and_mocked_models(monkeypatch):
    from weilv import personal_memory_retrieval
    from weilv.api import app as api
    from weilv.elasticsearch_indices import ensure_user_memory_indices
    from weilv.user_memory import UserProfile, upsert_user_profile

    client = _client_or_skip()
    prefix = f"weilv_feedback_flow_{uuid4().hex}_"
    indices = _patch_indices(monkeypatch, prefix)
    _, _, log_index = indices
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
    monkeypatch.setattr(api, "embed_memory", lambda *_args, **_kwargs: {"status": "embedded"})
    monkeypatch.setattr(
        personal_memory_retrieval,
        "embed_texts",
        lambda *_args, **_kwargs: [[0.1] * 1024],
    )
    monkeypatch.setattr(
        personal_memory_retrieval,
        "rerank_texts",
        lambda _query, documents, _key: [
            {"index": index, "relevance_score": 1.0} for index in range(len(documents))
        ],
    )
    profile = UserProfile(
        "poc-feedback-user",
        "junior_high",
        True,
        "2026-08-13T10:00:00+08:00",
        "2026-08-13T10:00:00+08:00",
    )

    try:
        ensure_user_memory_indices(client, prefix)
        upsert_user_profile(client, profile)
        api.app.state.es_client = client
        api.app.state.api_key = "mock-key"
        http = TestClient(api.app)
        recommendation = http.post(
            "/api/v1/recommendations", json=_recommendation_payload(profile.user_id)
        )
        recommendation_id = recommendation.json()["recommendation_id"]
        feedback = http.post(
            f"/api/v1/users/{profile.user_id}/recommendations/{recommendation_id}/feedback",
            json=_feedback_payload(),
        )
        memories = personal_memory_retrieval.retrieve_personal_memories(
            client, profile, "MT-SED-001 completed easy", "mock-key"
        )

        assert recommendation.status_code == feedback.status_code == 200
        assert feedback.json()["memory_persisted"] is True
        assert memories[0]["task_id"] == "MT-SED-001"
        assert "query" not in client.get(index=log_index, id=recommendation_id)["_source"]
    finally:
        for index_name in indices:
            if client.indices.exists(index=index_name):
                client.indices.delete(index=index_name)
        client.close()


@pytest.mark.integration
@pytest.mark.live_model
def test_live_recommend_feedback_embed_and_retrieve_cleans_up(monkeypatch):
    from weilv import basic_rag, personal_memory_retrieval, user_memory
    from weilv.api import app as api
    from weilv.elasticsearch_indices import ensure_user_memory_indices

    setup_client = _client_or_skip()
    prefix = f"weilv_feedback_live_{uuid4().hex}_"
    indices = _patch_indices(monkeypatch, prefix)
    _, memory_index, _ = indices
    counts = {"embedding": 0, "rerank": 0, "qwen_plus": 0}
    real_basic_embed = basic_rag.embed_texts
    real_basic_rerank = basic_rag.rerank_texts
    real_explain = basic_rag.explain_selected_task
    real_memory_embed = personal_memory_retrieval.embed_texts
    real_memory_rerank = personal_memory_retrieval.rerank_texts

    def basic_embed(*args, **kwargs):
        counts["embedding"] += 1
        return real_basic_embed(*args, **kwargs)

    def basic_rerank(*args, **kwargs):
        counts["rerank"] += 1
        return real_basic_rerank(*args, **kwargs)

    def explain(*args, **kwargs):
        counts["qwen_plus"] += 1
        return real_explain(*args, **kwargs)

    def memory_embed(*args, **kwargs):
        counts["embedding"] += 1
        return real_memory_embed(*args, **kwargs)

    def memory_rerank(*args, **kwargs):
        counts["rerank"] += 1
        return real_memory_rerank(*args, **kwargs)

    monkeypatch.setattr(basic_rag, "embed_texts", basic_embed)
    monkeypatch.setattr(basic_rag, "rerank_texts", basic_rerank)
    monkeypatch.setattr(basic_rag, "explain_selected_task", explain)
    monkeypatch.setattr(personal_memory_retrieval, "embed_texts", memory_embed)
    monkeypatch.setattr(personal_memory_retrieval, "rerank_texts", memory_rerank)
    user_id = "poc-stage5-feedback-live"

    try:
        ensure_user_memory_indices(setup_client, prefix)
        with TestClient(api.app) as http:
            put = http.put(
                f"/api/v1/users/{user_id}/profile",
                json={"target_stage": "junior_high", "memory_enabled": True},
            )
            recommendation = http.post(
                "/api/v1/recommendations", json=_recommendation_payload(user_id)
            )
            recommendation_id = recommendation.json()["recommendation_id"]
            feedback = http.post(
                f"/api/v1/users/{user_id}/recommendations/{recommendation_id}/feedback",
                json=_feedback_payload(),
            )
            profile = user_memory.get_user_profile(http.app.state.es_client, user_id)
            http.app.state.es_client.indices.refresh(index=memory_index)
            memories = personal_memory_retrieval.retrieve_personal_memories(
                http.app.state.es_client,
                profile,
                "MT-SED-001 completed easy",
                http.app.state.api_key,
            )

        assert put.status_code == recommendation.status_code == feedback.status_code == 200
        assert feedback.json()["memory_persisted"] is True
        assert memories
        assert counts == {"embedding": 3, "rerank": 3, "qwen_plus": 1}
        print(f"live_model_calls={counts}")
    finally:
        for index_name in indices:
            if setup_client.indices.exists(index=index_name):
                setup_client.indices.delete(index=index_name)
        setup_client.close()
