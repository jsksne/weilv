"""Elasticsearch indexing and observable two-path retrieval helpers."""

from weilv.dashscope_models import EMBEDDING_DIMENSION


def index_chunks(client, chunks: list[dict], index_name: str) -> int:
    operations = []
    for chunk in chunks:
        operations.extend(
            [
                {"index": {"_index": index_name, "_id": chunk["chunk_id"]}},
                chunk,
            ]
        )

    response = client.bulk(operations=operations, refresh="wait_for")
    if response["errors"]:
        errors = [item["index"]["error"] for item in response["items"] if "error" in item["index"]]
        raise RuntimeError(f"Elasticsearch bulk indexing failed: {errors}")
    return len(chunks)


def _search_hits(response, channel: str) -> list[dict]:
    results = []
    for rank, hit in enumerate(response["hits"]["hits"], start=1):
        results.append(
            {
                **hit["_source"],
                f"{channel}_rank": rank,
                f"{channel}_score": hit["_score"],
            }
        )
    return results


def _exact_filters(filters: dict[str, str] | None) -> list[dict]:
    return [{"term": {field: value}} for field, value in (filters or {}).items()]


def bm25_search(
    client,
    query: str,
    index_name: str,
    size: int = 10,
    filters: dict[str, str] | None = None,
    raw_filters: list[dict] | None = None,
    search_fields: list[str] | None = None,
) -> list[dict]:
    text_query = {
        "multi_match": {"query": query, "fields": search_fields or ["title^2", "content"]}
    }
    exact_filters = [*_exact_filters(filters), *(raw_filters or [])]
    response = client.search(
        index=index_name,
        size=size,
        query=(
            {"bool": {"must": [text_query], "filter": exact_filters}}
            if exact_filters
            else text_query
        ),
        source_excludes=["embedding"],
    )
    return _search_hits(response, "bm25")


def vector_search(
    client,
    query_vector: list[float],
    index_name: str,
    size: int = 10,
    filters: dict[str, str] | None = None,
    raw_filters: list[dict] | None = None,
) -> list[dict]:
    if len(query_vector) != EMBEDDING_DIMENSION:
        raise ValueError(f"query vector must have {EMBEDDING_DIMENSION} dimensions")

    knn = {
        "field": "embedding",
        "query_vector": query_vector,
        "k": size,
        "num_candidates": max(100, size),
    }
    if exact_filters := [*_exact_filters(filters), *(raw_filters or [])]:
        knn["filter"] = exact_filters

    response = client.search(
        index=index_name,
        knn=knn,
        source_excludes=["embedding"],
    )
    return _search_hits(response, "vector")


def merge_candidates(
    bm25: list[dict], vector: list[dict], identity_field: str = "chunk_id"
) -> list[dict]:
    merged: dict[str, dict] = {}
    for hit in [*bm25, *vector]:
        identity = hit[identity_field]
        if identity in merged:
            merged[identity].update(hit)
        else:
            merged[identity] = hit.copy()

    return [
        {**candidate, "merge_rank": rank} for rank, candidate in enumerate(merged.values(), start=1)
    ]


def apply_rerank(candidates: list[dict], rerank_results: list[dict]) -> list[dict]:
    return [
        {
            **candidates[result["index"]],
            "rerank_rank": rank,
            "rerank_score": result["relevance_score"],
        }
        for rank, result in enumerate(rerank_results, start=1)
    ]
