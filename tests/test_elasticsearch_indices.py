def test_health_knowledge_index_uses_1024_dimension_cosine_vectors():
    from weilv.elasticsearch_indices import get_index_definitions

    definitions = get_index_definitions()
    embedding = definitions["health_knowledge_v1"]["mappings"]["properties"]["embedding"]

    assert embedding == {
        "type": "dense_vector",
        "dims": 1024,
        "index": True,
        "similarity": "cosine",
    }


def test_definitions_include_the_three_stage_one_indices():
    from weilv.elasticsearch_indices import get_index_definitions

    assert set(get_index_definitions()) == {
        "source_documents_v1",
        "health_knowledge_v1",
        "micro_tasks_v1",
    }


def test_source_documents_definition_keeps_traceability_fields_searchable():
    from weilv.elasticsearch_indices import get_index_definitions

    properties = get_index_definitions()["source_documents_v1"]["mappings"]["properties"]

    assert properties["document_id"] == {"type": "keyword"}
    assert properties["source_url"] == {"type": "keyword", "index": False}
    assert properties["snapshot_url"] == {"type": "keyword", "index": False}
    assert properties["snapshot_note"] == {"type": "text", "index": False}
    assert properties["content_hash"] == {"type": "keyword"}
    assert properties["local_path"] == {"type": "keyword", "index": False}
    assert properties["review_status"] == {"type": "keyword"}


def test_source_documents_definition_contains_every_required_metadata_field():
    from weilv.elasticsearch_indices import get_index_definitions

    properties = get_index_definitions()["source_documents_v1"]["mappings"]["properties"]

    assert set(properties) >= {
        "document_id",
        "title",
        "source_org",
        "source_url",
        "published_at",
        "retrieved_at",
        "document_type",
        "domains",
        "target_stage",
        "license_note",
        "content_hash",
        "local_path",
        "review_status",
    }


def test_health_knowledge_definition_contains_reviewed_chunk_fields():
    from weilv.elasticsearch_indices import get_index_definitions

    properties = get_index_definitions()["health_knowledge_v1"]["mappings"]["properties"]

    assert set(properties) >= {
        "chunk_id",
        "document_id",
        "title",
        "section_path",
        "content",
        "domain",
        "target_stage",
        "applicability",
        "warnings",
        "source_locator",
        "source_url",
        "published_at",
        "knowledge_role",
        "proposed_use",
        "review_status",
        "embedding_model",
        "embedding_dim",
        "embedding",
    }
    assert properties["content"] == {"type": "text"}
    assert properties["review_status"] == {"type": "keyword"}


def test_micro_tasks_definition_contains_safety_and_review_fields():
    from weilv.elasticsearch_indices import get_index_definitions

    properties = get_index_definitions()["micro_tasks_v1"]["mappings"]["properties"]

    assert set(properties) >= {
        "task_id",
        "title",
        "instruction",
        "domain",
        "covered_domains",
        "target_stage",
        "context_tags",
        "trigger",
        "execution_contexts",
        "device_required_during_execution",
        "estimated_minutes",
        "burden_level",
        "evidence_chunk_ids",
        "safety_evidence_chunk_ids",
        "applicability",
        "contraindications",
        "stop_conditions",
        "safety_level",
        "safety_capabilities",
        "review_status",
        "embedding",
    }
    assert properties["embedding"] == {
        "type": "dense_vector",
        "dims": 1024,
        "index": True,
        "similarity": "cosine",
    }
    assert properties["stop_conditions"] == {"type": "text"}
    assert properties["review_status"] == {"type": "keyword"}
    assert properties["covered_domains"] == {"type": "keyword"}
    assert properties["safety_evidence_chunk_ids"] == {"type": "keyword"}
    assert properties["safety_capabilities"] == {"type": "keyword"}
    assert properties["execution_contexts"] == {"type": "keyword"}
    assert properties["device_required_during_execution"] == {"type": "boolean"}


def test_named_health_knowledge_index_reuses_the_frozen_mapping():
    from weilv.elasticsearch_indices import ensure_health_knowledge_index

    class Indices:
        def __init__(self):
            self.calls = []

        def exists(self, index):
            return False

        def create(self, **kwargs):
            self.calls.append(kwargs)

    indices = Indices()
    client = type("Client", (), {"indices": indices})()

    assert ensure_health_knowledge_index(client, "health_knowledge_poc_v1") is True
    assert indices.calls[0]["index"] == "health_knowledge_poc_v1"
    assert indices.calls[0]["mappings"]["properties"]["embedding"] == {
        "type": "dense_vector",
        "dims": 1024,
        "index": True,
        "similarity": "cosine",
    }


