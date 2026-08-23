import pytest


def _profile(enabled=True):
    from weilv.user_memory import UserProfile

    return UserProfile("user-A", "junior_high", enabled, "created", "updated")


def _memory(memory_id="UM-1", **changes):
    memory = {
        "memory_id": memory_id,
        "user_id": "user-A",
        "memory_type": "task_feedback",
        "source_type": "structured_task_feedback",
        "task_id": "MT-SED-001",
        "domain": "sedentary",
        "memory_key": "task_feedback",
        "memory_value": {"helpfulness": 5},
        "retrieval_text": f"memory={memory_id}",
        "created_at": "created",
        "updated_at": "updated",
        "active": True,
        "review_status": "valid",
    }
    memory.update(changes)
    return memory


class MemoryClient:
    def __init__(self, document=None):
        self.document = document
        self.update_calls = []

    def get(self, **_):
        from elasticsearch import NotFoundError

        if self.document is None:
            raise NotFoundError("not found", meta=None, body=None)
        return {"_source": dict(self.document)}

    def update(self, **kwargs):
        self.update_calls.append(kwargs)
        self.document.update(kwargs["doc"])


def _install_retrieval_fakes(monkeypatch, bm25=None, vector=None, rerank_order=None):
    from weilv import personal_memory_retrieval as module

    calls = {"embed": [], "bm25": [], "vector": [], "rerank": []}

    def embed(texts, api_key, text_type):
        calls["embed"].append((texts, api_key, text_type))
        return [[0.1] * 1024]

    def bm25_search(*args, **kwargs):
        calls["bm25"].append((args, kwargs))
        return list(bm25 or [])

    def vector_search(*args, **kwargs):
        calls["vector"].append((args, kwargs))
        return list(vector or [])

    def rerank(query, documents, api_key):
        calls["rerank"].append((query, documents, api_key))
        order = rerank_order if rerank_order is not None else range(len(documents))
        return [
            {"index": index, "relevance_score": 1 - position / 100}
            for position, index in enumerate(order)
        ]

    monkeypatch.setattr(module, "embed_texts", embed)
    monkeypatch.setattr(module, "bm25_search", bm25_search)
    monkeypatch.setattr(module, "vector_search", vector_search)
    monkeypatch.setattr(module, "rerank_texts", rerank)
    return calls


def test_disabled_profile_returns_empty_without_model_or_search_calls(monkeypatch):
    from weilv.personal_memory_retrieval import retrieve_personal_memories

    calls = _install_retrieval_fakes(monkeypatch, bm25=[_memory()])

    assert retrieve_personal_memories(object(), _profile(False), "query", "key") == []
    assert calls == {"embed": [], "bm25": [], "vector": [], "rerank": []}


def test_retrieval_uses_hard_es_filters_and_distinct_recall_sizes(monkeypatch):
    from weilv.personal_memory_retrieval import retrieve_personal_memories

    calls = _install_retrieval_fakes(monkeypatch, bm25=[_memory()])
    retrieve_personal_memories(object(), _profile(), "query", "key")

    filters = {"user_id": "user-A", "active": True, "review_status": "valid"}
    assert calls["bm25"][0][1] == {
        "size": 10,
        "filters": filters,
        "search_fields": ["retrieval_text"],
    }
    assert calls["vector"][0][1] == {"size": 10, "filters": filters}


@pytest.mark.parametrize(
    "hidden",
    [
        _memory(user_id="user-B"),
        _memory(active=False),
        _memory(review_status="invalid"),
    ],
)
def test_safety_filter_prevents_hidden_memory_from_reaching_reranker(monkeypatch, hidden):
    from weilv.personal_memory_retrieval import retrieve_personal_memories

    visible = _memory("UM-visible")
    calls = _install_retrieval_fakes(monkeypatch, bm25=[hidden, visible])

    result = retrieve_personal_memories(object(), _profile(), "query", "key")

    assert [item["memory_id"] for item in result] == ["UM-visible"]
    assert calls["rerank"][0][1] == [visible["retrieval_text"]]


