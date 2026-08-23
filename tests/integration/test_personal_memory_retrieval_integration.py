from uuid import uuid4

import pytest
from elasticsearch import Elasticsearch


def _client_or_skip():
    client = Elasticsearch("http://127.0.0.1:9200", request_timeout=30)
    if not client.ping():
        client.close()
        pytest.skip("local Elasticsearch is not running")
    return client


def _memory(memory_id, user_id, *, active=True, review_status="valid", embedding=None):
    from weilv.user_memory import UserMemoryCandidate, build_retrieval_text

    candidate = UserMemoryCandidate(
        memory_id,
        user_id,
        "context_preference",
        "explicit_user_setting",
        None,
        "sedentary",
        "context_preference",
        {"preferred_context": "home"},
        "2026-08-13T10:00:00+08:00",
        "2026-08-13T10:00:00+08:00",
    )
    document = {
        "memory_id": memory_id,
        "user_id": user_id,
        "memory_type": "context_preference",
        "source_type": "explicit_user_setting",
        "task_id": None,
        "domain": "sedentary",
        "memory_key": "context_preference",
        "memory_value": candidate.memory_value,
        "retrieval_text": build_retrieval_text(candidate),
        "created_at": "2026-08-13T10:00:00+08:00",
        "updated_at": "2026-08-13T10:00:00+08:00",
        "active": active,
        "review_status": review_status,
    }
    if embedding is not None:
        document["embedding"] = embedding
    return document


@pytest.mark.integration
def test_real_es_hard_filters_bm25_without_vector_and_forget(monkeypatch):
    from weilv import personal_memory_retrieval as retrieval
    from weilv.elasticsearch_indices import ensure_user_memory_indices
    from weilv.user_memory import UserProfile, forget_memory

    client = _client_or_skip()
    prefix = f"weilv_personal_memory_test_{uuid4().hex}_"
    profile_index = f"{prefix}user_profiles_v1"
    memory_index = f"{prefix}user_memory_v1"
    monkeypatch.setattr(retrieval, "USER_MEMORY_INDEX", memory_index)
    monkeypatch.setattr("weilv.user_memory.USER_MEMORY_INDEX", memory_index)
    profile = UserProfile("user-A", "junior_high", True, "created", "updated")
    rerank_documents = []
    monkeypatch.setattr(retrieval, "embed_texts", lambda *_args, **_kwargs: [[0.1] * 1024])
    monkeypatch.setattr(
        retrieval,
        "rerank_texts",
        lambda _query, documents, _api_key: rerank_documents.extend(documents)
        or [{"index": index, "relevance_score": 1.0} for index in range(len(documents))],
    )
    documents = [
        _memory("visible-no-vector", "user-A"),
        _memory("other-user", "user-B", embedding=[0.1] * 1024),
        _memory("inactive", "user-A", active=False),
        _memory("invalid", "user-A", review_status="invalid"),
    ]

    try:
        ensure_user_memory_indices(client, prefix)
        for document in documents:
            client.index(index=memory_index, id=document["memory_id"], document=document)
        client.indices.refresh(index=memory_index)

        result = retrieval.retrieve_personal_memories(client, profile, "preferred_context home", "unused")

        assert [item["memory_id"] for item in result] == ["visible-no-vector"]
        assert rerank_documents == [documents[0]["retrieval_text"]]
        assert forget_memory(client, profile.user_id, "visible-no-vector")["status"] == "forgotten"
        client.indices.refresh(index=memory_index)
        assert retrieval.retrieve_personal_memories(
            client, profile, "preferred_context home", "unused"
        ) == []
    finally:
        for index_name in (profile_index, memory_index):
            if client.indices.exists(index=index_name):
                client.indices.delete(index=index_name)
        client.close()


@pytest.mark.integration
@pytest.mark.live_model
def test_live_personal_memory_hybrid_poc_cleans_up(monkeypatch):
    from weilv import personal_memory_retrieval as retrieval
    from weilv.elasticsearch_indices import ensure_user_memory_indices
    from weilv.retrieval_slice import load_api_key
    from weilv.user_memory import (
        UserMemoryCandidate,
        UserProfile,
        build_retrieval_text,
        create_memory,
    )

    try:
        api_key = load_api_key()
    except RuntimeError:
        pytest.skip("DASHSCOPE_API_KEY is not configured")

    client = _client_or_skip()
    prefix = f"weilv_personal_memory_live_{uuid4().hex}_"
    profile_index = f"{prefix}user_profiles_v1"
    memory_index = f"{prefix}user_memory_v1"
    monkeypatch.setattr(retrieval, "USER_MEMORY_INDEX", memory_index)
    monkeypatch.setattr("weilv.user_memory.USER_MEMORY_INDEX", memory_index)
    profile = UserProfile("poc-user-memory-001", "junior_high", True, "created", "updated")
    real_embed = retrieval.embed_texts
    real_rerank = retrieval.rerank_texts
    model_calls = {"embedding": [], "rerank": 0}

    def counted_embed(texts, key, text_type):
        model_calls["embedding"].append(text_type)
        return real_embed(texts, key, text_type)

    def counted_rerank(query, texts, key):
        model_calls["rerank"] += 1
        return real_rerank(query, texts, key)

    monkeypatch.setattr(retrieval, "embed_texts", counted_embed)
    monkeypatch.setattr(retrieval, "rerank_texts", counted_rerank)
    candidates = [
        UserMemoryCandidate(
            "", profile.user_id, "task_feedback", "structured_task_feedback", task_id,
            domain, "task_feedback", value, "2026-08-13T10:00:00+08:00",
            "2026-08-13T10:00:00+08:00"
        )
        for task_id, domain, value in (
            (
                "MT-SED-001",
                "sedentary",
                {"completion_status": "completed", "helpfulness": 5, "burden": "easy"},
            ),
            (
                "MT-BREAK-001",
                "study_break",
                {"completion_status": "completed", "helpfulness": 4, "burden": "acceptable"},
            ),
            (
                "MT-SLEEP-001",
                "sleep",
                {"completion_status": "skipped", "helpfulness": 2, "burden": "hard"},
            ),
        )
    ]
    valid_task_ids = {candidate.task_id for candidate in candidates}

    try:
        ensure_user_memory_indices(client, prefix)
        memory_ids = []
        for candidate in candidates:
            result = create_memory(client, profile, candidate, valid_task_ids)
            assert result["status"] == "created"
            memory_ids.append(result["memory_id"])
            stored = client.get(index=memory_index, id=result["memory_id"])["_source"]
            assert stored["retrieval_text"] == build_retrieval_text(candidate)
        client.indices.refresh(index=memory_index)
        for memory_id in memory_ids:
            assert retrieval.embed_memory(client, profile.user_id, memory_id, api_key)[
                "status"
            ] == "embedded"
        client.indices.refresh(index=memory_index)

        result = retrieval.retrieve_personal_memories(
            client,
            profile,
            "我写作业坐了很久，现在想休息一下",
            api_key,
        )

        assert result
        assert len(result) <= 5
        assert all(item["retrieval_text"].startswith("type=task_feedback\n") for item in result)
        assert model_calls == {
            "embedding": ["document", "document", "document", "query"],
            "rerank": 1,
        }
    finally:
        for index_name in (profile_index, memory_index):
            if client.indices.exists(index=index_name):
                client.indices.delete(index=index_name)
        client.close()
