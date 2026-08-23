"""Runnable Stage 1/2 retrieval slice with fully visible intermediate results."""

import argparse
import json
import os
import sys
from pathlib import Path

from elasticsearch import Elasticsearch

from weilv.dashscope_models import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    embed_texts,
    rerank_texts,
)
from weilv.elasticsearch_indices import ensure_health_knowledge_index
from weilv.retrieval import (
    apply_rerank,
    bm25_search,
    index_chunks,
    merge_candidates,
    vector_search,
)

DEFAULT_INDEX = "health_knowledge_poc_v1"


def load_chunks(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _env_value(name: str, env_file: Path) -> str | None:
    if value := os.getenv(name):
        return value
    if not env_file.exists():
        return None

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name and value.strip():
            return value.strip().strip("\"'")
    return None


def load_api_key(env_file: Path = Path(".env")) -> str:
    api_key = _env_value("DASHSCOPE_API_KEY", env_file)
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured in the environment or .env")
    return api_key


def validate_index_target(chunks: list[dict], index_name: str) -> None:
    if index_name == "health_knowledge_v1" and any(
        chunk.get("review_status") != "content_reviewed" for chunk in chunks
    ):
        raise RuntimeError(
            "health_knowledge_v1 only accepts chunks with review_status=content_reviewed"
        )


def run_slice(
    query: str,
    chunks: list[dict],
    client,
    api_key: str,
    index_name: str = DEFAULT_INDEX,
) -> dict:
    validate_index_target(chunks, index_name)
    document_vectors = embed_texts(
        [chunk["content"] for chunk in chunks],
        api_key=api_key,
        text_type="document",
    )
    indexed_chunks = [
        {
            **chunk,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIMENSION,
            "embedding": vector,
        }
        for chunk, vector in zip(chunks, document_vectors, strict=True)
    ]
    indexed_count = index_chunks(client, indexed_chunks, index_name)

    query_vector = embed_texts([query], api_key=api_key, text_type="query")[0]
    bm25 = bm25_search(client, query, index_name)
    vector = vector_search(client, query_vector, index_name)
    merged = merge_candidates(bm25, vector)
    rerank_results = rerank_texts(
        query,
        [candidate["content"] for candidate in merged],
        api_key=api_key,
    )
    reranked = apply_rerank(merged, rerank_results)

    return {
        "query": query,
        "indexed_count": indexed_count,
        "bm25": bm25,
        "vector": vector,
        "merged": merged,
        "reranked": reranked,
        "final": reranked[:5],
    }


def _print_stage(title: str, candidates: list[dict]) -> None:
    print(f"\n=== {title} ===")
    for position, candidate in enumerate(candidates, start=1):
        scores = " ".join(
            f"{name}={candidate[name]:.6f}"
            for name in ("bm25_score", "vector_score", "rerank_score")
            if name in candidate
        )
        print(
            f"{position}. chunk_id={candidate['chunk_id']} "
            f"document_id={candidate['document_id']} {scores}"
        )
        print(f"   source={candidate['source_locator']}")
        print(f"   content={candidate['content']}")


def print_results(result: dict) -> None:
    print("=== Query ===")
    print(result["query"])
    _print_stage("BM25 Top 10", result["bm25"])
    _print_stage("Vector Cosine kNN Top 10", result["vector"])
    _print_stage("合并候选 / Reranker 前", result["merged"])
    _print_stage("Reranker 后", result["reranked"])
    _print_stage("最终 Top 结果", result["final"])


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run the Weilv Stage 1/2 retrieval slice")
    parser.add_argument("query", help="健康检索问题")
    parser.add_argument(
        "--chunks",
        type=Path,
        default=Path("data/metadata/knowledge_chunks.poc.jsonl"),
        help="待向量化的知识 Chunk JSONL",
    )
    parser.add_argument("--index", default=DEFAULT_INDEX)
    args = parser.parse_args()

    env_file = Path(".env")
    api_key = load_api_key(env_file)
    es_url = _env_value("ELASTICSEARCH_URL", env_file) or "http://127.0.0.1:9200"
    chunks = load_chunks(args.chunks)
    if any(chunk.get("review_status") != "content_reviewed" for chunk in chunks):
        print("WARNING: 包含未完成人工内容审核的技术 POC Chunk；结果不得用于健康推荐。")

    client = Elasticsearch(es_url, request_timeout=30)
    try:
        if not client.ping():
            raise RuntimeError(f"Elasticsearch is not reachable: {es_url}")
        ensure_health_knowledge_index(client, args.index)
        print_results(run_slice(args.query, chunks, client, api_key, args.index))
    finally:
        client.close()


if __name__ == "__main__":
    main()