def test_query_embedding_is_reused_without_embedding_api_call(monkeypatch):
    from weilv.personal_memory_retrieval import retrieve_personal_memories

    calls = _install_retrieval_fakes(monkeypatch, vector=[_memory()])
    vector = [0.2] * 1024
    retrieve_personal_memories(object(), _profile(), "query", "key", query_embedding=vector)

    assert calls["embed"] == []
    assert calls["vector"][0][0][1] is vector


def test_missing_query_embedding_is_generated_exactly_once(monkeypatch):
    from weilv.personal_memory_retrieval import retrieve_personal_memories

    calls = _install_retrieval_fakes(monkeypatch)
    retrieve_personal_memories(object(), _profile(), "query", "key")

    assert calls["embed"] == [(["query"], "key", "query")]


def test_hybrid_merge_deduplicates_before_rerank_and_uses_only_retrieval_text(monkeypatch):
    from weilv.personal_memory_retrieval import retrieve_personal_memories

    shared = _memory(memory_value={"private": "must-not-rerank"})
    calls = _install_retrieval_fakes(monkeypatch, bm25=[shared], vector=[shared])

    result = retrieve_personal_memories(object(), _profile(), "raw query", "key")

    assert len(result) == 1
    assert calls["rerank"] == [("raw query", [shared["retrieval_text"]], "key")]


def test_reranker_controls_final_order_and_limits_only_final_results(monkeypatch):
    from weilv.personal_memory_retrieval import (
        BM25_RECALL_K,
        MEMORY_RERANK_K,
        VECTOR_RECALL_K,
        retrieve_personal_memories,
    )

    candidates = [_memory(f"UM-{number}") for number in range(12)]
    calls = _install_retrieval_fakes(
        monkeypatch,
        bm25=candidates[:10],
        vector=candidates[2:12],
        rerank_order=list(reversed(range(12))),
    )

    result = retrieve_personal_memories(object(), _profile(), "query", "key")

    assert (BM25_RECALL_K, VECTOR_RECALL_K, MEMORY_RERANK_K) == (10, 10, 5)
    assert len(calls["rerank"][0][1]) == 12
    assert [item["memory_id"] for item in result] == ["UM-11", "UM-10", "UM-9", "UM-8", "UM-7"]


def test_empty_candidates_skip_reranker(monkeypatch):
    from weilv.personal_memory_retrieval import retrieve_personal_memories

    calls = _install_retrieval_fakes(monkeypatch)

    assert retrieve_personal_memories(object(), _profile(), "query", "key") == []
    assert calls["rerank"] == []


def test_embed_memory_uses_only_retrieval_text_and_updates_only_embedding(monkeypatch):
    from weilv import personal_memory_retrieval as module

    client = MemoryClient(_memory())
    calls = []
    vector = [0.3] * 1024
    monkeypatch.setattr(
        module,
        "embed_texts",
        lambda texts, api_key, text_type: calls.append((texts, api_key, text_type)) or [vector],
    )

    assert module.embed_memory(client, "user-A", "UM-1", "key") == {
        "status": "embedded",
        "memory_id": "UM-1",
    }
    assert calls == [(["memory=UM-1"], "key", "document")]
    assert client.update_calls == [
        {
            "index": "user_memory_v1",
            "id": "UM-1",
            "doc": {"embedding": vector},
            "refresh": "wait_for",
        }
    ]


def test_embed_memory_rejects_wrong_dimension_without_update(monkeypatch):
    from weilv import personal_memory_retrieval as module

    client = MemoryClient(_memory())
    monkeypatch.setattr(module, "embed_texts", lambda *_args, **_kwargs: [[0.1] * 2])

    with pytest.raises(ValueError, match="1024"):
        module.embed_memory(client, "user-A", "UM-1", "key")
    assert client.update_calls == []


def test_embed_memory_rejects_cross_user_access(monkeypatch):
    from weilv import personal_memory_retrieval as module

    client = MemoryClient(_memory(user_id="user-B"))
    monkeypatch.setattr(
        module,
        "embed_texts",
        lambda *_args, **_kwargs: pytest.fail("embedding must not be called"),
    )

    assert module.embed_memory(client, "user-A", "UM-1", "key") == {
        "status": "rejected",
        "memory_id": "UM-1",
        "reason_code": "memory_owner_mismatch",
    }
