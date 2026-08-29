"""Build the formal health_knowledge_v1 Elasticsearch index from reviewed chunks."""

import json
import sys
from pathlib import Path

from weilv.dashscope_models import EMBEDDING_DIMENSION, EMBEDDING_MODEL, embed_texts
from weilv.elasticsearch_indices import ensure_stage_one_indices
from weilv.retrieval import index_chunks
from weilv.retrieval_slice import create_elasticsearch_client, load_api_key

KNOWLEDGE_PATH = Path("data/metadata/health_knowledge_v1.jsonl")


def bootstrap_health_knowledge(client, api_key: str) -> int:
    chunks = [json.loads(line) for line in KNOWLEDGE_PATH.read_text(encoding="utf-8").splitlines()]
    ensure_stage_one_indices(client)
    # text-embedding-v4 单次批量上限 10；import helper 按批嵌入，不改模型核心。
    batch_size = 10
    texts = [chunk["content"] for chunk in chunks]
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(
            embed_texts(
                texts[start : start + batch_size],
                api_key=api_key,
                text_type="document",
            )
        )
    if len(vectors) != len(chunks) or any(len(v) != EMBEDDING_DIMENSION for v in vectors):
        raise ValueError("health-knowledge embeddings must have 1024 dimensions")

    documents = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        documents.append(
            {
                **chunk,
                "embedding_model": EMBEDDING_MODEL,
                "embedding_dim": EMBEDDING_DIMENSION,
                "embedding": vector,
            }
        )
    return index_chunks(client, documents, "health_knowledge_v1")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    env_file = Path(".env")
    client = create_elasticsearch_client(env_file)
    try:
        count = bootstrap_health_knowledge(client, load_api_key(env_file))
        print(f"health_knowledge_v1: {count} chunks indexed")
    finally:
        client.close()


if __name__ == "__main__":
    main()
