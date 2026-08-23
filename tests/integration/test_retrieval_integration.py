from pathlib import Path
from uuid import uuid4

import pytest
from elasticsearch import Elasticsearch


def _client_or_skip():
    client = Elasticsearch("http://127.0.0.1:9200", request_timeout=30)
    if not client.ping():
        client.close()
        pytest.skip("local Elasticsearch is not running")
    return client


def _chunk(chunk_id, content, embedding, domain="sedentary"):
    return {
        "chunk_id": chunk_id,
        "document_id": "SRC-TEST",
        "title": "可追溯测试资料",
        "section_path": ["测试章节"],
        "content": content,
        "domain": domain,
        "target_stage": "both",
        "applicability": "合成集成测试",
        "warnings": "仅用于测试",
        "source_locator": f"test-source.md:{chunk_id}",
        "source_url": "https://example.test/source",
        "published_at": "2026-08-10",
        "review_status": "poc_unreviewed",
        "embedding_model": "test-vector",
        "embedding_dim": 1024,
        "embedding": embedding,
    }


@pytest.mark.integration
def test_real_elasticsearch_indexes_and_searches_bm25_and_cosine_vectors():
    from weilv.elasticsearch_indices import ensure_stage_one_indices
    from weilv.retrieval import bm25_search, index_chunks, vector_search

    client = _client_or_skip()
    prefix = f"weilv_retrieval_test_{uuid4().hex}_"
    names = [
        f"{prefix}source_documents_v1",
        f"{prefix}health_knowledge_v1",
        f"{prefix}micro_tasks_v1",
    ]
    health_index = f"{prefix}health_knowledge_v1"
    first = [1.0, *([0.0] * 1023)]
    second = [0.0, 1.0, *([0.0] * 1022)]

    try:
        ensure_stage_one_indices(client, prefix=prefix)
        assert (
            index_chunks(
                client,
                [
                    _chunk("KC-SEDENTARY", "久坐学习后应起身活动。", first),
                    _chunk("KC-SLEEP", "保持规律睡眠作息。", second, domain="sleep"),
                ],
                health_index,
            )
            == 2
        )

        bm25 = bm25_search(client, "久坐", health_index)
        vector = vector_search(client, first, health_index)
        filtered_bm25 = bm25_search(
            client, "规律", health_index, filters={"domain": "sleep"}
        )
        filtered_vector = vector_search(
            client, first, health_index, filters={"domain": "sleep"}
        )

        assert bm25[0]["chunk_id"] == "KC-SEDENTARY"
        assert vector[0]["chunk_id"] == "KC-SEDENTARY"
        assert filtered_bm25[0]["chunk_id"] == "KC-SLEEP"
        assert filtered_vector[0]["chunk_id"] == "KC-SLEEP"
        assert bm25[0]["document_id"] == "SRC-TEST"
        assert vector[0]["source_locator"] == "test-source.md:KC-SEDENTARY"
    finally:
        for name in names:
            if client.indices.exists(index=name):
                client.indices.delete(index=name)
        client.close()


@pytest.mark.integration
@pytest.mark.live_model
def test_live_stage_one_two_retrieval_slice_is_traceable():
    from weilv.elasticsearch_indices import ensure_stage_one_indices
    from weilv.retrieval_slice import load_api_key, load_chunks, run_slice

    try:
        api_key = load_api_key(Path(".env"))
    except RuntimeError:
        pytest.skip("DASHSCOPE_API_KEY is not configured")

    client = _client_or_skip()
    prefix = f"weilv_live_test_{uuid4().hex}_"
    names = [
        f"{prefix}source_documents_v1",
        f"{prefix}health_knowledge_v1",
        f"{prefix}micro_tasks_v1",
    ]

    try:
        ensure_stage_one_indices(client, prefix=prefix)
        result = run_slice(
            "久坐复习一小时后应该怎么活动？",
            load_chunks(Path("data/metadata/knowledge_chunks.poc.jsonl")),
            client,
            api_key,
            index_name=f"{prefix}health_knowledge_v1",
        )

        assert result["bm25"]
        assert result["vector"]
        assert result["merged"]
        assert result["reranked"]
        assert all(item["document_id"] == "SRC-001" for item in result["final"])
        assert all(item["source_locator"] for item in result["final"])
    finally:
        for name in names:
            if client.indices.exists(index=name):
                client.indices.delete(index=name)
        client.close()
