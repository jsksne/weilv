"""Build the formal micro_tasks_v1 Elasticsearch index from reviewed data."""

import sys

from elasticsearch import Elasticsearch

from weilv.dashscope_models import EMBEDDING_DIMENSION, embed_texts
from weilv.elasticsearch_indices import ensure_stage_one_indices
from weilv.micro_tasks import FORMAL_TASKS_PATH, embedding_text, load_formal_micro_tasks
from weilv.retrieval_slice import _env_value, load_api_key


def bootstrap_micro_tasks(client, api_key: str) -> int:
    tasks = load_formal_micro_tasks(FORMAL_TASKS_PATH)
    ensure_stage_one_indices(client)
    vectors = embed_texts(
        [embedding_text(task) for task in tasks],
        api_key=api_key,
        text_type="document",
    )
    if len(vectors) != len(tasks) or any(len(vector) != EMBEDDING_DIMENSION for vector in vectors):
        raise ValueError(f"micro-task embeddings must have {EMBEDDING_DIMENSION} dimensions")

    operations = []
    for task, vector in zip(tasks, vectors, strict=True):
        operations.extend(
            [
                {"index": {"_index": "micro_tasks_v1", "_id": task["task_id"]}},
                {**task, "embedding": vector},
            ]
        )
    response = client.bulk(operations=operations, refresh="wait_for")
    if response["errors"]:
        errors = [
            item["index"]["error"]
            for item in response["items"]
            if "error" in item["index"]
        ]
        raise RuntimeError(f"Elasticsearch micro-task indexing failed: {errors}")
    return len(tasks)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    env_file = FORMAL_TASKS_PATH.parents[2] / ".env"
    es_url = _env_value("ELASTICSEARCH_URL", env_file) or "http://127.0.0.1:9200"
    client = Elasticsearch(es_url, request_timeout=30)
    try:
        count = bootstrap_micro_tasks(client, load_api_key(env_file))
        print(f"Indexed {count} formal micro-tasks into micro_tasks_v1.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
