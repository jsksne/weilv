"""Elasticsearch index definitions for the current retrieval POC."""


def get_index_definitions() -> dict[str, dict]:
    return {
        "source_documents_v1": {
            "mappings": {
                "properties": {
                    "document_id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "source_org": {"type": "keyword"},
                    "source_url": {"type": "keyword", "index": False},
                    "snapshot_url": {"type": "keyword", "index": False},
                    "snapshot_note": {"type": "text", "index": False},
                    "published_at": {"type": "date"},
                    "retrieved_at": {"type": "date"},
                    "document_type": {"type": "keyword"},
                    "domains": {"type": "keyword"},
                    "target_stage": {"type": "keyword"},
                    "license_note": {"type": "text", "index": False},
                    "content_hash": {"type": "keyword"},
                    "local_path": {"type": "keyword", "index": False},
                    "review_status": {"type": "keyword"},
                    "conversion_status": {"type": "keyword"},
                    "allowed_for_knowledge_index": {"type": "boolean"},
                }
            }
        },
        "health_knowledge_v1": {
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "document_id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "section_path": {"type": "keyword"},
                    "content": {"type": "text"},
                    "domain": {"type": "keyword"},
                    "target_stage": {"type": "keyword"},
                    "applicability": {"type": "text"},
                    "warnings": {"type": "text"},
                    "source_locator": {"type": "keyword"},
                    "source_url": {"type": "keyword", "index": False},
                    "published_at": {"type": "date"},
                    "knowledge_role": {"type": "keyword"},
                    "proposed_use": {"type": "keyword"},
                    "review_status": {"type": "keyword"},
                    "embedding_model": {"type": "keyword"},
                    "embedding_dim": {"type": "integer"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": 1024,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            }
        },
        "micro_tasks_v1": {
            "mappings": {
                "properties": {
                    "task_id": {"type": "keyword"},
                    "name": {"type": "text"},
                    "instruction": {"type": "text"},
                    "domain": {"type": "keyword"},
                    "covered_domains": {"type": "keyword"},
                    "duration_minutes": {"type": "short"},
                    "intensity": {"type": "keyword"},
                    "scenarios": {"type": "keyword"},
                    "exam_week_fit": {"type": "boolean"},
                    "allow_conditions": {"type": "text"},
                    "stop_conditions": {"type": "text"},
                    "source_chunk_ids": {"type": "keyword"},
                    "review_status": {"type": "keyword"},
                    "title": {"type": "text"},
                    "target_stage": {"type": "keyword"},
                    "context_tags": {"type": "keyword"},
                    "trigger": {"type": "text"},
                    "execution_contexts": {"type": "keyword"},
                    "device_required_during_execution": {"type": "boolean"},
                    "estimated_minutes": {"type": "short"},
                    "burden_level": {"type": "keyword"},
                    "evidence_chunk_ids": {"type": "keyword"},
                    "safety_evidence_chunk_ids": {"type": "keyword"},
                    "applicability": {"type": "text"},
                    "contraindications": {"type": "text"},
                    "safety_level": {"type": "keyword"},
                    "safety_capabilities": {"type": "keyword"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": 1024,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            }
        },
    }


def get_user_memory_index_definitions() -> dict[str, dict]:
    return {
        "user_profiles_v1": {
            "mappings": {
                "properties": {
                    "user_id": {"type": "keyword"},
                    "target_stage": {"type": "keyword"},
                    "memory_enabled": {"type": "boolean"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                }
            }
        },
        "user_memory_v1": {
            "mappings": {
                "properties": {
                    "memory_id": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "memory_type": {"type": "keyword"},
                    "source_type": {"type": "keyword"},
                    "task_id": {"type": "keyword"},
                    "domain": {"type": "keyword"},
                    "memory_key": {"type": "keyword"},
                    "memory_value": {"type": "object", "enabled": False},
                    "retrieval_text": {"type": "text"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                    "active": {"type": "boolean"},
                    "review_status": {"type": "keyword"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": 1024,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            }
        },
        "interaction_logs_v1": {
            "mappings": {
                "properties": {
                    "recommendation_id": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "status": {"type": "keyword"},
                    "selected_task_id": {"type": "keyword"},
                    "target_stage": {"type": "keyword"},
                    "current_context": {"type": "keyword"},
                    "activity_context": {"type": "keyword"},
                    "available_minutes": {"type": "integer"},
                    "created_at": {"type": "date"},
                    "feedback": {
                        "properties": {
                            "completion_status": {"type": "keyword"},
                            "usefulness": {"type": "keyword"},
                            "difficulty": {"type": "keyword"},
                            "reason": {"type": "text", "index": False},
                        }
                    },
                    "feedback_updated_at": {"type": "date"},
                    "memory_persisted": {"type": "boolean"},
                }
            }
        },
        "user_questionnaire_v1": {
            "mappings": {
                "properties": {
                    "user_id": {"type": "keyword"},
                    "questionnaire_id": {"type": "keyword"},
                    "completion_state": {"type": "keyword"},
                    "updated_at": {"type": "date"},
                    "completed_at": {"type": "date"},
                    "answers": {"type": "object", "enabled": False},
                    "memory_record_ids": {"type": "keyword"},
                }
            }
        },
    }


def ensure_user_memory_indices(client, prefix: str = "") -> list[str]:
    created = []
    for logical_name, definition in get_user_memory_index_definitions().items():
        index_name = f"{prefix}{logical_name}"
        if client.indices.exists(index=index_name):
            continue
        client.indices.create(
            index=index_name,
            settings={"number_of_shards": 1, "number_of_replicas": 0},
            mappings=definition["mappings"],
        )
        created.append(index_name)
    return created


def ensure_stage_one_indices(client, prefix: str = "") -> list[str]:
    """Create the three Stage 1 indices if they do not already exist."""

    created = []
    for logical_name, definition in get_index_definitions().items():
        index_name = f"{prefix}{logical_name}"
        if client.indices.exists(index=index_name):
            continue

        client.indices.create(
            index=index_name,
            settings={"number_of_shards": 1, "number_of_replicas": 0},
            mappings=definition["mappings"],
        )
        created.append(index_name)

    return created


def ensure_health_knowledge_index(client, index_name: str) -> bool:
    """Create a named health-knowledge index using the frozen POC mapping."""

    if client.indices.exists(index=index_name):
        return False

    definition = get_index_definitions()["health_knowledge_v1"]
    client.indices.create(
        index=index_name,
        settings={"number_of_shards": 1, "number_of_replicas": 0},
        mappings=definition["mappings"],
    )
    return True
