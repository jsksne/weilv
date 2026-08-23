from uuid import uuid4

import pytest
from elasticsearch import Elasticsearch


@pytest.mark.integration
@pytest.mark.live_model
def test_live_personal_rag_uses_exact_evidence_and_guard_once(monkeypatch):
    from weilv import basic_rag, personal_memory_retrieval, personal_rag
    from weilv.elasticsearch_indices import ensure_user_memory_indices
    from weilv.retrieval_slice import load_api_key
    from weilv.user_memory import (
        UserProfile,
        upsert_user_profile,
    )

    try:
        api_key = load_api_key()
    except RuntimeError:
        pytest.skip("DASHSCOPE_API_KEY is not configured")

    client = Elasticsearch("http://127.0.0.1:9200", request_timeout=30)
    if not client.ping():
        client.close()
        pytest.skip("local Elasticsearch is not running")

    prefix = f"weilv_personal_rag_live_{uuid4().hex}_"
    profile_index = f"{prefix}user_profiles_v1"
    memory_index = f"{prefix}user_memory_v1"
    monkeypatch.setattr("weilv.user_memory.USER_PROFILE_INDEX", profile_index)
    monkeypatch.setattr("weilv.user_memory.USER_MEMORY_INDEX", memory_index)
    monkeypatch.setattr(personal_memory_retrieval, "USER_MEMORY_INDEX", memory_index)
    request = basic_rag.BasicRagRequest(
        query="我写作业坐了很久，现在有十分钟可以休息",
        target_stage="junior_high",
        current_context="home",
        available_minutes=10,
    )
    profile = UserProfile("poc-grounding-guard", "junior_high", True, "2026-08-13", "2026-08-13")
    counts = {"query_embedding": 0, "explanation": 0}
    real_embed = basic_rag.embed_texts
    real_explain = basic_rag.explain_selected_task

    def counted_query_embed(texts, api_key, text_type):
        if text_type == "query":
            counts["query_embedding"] += 1
        return real_embed(texts, api_key, text_type)

    def counted_explain(query, selected_task, knowledge, api_key):
        counts["explanation"] += 1
        return real_explain(query, selected_task, knowledge, api_key)

    try:
        ensure_user_memory_indices(client, prefix)
        upsert_user_profile(client, profile)
        client.indices.refresh(index=memory_index)

        monkeypatch.setattr(basic_rag, "embed_texts", counted_query_embed)
        monkeypatch.setattr(basic_rag, "explain_selected_task", counted_explain)
        result = personal_rag.run_personal_rag(request, profile.user_id, client, api_key)

        assert result["status"] == "allowed"
        assert {item["chunk_id"] for item in result["sources"]} == set(
            result["selected_task"]["evidence_chunk_ids"]
        )
        assert result["context_sources"]
        assert result["personalization"] == {
            "memory_used": False,
            "memory_ids": [],
            "base_task_rank": 1,
            "personalization_delta": 0,
            "adjusted_rank": 1,
            "reason_codes": [],
        }
        assert result["selected_task"]["task_id"] in {
            hit["_source"]["task_id"]
            for hit in client.search(index="micro_tasks_v1", size=100)["hits"]["hits"]
        }
        assert set(result["explanation_guard"]) == {
            "passed",
            "fallback_used",
            "reason_codes",
        }
        assert counts == {"query_embedding": 1, "explanation": 1}
    finally:
        for index_name in (profile_index, memory_index):
            if client.indices.exists(index=index_name):
                client.indices.delete(index=index_name)
        client.close()
