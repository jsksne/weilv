"""Stage 4 Personal Memory embedding and hybrid retrieval."""

from typing import Any

from elasticsearch import NotFoundError

from weilv.dashscope_models import EMBEDDING_DIMENSION, embed_texts, rerank_texts
from weilv.retrieval import (
    apply_rerank,
    bm25_search,
    merge_candidates,
    vector_search,
)
from weilv.user_memory import USER_MEMORY_INDEX, UserProfile

BM25_RECALL_K = 10
VECTOR_RECALL_K = 10
MEMORY_RERANK_K = 5


def embed_memory(client, user_id: str, memory_id: str, api_key: str) -> dict[str, str]:
    try:
        memory = client.get(index=USER_MEMORY_INDEX, id=memory_id)["_source"]
    except NotFoundError:
        return {"status": "not_found", "memory_id": memory_id}
    if memory["user_id"] != user_id:
        return {
            "status": "rejected",
            "memory_id": memory_id,
            "reason_code": "memory_owner_mismatch",
        }

    vector = embed_texts([memory["retrieval_text"]], api_key, "document")[0]
    if len(vector) != EMBEDDING_DIMENSION:
        raise ValueError(f"memory embedding must have {EMBEDDING_DIMENSION} dimensions")
    client.update(
        index=USER_MEMORY_INDEX,
        id=memory_id,
        doc={"embedding": vector},
        refresh="wait_for",
    )
    return {"status": "embedded", "memory_id": memory_id}


def _visible(candidate: dict[str, Any], user_id: str) -> bool:
    return (
        candidate.get("user_id") == user_id
        and candidate.get("active") is True
        and candidate.get("review_status") == "valid"
    )


def retrieve_personal_memories(
    client,
    profile: UserProfile,
    query: str,
    api_key: str,
    query_embedding: list[float] | None = None,
) -> list[dict[str, Any]]:
    if not profile.memory_enabled:
        return []

    filters = {
        "user_id": profile.user_id,
        "active": True,
        "review_status": "valid",
    }
    bm25 = bm25_search(
        client,
        query,
        USER_MEMORY_INDEX,
        size=BM25_RECALL_K,
        filters=filters,
        search_fields=["retrieval_text"],
    )
    if query_embedding is None:
        query_embedding = embed_texts([query], api_key, "query")[0]
    vector = vector_search(
        client,
        query_embedding,
        USER_MEMORY_INDEX,
        size=VECTOR_RECALL_K,
        filters=filters,
    )

    candidates = [
        candidate
        for candidate in merge_candidates(bm25, vector, identity_field="memory_id")
        if _visible(candidate, profile.user_id)
    ]
    if not candidates:
        return []
    rerank_results = rerank_texts(
        query,
        [candidate["retrieval_text"] for candidate in candidates],
        api_key,
    )
    return apply_rerank(candidates, rerank_results)[:MEMORY_RERANK_K]