def test_serverless_index_creation_omits_shard_settings(monkeypatch):
    from weilv.elasticsearch_indices import get_index_definitions, index_create_kwargs

    definition = get_index_definitions()["health_knowledge_v1"]

    assert index_create_kwargs("health_knowledge_v1", definition, serverless=True) == {
        "index": "health_knowledge_v1",
        "mappings": definition["mappings"],
    }
    monkeypatch.setenv("WEILV_ELASTICSEARCH_SERVERLESS", "true")
    assert "settings" not in index_create_kwargs("health_knowledge_v1", definition)


def test_user_memory_indices_have_the_frozen_stage_four_contract():
    from weilv.elasticsearch_indices import get_user_memory_index_definitions

    definitions = get_user_memory_index_definitions()
    profile = definitions["user_profiles_v1"]["mappings"]["properties"]
    memory = definitions["user_memory_v1"]["mappings"]["properties"]
    interaction = definitions["interaction_logs_v1"]["mappings"]["properties"]

    assert set(profile) == {
        "user_id",
        "target_stage",
        "memory_enabled",
        "created_at",
        "updated_at",
    }
    assert set(memory) == {
        "memory_id",
        "user_id",
        "memory_type",
        "source_type",
        "task_id",
        "domain",
        "memory_key",
        "memory_value",
        "retrieval_text",
        "created_at",
        "updated_at",
        "active",
        "review_status",
        "embedding",
    }
    assert memory["memory_value"] == {"type": "object", "enabled": False}
    assert memory["embedding"] == {
        "type": "dense_vector",
        "dims": 1024,
        "index": True,
        "similarity": "cosine",
    }
    assert set(interaction) == {
        "recommendation_id",
        "user_id",
        "status",
        "selected_task_id",
        "target_stage",
        "current_context",
        "activity_context",
        "available_minutes",
        "created_at",
        "feedback",
        "feedback_updated_at",
        "memory_persisted",
    }
    assert interaction["feedback"] == {
        "properties": {
            "completion_status": {"type": "keyword"},
            "usefulness": {"type": "keyword"},
            "difficulty": {"type": "keyword"},
            "reason": {"type": "text", "index": False},
        }
    }


def test_standard_index_creation_body_keeps_the_frozen_infrastructure_settings(monkeypatch):
    from weilv.elasticsearch_indices import get_index_definitions, index_create_kwargs

    monkeypatch.delenv("WEILV_ELASTICSEARCH_SERVERLESS", raising=False)
    definition = get_index_definitions()["health_knowledge_v1"]

    assert index_create_kwargs("health_knowledge_v1", definition) == {
        "index": "health_knowledge_v1",
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": definition["mappings"],
    }


def test_serverless_index_creation_omits_only_infrastructure_settings(monkeypatch):
    from weilv.elasticsearch_indices import get_index_definitions, index_create_kwargs

    monkeypatch.setenv("WEILV_ELASTICSEARCH_SERVERLESS", "yes")
    definition = get_index_definitions()["health_knowledge_v1"]

    serverless = index_create_kwargs("health_knowledge_v1", definition)
    standard = index_create_kwargs("health_knowledge_v1", definition, serverless=False)

    assert "settings" not in serverless
    assert serverless["mappings"] == standard["mappings"] == definition["mappings"]


def test_all_seven_formal_indices_use_the_same_serverless_compatibility_rule(monkeypatch):
    from weilv.elasticsearch_indices import ensure_stage_one_indices, ensure_user_memory_indices

    class Indices:
        def __init__(self):
            self.calls = []

        def exists(self, *, index):
            return False

        def create(self, **kwargs):
            self.calls.append(kwargs)

    client = type("Client", (), {"indices": Indices()})()
    monkeypatch.setenv("WEILV_ELASTICSEARCH_SERVERLESS", "1")

    assert len(ensure_stage_one_indices(client)) == 3
    assert len(ensure_user_memory_indices(client)) == 4
    assert len(client.indices.calls) == 7
    assert all("settings" not in call for call in client.indices.calls)
    assert all(call["mappings"]["properties"] for call in client.indices.calls)


def test_named_health_knowledge_index_uses_serverless_compatibility_rule(monkeypatch):
    from weilv.elasticsearch_indices import ensure_health_knowledge_index

    class Indices:
        def __init__(self):
            self.calls = []

        def exists(self, *, index):
            return False

        def create(self, **kwargs):
            self.calls.append(kwargs)

    client = type("Client", (), {"indices": Indices()})()
    monkeypatch.setenv("WEILV_ELASTICSEARCH_SERVERLESS", "true")

    assert ensure_health_knowledge_index(client, "weilv-serverless-probe") is True
    assert "settings" not in client.indices.calls[0]
    assert client.indices.calls[0]["mappings"]["properties"]["embedding"]["type"] == "dense_vector"
