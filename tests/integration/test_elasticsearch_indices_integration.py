from uuid import uuid4

import pytest
from elasticsearch import Elasticsearch


@pytest.mark.integration
def test_ensure_stage_one_indices_creates_real_elasticsearch_mappings():
    from weilv.elasticsearch_indices import ensure_stage_one_indices

    client = Elasticsearch("http://127.0.0.1:9200", request_timeout=30)
    if not client.ping():
        pytest.skip("local Elasticsearch is not running")

    prefix = f"weilv_test_{uuid4().hex}_"
    names = [
        f"{prefix}source_documents_v1",
        f"{prefix}health_knowledge_v1",
        f"{prefix}micro_tasks_v1",
    ]

    try:
        ensure_stage_one_indices(client, prefix=prefix)
        assert all(client.indices.exists(index=name) for name in names)

        mapping = client.indices.get_mapping(index=f"{prefix}health_knowledge_v1")
        embedding = mapping[f"{prefix}health_knowledge_v1"]["mappings"]["properties"][
            "embedding"
        ]
        assert embedding["dims"] == 1024
        assert embedding["similarity"] == "cosine"
    finally:
        for name in names:
            if client.indices.exists(index=name):
                client.indices.delete(index=name)
