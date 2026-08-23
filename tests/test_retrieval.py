import pytest


class RecordingClient:
    def __init__(self, search_responses=None, bulk_response=None):
        self.search_responses = list(search_responses or [])
        self.bulk_response = bulk_response or {"errors": False, "items": []}
        self.bulk_calls = []
        self.search_calls = []

    def bulk(self, **kwargs):
        self.bulk_calls.append(kwargs)
        return self.bulk_response

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        return self.search_responses.pop(0)


def _es_response(*hits):
    return {"hits": {"hits": [{"_score": score, "_source": source} for score, source in hits]}}


def test_index_chunks_uses_chunk_id_and_waits_for_refresh():
    from weilv.retrieval import index_chunks

    client = RecordingClient()
    chunk = {
        "chunk_id": "KC-SRC-001-001",
        "document_id": "SRC-001",
        "content": "久坐后起身活动。",
        "embedding": [0.1] * 1024,
    }

    count = index_chunks(client, [chunk], index_name="health_knowledge_v1")

    assert count == 1
    assert client.bulk_calls == [
        {
            "operations": [
                {
                    "index": {
                        "_index": "health_knowledge_v1",
                        "_id": "KC-SRC-001-001",
                    }
                },
                chunk,
            ],
            "refresh": "wait_for",
        }
    ]


def test_index_chunks_raises_when_elasticsearch_reports_bulk_errors():
    from weilv.retrieval import index_chunks

    client = RecordingClient(
        bulk_response={
            "errors": True,
            "items": [
                {
                    "index": {
                        "_id": "bad",
                        "status": 400,
                        "error": {"type": "mapper_parsing_exception"},
                    }
                }
            ],
        }
    )

    with pytest.raises(RuntimeError, match="mapper_parsing_exception"):
        index_chunks(client, [{"chunk_id": "bad"}], index_name="health_knowledge_v1")


def test_bm25_search_requests_top_10_and_keeps_traceability_fields():
    from weilv.retrieval import bm25_search

    source = {
        "chunk_id": "KC-1",
        "document_id": "SRC-001",
        "content": "久坐后起身活动。",
        "source_locator": "source.md:L107-L107",
    }
    client = RecordingClient(search_responses=[_es_response((2.5, source))])

    hits = bm25_search(client, "久坐后怎么活动", "health_knowledge_v1")

    assert hits == [{**source, "bm25_rank": 1, "bm25_score": 2.5}]
    assert client.search_calls == [
        {
            "index": "health_knowledge_v1",
            "size": 10,
            "query": {
                "multi_match": {
                    "query": "久坐后怎么活动",
                    "fields": ["title^2", "content"],
                }
            },
            "source_excludes": ["embedding"],
        }
    ]


def test_vector_search_requests_cosine_index_top_10_candidates():
    from weilv.retrieval import vector_search

    source = {
        "chunk_id": "KC-2",
        "document_id": "SRC-001",
        "content": "保持规律睡眠。",
        "source_locator": "source.md:L137-L137",
    }
    client = RecordingClient(search_responses=[_es_response((0.88, source))])
    vector = [0.2] * 1024

    hits = vector_search(client, vector, "health_knowledge_v1")

    assert hits == [{**source, "vector_rank": 1, "vector_score": 0.88}]
    assert client.search_calls == [
        {
            "index": "health_knowledge_v1",
            "knn": {
                "field": "embedding",
                "query_vector": vector,
                "k": 10,
                "num_candidates": 100,
            },
            "source_excludes": ["embedding"],
        }
    ]


def test_vector_search_rejects_a_non_1024_query_vector():
    from weilv.retrieval import vector_search

    with pytest.raises(ValueError, match="1024"):
        vector_search(RecordingClient(), [0.1, 0.2], "health_knowledge_v1")


def test_bm25_and_vector_search_apply_exact_metadata_filters():
    from weilv.retrieval import bm25_search, vector_search

    client = RecordingClient(search_responses=[_es_response(), _es_response()])
    filters = {"domain": "sleep", "review_status": "content_reviewed"}

    bm25_search(client, "规律作息", "health_knowledge_v1", filters=filters)
    vector_search(client, [0.1] * 1024, "health_knowledge_v1", filters=filters)

    expected_filter = [
        {"term": {"domain": "sleep"}},
        {"term": {"review_status": "content_reviewed"}},
    ]
    assert client.search_calls[0]["query"] == {
        "bool": {
            "must": [{"multi_match": {"query": "规律作息", "fields": ["title^2", "content"]}}],
            "filter": expected_filter,
        }
    }
    assert client.search_calls[1]["knn"]["filter"] == expected_filter


def test_merge_candidates_deduplicates_by_chunk_id_and_keeps_both_scores():
    from weilv.retrieval import merge_candidates

    bm25 = [
        {"chunk_id": "a", "content": "A", "bm25_rank": 1, "bm25_score": 3.0},
        {"chunk_id": "b", "content": "B", "bm25_rank": 2, "bm25_score": 2.0},
    ]
    vector = [
        {"chunk_id": "b", "content": "B", "vector_rank": 1, "vector_score": 0.9},
        {"chunk_id": "c", "content": "C", "vector_rank": 2, "vector_score": 0.8},
    ]

    assert merge_candidates(bm25, vector) == [
        {
            "chunk_id": "a",
            "content": "A",
            "bm25_rank": 1,
            "bm25_score": 3.0,
            "merge_rank": 1,
        },
        {
            "chunk_id": "b",
            "content": "B",
            "bm25_rank": 2,
            "bm25_score": 2.0,
            "vector_rank": 1,
            "vector_score": 0.9,
            "merge_rank": 2,
        },
        {
            "chunk_id": "c",
            "content": "C",
            "vector_rank": 2,
            "vector_score": 0.8,
            "merge_rank": 3,
        },
    ]


def test_apply_rerank_reorders_candidates_using_original_indices():
    from weilv.retrieval import apply_rerank

    candidates = [
        {"chunk_id": "a", "content": "A"},
        {"chunk_id": "b", "content": "B"},
        {"chunk_id": "c", "content": "C"},
    ]

    reranked = apply_rerank(
        candidates,
        [
            {"index": 2, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.40},
            {"index": 1, "relevance_score": 0.10},
        ],
    )

    assert reranked == [
        {"chunk_id": "c", "content": "C", "rerank_rank": 1, "rerank_score": 0.95},
        {"chunk_id": "a", "content": "A", "rerank_rank": 2, "rerank_score": 0.40},
        {"chunk_id": "b", "content": "B", "rerank_rank": 3, "rerank_score": 0.10},
    ]
