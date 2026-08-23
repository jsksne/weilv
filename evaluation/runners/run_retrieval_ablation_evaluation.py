"""Run the frozen Stage 6D-1 Knowledge Retrieval ablation evaluation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import math
import platform
import random
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch

from weilv.basic_rag import _knowledge_filters
from weilv.dashscope_models import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    RERANK_MODEL,
    embed_texts,
    rerank_texts,
)
from weilv.elasticsearch_indices import get_index_definitions
from weilv.retrieval import (
    apply_rerank,
    bm25_search,
    merge_candidates,
    vector_search,
)
from weilv.retrieval_slice import _env_value, load_api_key

EXPECTED_GOLD_SHA256 = "2fb07424641826c98f2c722e3e13dedf5a95c12fccad726fa32ddb9f3f9599b0"
EXPECTED_CORPUS_SHA256 = "e04e27a27175211d32c57f36b715bc19faf45ca6be7ccd8e993a86a668392938"
BM25_RECALL_K = 10
VECTOR_RECALL_K = 10
RRF_K = 60
METHODS = ("BM25", "Vector", "Hybrid-RRF", "Hybrid+Reranker")
CLAIM_DEFINITIONS = (
    (
        "CR-RET-001",
        "Hybrid candidate generation improves or preserves relevant-knowledge recall relative to either single retrieval route.",
    ),
    (
        "CR-RET-002",
        "qwen3-rerank improves ranked relevance quality over the preregistered Hybrid-RRF baseline.",
    ),
    (
        "CR-RET-003",
        "Hybrid+Reranker provides the strongest overall retrieval quality among the evaluated methods.",
    ),
    (
        "CR-RET-REAL-001",
        "Improved retrieval metrics directly improve real adolescents' health outcomes.",
    ),
)
DEFAULT_GOLD_PATH = Path("evaluation/datasets/retrieval_gold_v1.jsonl")
DEFAULT_CORPUS_PATH = Path("data/metadata/health_knowledge_v1.jsonl")
DEFAULT_CORPUS_MANIFEST_PATH = Path("evaluation/manifests/retrieval_knowledge_corpus_v1.json")
DEFAULT_GOLD_MANIFEST_PATH = Path("evaluation/manifests/retrieval_gold_v1_manifest.json")
DEFAULT_OUTPUT_ROOT = Path("evaluation/runs")
DEFAULT_CLAIM_PATH = Path("evaluation/claims/claim_registry_retrieval_v1.csv")
RELEVANT_PRODUCTION_SOURCES = (
    Path("src/weilv/basic_rag.py"),
    Path("src/weilv/dashscope_models.py"),
    Path("src/weilv/elasticsearch_indices.py"),
    Path("src/weilv/retrieval.py"),
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _eligible_corpus(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (
            chunk
            for chunk in chunks
            if chunk.get("review_status") == "content_reviewed"
            and "rag_knowledge" in chunk.get("proposed_use", [])
            and "exclude_from_normal_recommendation" not in chunk.get("proposed_use", [])
            and "restricted_clinical" not in chunk.get("proposed_use", [])
            and chunk.get("knowledge_role") != "restricted_clinical"
        ),
        key=lambda chunk: chunk["chunk_id"],
    )


def corpus_sha256(chunks: list[dict[str, Any]]) -> str:
    payload = (
        "\n".join(
            json.dumps(chunk, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for chunk in chunks
        )
        + "\n"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_frozen_inputs(
    *,
    gold_path: Path,
    corpus_path: Path,
    corpus_manifest_path: Path,
) -> dict[str, Any]:
    actual_gold_sha = file_sha256(gold_path)
    if actual_gold_sha != EXPECTED_GOLD_SHA256:
        raise RuntimeError(
            f"Gold SHA-256 mismatch: expected {EXPECTED_GOLD_SHA256}, got {actual_gold_sha}"
        )

    all_chunks = _read_jsonl(corpus_path)
    frozen_chunks = _eligible_corpus(all_chunks)
    actual_corpus_sha = corpus_sha256(frozen_chunks)
    if actual_corpus_sha != EXPECTED_CORPUS_SHA256:
        raise RuntimeError(
            f"Corpus SHA-256 mismatch: expected {EXPECTED_CORPUS_SHA256}, got {actual_corpus_sha}"
        )

    manifest = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
    chunk_ids = [chunk["chunk_id"] for chunk in frozen_chunks]
    if (
        manifest.get("corpus_sha256") != EXPECTED_CORPUS_SHA256
        or manifest.get("chunk_count") != 27
        or manifest.get("chunk_ids") != chunk_ids
    ):
        raise RuntimeError("Frozen corpus manifest does not match the recomputed corpus")

    cases = _read_jsonl(gold_path)
    case_ids = [case.get("case_id") for case in cases]
    if len(cases) != 24 or len(set(case_ids)) != 24:
        raise RuntimeError("Gold must contain 24 unique cases")
    frozen_id_set = set(chunk_ids)
    for case in cases:
        references = set(case.get("relevance_2_chunk_ids", [])) | set(
            case.get("relevance_1_chunk_ids", [])
        )
        if not case.get("relevance_2_chunk_ids"):
            raise RuntimeError(f"Gold case lacks relevance=2: {case['case_id']}")
        if references - frozen_id_set:
            raise RuntimeError(
                f"Gold case references chunks outside frozen corpus: {case['case_id']}"
            )
        if case.get("review_status") != "reviewed" or case.get("human_reviewed") is not True:
            raise RuntimeError(f"Gold case is not human-reviewed: {case['case_id']}")

    return {
        "cases": cases,
        "corpus_chunks": frozen_chunks,
        "corpus_manifest": manifest,
        "gold_sha256": actual_gold_sha,
        "corpus_sha256": actual_corpus_sha,
    }


def reciprocal_rank_fusion(
    bm25_ranking: list[dict[str, Any]],
    vector_ranking: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ranks: dict[str, dict[str, int | None]] = {}
    for position, row in enumerate(bm25_ranking, start=1):
        ranks.setdefault(row["chunk_id"], {"bm25_rank": None, "vector_rank": None})["bm25_rank"] = (
            int(row.get("bm25_rank", position))
        )
    for position, row in enumerate(vector_ranking, start=1):
        ranks.setdefault(row["chunk_id"], {"bm25_rank": None, "vector_rank": None})[
            "vector_rank"
        ] = int(row.get("vector_rank", position))

    rows = []
    for chunk_id, source_ranks in ranks.items():
        available = [rank for rank in source_ranks.values() if rank is not None]
        score = sum(1 / (RRF_K + rank) for rank in available)
        rows.append(
            {
                "chunk_id": chunk_id,
                **source_ranks,
                "best_source_rank": min(available),
                "rrf_score": score,
            }
        )
    rows.sort(key=lambda row: (-row["rrf_score"], row["best_source_rank"], row["chunk_id"]))
    return [{**row, "rrf_rank": rank} for rank, row in enumerate(rows, start=1)]


def _dcg(relevances: list[int], k: int) -> float:
    return sum(
        (2**relevance - 1) / math.log2(rank + 1)
        for rank, relevance in enumerate(relevances[:k], start=1)
    )


def calculate_ranking_metrics(
    ranking_ids: list[str],
    *,
    relevance_2_ids: list[str],
    relevance_1_ids: list[str],
) -> dict[str, dict[int, float]]:
    direct = set(relevance_2_ids)
    relevant = direct | set(relevance_1_ids)
    if not direct or not relevant:
        raise ValueError("Gold relevance sets must contain at least one direct answer")

    recall = {}
    direct_recall = {}
    for k in (1, 3, 5, 10):
        top_k = set(ranking_ids[:k])
        recall[k] = len(top_k & relevant) / len(relevant)
        direct_recall[k] = len(top_k & direct) / len(direct)

    reciprocal_rank = 0.0
    for rank, chunk_id in enumerate(ranking_ids[:10], start=1):
        if chunk_id in relevant:
            reciprocal_rank = 1 / rank
            break

    graded = {chunk_id: 2 for chunk_id in direct}
    graded.update({chunk_id: 1 for chunk_id in relevance_1_ids})
    observed = [graded.get(chunk_id, 0) for chunk_id in ranking_ids]
    ideal = sorted(graded.values(), reverse=True)
    ndcg = {}
    for k in (3, 5, 10):
        idcg = _dcg(ideal, k)
        ndcg[k] = _dcg(observed, k) / idcg if idcg else 0.0

    return {
        "Recall": recall,
        "DirectRecall": direct_recall,
        "MRR": {10: reciprocal_rank},
        "nDCG": ndcg,
    }


def hybrid_candidate_pool_recall(
    candidate_ids: list[str],
    *,
    relevance_2_ids: list[str],
    relevance_1_ids: list[str],
) -> float:
    relevant = set(relevance_2_ids) | set(relevance_1_ids)
    if not relevant:
        raise ValueError("Gold relevance set must not be empty")
    return len(set(candidate_ids) & relevant) / len(relevant)


def validate_production_contract() -> dict[str, Any]:
    bm25_default = inspect.signature(bm25_search).parameters["size"].default
    vector_default = inspect.signature(vector_search).parameters["size"].default
    vector_mapping = get_index_definitions()["health_knowledge_v1"]["mappings"]["properties"][
        "embedding"
    ]
    if bm25_default != BM25_RECALL_K or vector_default != VECTOR_RECALL_K:
        raise RuntimeError("Production retrieval recall K no longer matches frozen constants")
    if (
        EMBEDDING_MODEL != "text-embedding-v4"
        or EMBEDDING_DIMENSION != 1024
        or RERANK_MODEL != "qwen3-rerank"
        or vector_mapping.get("dims") != 1024
        or vector_mapping.get("similarity") != "cosine"
    ):
        raise RuntimeError("Production model or vector mapping contract changed")
    return {
        "BM25_RECALL_K": BM25_RECALL_K,
        "VECTOR_RECALL_K": VECTOR_RECALL_K,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dim": EMBEDDING_DIMENSION,
        "vector_similarity": vector_mapping["similarity"],
        "reranker_model": RERANK_MODEL,
        "RRF_K": RRF_K,
        "RRF_semantics": "evaluation_only_not_production_ranking",
    }


def build_hybrid_candidate_pool(
    bm25_ranking: list[dict[str, Any]],
    vector_ranking: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = merge_candidates(bm25_ranking, vector_ranking)
    identities = [row["chunk_id"] for row in merged]
    if len(identities) != len(set(identities)):
        raise RuntimeError("Production candidate merge did not deduplicate chunk IDs")
    return merged


def _route_ranking(rows: list[dict[str, Any]], channel: str) -> list[dict[str, Any]]:
    return [
        {
            "rank": rank,
            "chunk_id": row["chunk_id"],
            f"{channel}_score": row[f"{channel}_score"],
        }
        for rank, row in enumerate(rows, start=1)
    ]


def _rrf_output(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rank": row["rrf_rank"],
            "chunk_id": row["chunk_id"],
            "rrf_score": row["rrf_score"],
            "bm25_rank": row["bm25_rank"],
            "vector_rank": row["vector_rank"],
            "best_source_rank": row["best_source_rank"],
        }
        for row in rows
    ]


def _rerank_output(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "bm25_rank",
        "bm25_score",
        "vector_rank",
        "vector_score",
        "merge_rank",
    )
    return [
        {
            "rank": row["rerank_rank"],
            "chunk_id": row["chunk_id"],
            "rerank_score": row["rerank_score"],
            **{field: row[field] for field in fields if field in row},
        }
        for row in rows
    ]


def execute_case(
    case: dict[str, Any],
    *,
    client,
    api_key: str,
    knowledge_index: str = "health_knowledge_v1",
    embed_fn=None,
    bm25_fn=None,
    vector_fn=None,
    rerank_fn=None,
    clock_fn=None,
) -> dict[str, Any]:
    embed_fn = embed_fn or embed_texts
    bm25_fn = bm25_fn or bm25_search
    vector_fn = vector_fn or vector_search
    rerank_fn = rerank_fn or rerank_texts
    clock_fn = clock_fn or time.perf_counter
    filters = _knowledge_filters()
    query = case["query"]

    started = clock_fn()
    bm25_hits = bm25_fn(
        client,
        query,
        knowledge_index,
        size=BM25_RECALL_K,
        raw_filters=filters,
    )
    bm25_ms = (clock_fn() - started) * 1000
    if len(bm25_hits) > BM25_RECALL_K:
        raise RuntimeError("BM25 returned more than the frozen Top 10")

    vector_started = clock_fn()
    query_vector = embed_fn([query], api_key, "query")[0]
    if len(query_vector) != EMBEDDING_DIMENSION:
        raise RuntimeError("Query embedding dimension does not match production contract")
    vector_hits = vector_fn(
        client,
        query_vector,
        knowledge_index,
        size=VECTOR_RECALL_K,
        raw_filters=filters,
    )
    vector_ms = (clock_fn() - vector_started) * 1000
    if len(vector_hits) > VECTOR_RECALL_K:
        raise RuntimeError("Vector retrieval returned more than the frozen Top 10")

    candidate_pool = build_hybrid_candidate_pool(bm25_hits, vector_hits)
    candidate_ids = [row["chunk_id"] for row in candidate_pool]

    rrf_started = clock_fn()
    rrf_full = reciprocal_rank_fusion(bm25_hits, vector_hits)
    rrf_top10 = rrf_full[:10]
    rrf_ms = (clock_fn() - rrf_started) * 1000

    rerank_started = clock_fn()
    if candidate_pool:
        rerank_results = rerank_fn(
            query,
            [candidate["content"] for candidate in candidate_pool],
            api_key,
        )
        indices = [row["index"] for row in rerank_results]
        if len(indices) != len(candidate_pool) or set(indices) != set(range(len(candidate_pool))):
            raise RuntimeError("Reranker did not return a complete unique candidate ordering")
        reranked = apply_rerank(candidate_pool, rerank_results)
        reranker_calls = 1
    else:
        reranked = []
        reranker_calls = 0
    rerank_ms = (clock_fn() - rerank_started) * 1000

    bm25_output = _route_ranking(bm25_hits, "bm25")
    vector_output = _route_ranking(vector_hits, "vector")
    rrf_output = _rrf_output(rrf_top10)
    rerank_output = _rerank_output(reranked)
    gold_r2 = case["relevance_2_chunk_ids"]
    gold_r1 = case["relevance_1_chunk_ids"]
    method_rankings = {
        "BM25": [row["chunk_id"] for row in bm25_output],
        "Vector": [row["chunk_id"] for row in vector_output],
        "Hybrid-RRF": [row["chunk_id"] for row in rrf_output],
        "Hybrid+Reranker": [row["chunk_id"] for row in rerank_output],
    }
    per_method_metrics = {
        method: calculate_ranking_metrics(
            ranking,
            relevance_2_ids=gold_r2,
            relevance_1_ids=gold_r1,
        )
        for method, ranking in method_rankings.items()
    }

    return {
        "case_id": case["case_id"],
        "case_family_id": case["case_family_id"],
        "domain": case["domain"],
        "query": query,
        "gold_relevance_2_ids": gold_r2,
        "gold_relevance_1_ids": gold_r1,
        "bm25_ranking": bm25_output,
        "vector_ranking": vector_output,
        "hybrid_candidate_ids": candidate_ids,
        "hybrid_candidate_count": len(candidate_ids),
        "rrf_ranking": rrf_output,
        "rerank_ranking": rerank_output,
        "per_method_metrics": per_method_metrics,
        "hybrid_candidate_pool_recall": hybrid_candidate_pool_recall(
            candidate_ids,
            relevance_2_ids=gold_r2,
            relevance_1_ids=gold_r1,
        ),
        "latency_ms_by_method": {
            "BM25": bm25_ms,
            "Vector": vector_ms,
            "Hybrid-RRF": rrf_ms,
            "Hybrid+Reranker": rerank_ms,
        },
        "model_call_counts": {
            "text_embedding_v4": 1,
            "qwen3_rerank": reranker_calls,
            "qwen_plus": 0,
        },
    }


def _metric_at(method_metrics: dict[str, Any], metric: str, k: int) -> float:
    values = method_metrics[metric]
    return float(values[k] if k in values else values[str(k)])


def aggregate_metrics(results: list[dict[str, Any]], *, run_id: str) -> list[dict[str, Any]]:
    if not results:
        raise ValueError("Cannot aggregate an empty result set")
    metric_ks = (
        ("Recall", (1, 3, 5, 10)),
        ("DirectRecall", (1, 3, 5, 10)),
        ("MRR", (10,)),
        ("nDCG", (3, 5, 10)),
    )
    rows = []
    for method in METHODS:
        for metric, ks in metric_ks:
            for k in ks:
                values = [
                    _metric_at(result["per_method_metrics"][method], metric, k)
                    for result in results
                ]
                rows.append(
                    {
                        "method": method,
                        "metric": metric,
                        "k": k,
                        "value": statistics.mean(values),
                        "n_cases": len(values),
                        "run_id": run_id,
                    }
                )
    pool_values = [result["hybrid_candidate_pool_recall"] for result in results]
    rows.append(
        {
            "method": "Hybrid Candidate Pool",
            "metric": "Hybrid Candidate Pool Recall",
            "k": None,
            "value": statistics.mean(pool_values),
            "n_cases": len(pool_values),
            "run_id": run_id,
        }
    )
    return rows


def _metric_row_lookup(rows: list[dict[str, Any]]) -> dict[tuple[str, str, int | None], float]:
    return {(row["method"], row["metric"], row["k"]): float(row["value"]) for row in rows}


def calculate_paired_improvements(
    metric_rows: list[dict[str, Any]], *, run_id: str
) -> list[dict[str, Any]]:
    lookup = _metric_row_lookup(metric_rows)
    rows = []
    for baseline in ("BM25", "Vector", "Hybrid-RRF"):
        for metric, k in (("Recall", 5), ("MRR", 10), ("nDCG", 5)):
            baseline_value = lookup[(baseline, metric, k)]
            target_value = lookup[("Hybrid+Reranker", metric, k)]
            difference = target_value - baseline_value
            rows.append(
                {
                    "target_method": "Hybrid+Reranker",
                    "baseline_method": baseline,
                    "metric": metric,
                    "k": k,
                    "target_value": target_value,
                    "baseline_value": baseline_value,
                    "absolute_difference": difference,
                    "relative_difference": (
                        difference / baseline_value if baseline_value != 0 else None
                    ),
                    "run_id": run_id,
                }
            )
    return rows


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Percentile requires at least one value")
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def bootstrap_paired_ci(
    results: list[dict[str, Any]],
    *,
    baseline_method: str,
    seed: int = 20260816,
    resamples: int = 10000,
) -> dict[str, Any]:
    differences = [
        _metric_at(result["per_method_metrics"]["Hybrid+Reranker"], "nDCG", 5)
        - _metric_at(result["per_method_metrics"][baseline_method], "nDCG", 5)
        for result in results
    ]
    if not differences or resamples < 1:
        raise ValueError("Bootstrap requires cases and at least one resample")
    generator = random.Random(seed)
    estimates = [
        statistics.mean(generator.choice(differences) for _ in differences)
        for _ in range(resamples)
    ]
    return {
        "target_method": "Hybrid+Reranker",
        "baseline_method": baseline_method,
        "metric": "nDCG",
        "k": 5,
        "observed_absolute_difference": statistics.mean(differences),
        "ci_lower": _percentile(estimates, 0.025),
        "ci_upper": _percentile(estimates, 0.975),
        "confidence_level": 0.95,
        "seed": seed,
        "resamples": resamples,
        "n_cases": len(differences),
    }


def _directional_status(differences: list[float], *, improvement_required: bool) -> str:
    tolerance = 1e-12
    if all(value >= -tolerance for value in differences):
        if not improvement_required or any(value > tolerance for value in differences):
            return "SUPPORTED"
        return "NOT_SUPPORTED"
    if all(value <= tolerance for value in differences):
        return "NOT_SUPPORTED"
    return "MIXED"


def evaluate_claims(metric_rows: list[dict[str, Any]], *, run_id: str) -> list[dict[str, Any]]:
    lookup = _metric_row_lookup(metric_rows)
    pool = lookup[("Hybrid Candidate Pool", "Hybrid Candidate Pool Recall", None)]
    route_recalls = [
        lookup[("BM25", "Recall", 10)],
        lookup[("Vector", "Recall", 10)],
    ]
    claim_1_differences = [pool - value for value in route_recalls]
    claim_2_differences = [
        lookup[("Hybrid+Reranker", metric, k)] - lookup[("Hybrid-RRF", metric, k)]
        for metric, k in (("Recall", 5), ("MRR", 10), ("nDCG", 5))
    ]
    claim_3_differences = []
    for metric, k in (("Recall", 5), ("MRR", 10), ("nDCG", 5)):
        strongest_baseline = max(
            lookup[(method, metric, k)] for method in ("BM25", "Vector", "Hybrid-RRF")
        )
        claim_3_differences.append(lookup[("Hybrid+Reranker", metric, k)] - strongest_baseline)

    statuses = {
        "CR-RET-001": _directional_status(claim_1_differences, improvement_required=False),
        "CR-RET-002": _directional_status(claim_2_differences, improvement_required=True),
        "CR-RET-003": _directional_status(claim_3_differences, improvement_required=True),
        "CR-RET-REAL-001": "UNSUPPORTED",
    }
    rules = {
        "CR-RET-001": "SUPPORTED iff candidate-pool recall is >= both BM25 Recall@10 and Vector Recall@10; MIXED iff only one route is preserved.",
        "CR-RET-002": "SUPPORTED iff Hybrid+Reranker is non-inferior to Hybrid-RRF on Recall@5, MRR@10, and nDCG@5 with at least one strict improvement; MIXED for split directions.",
        "CR-RET-003": "SUPPORTED iff Hybrid+Reranker is non-inferior to the best other method on Recall@5, MRR@10, and nDCG@5 with at least one strict improvement; MIXED for split directions.",
        "CR-RET-REAL-001": "Always UNSUPPORTED because this retrieval benchmark does not measure real adolescent health outcomes.",
    }
    evidence = {
        "CR-RET-001": claim_1_differences,
        "CR-RET-002": claim_2_differences,
        "CR-RET-003": claim_3_differences,
        "CR-RET-REAL-001": ["not_measured"],
    }
    claim_text = dict(CLAIM_DEFINITIONS)
    return [
        {
            "claim_id": claim_id,
            "claim": claim_text[claim_id],
            "status": statuses[claim_id],
            "evaluation_rule": rules[claim_id],
            "evidence": json.dumps(evidence[claim_id], ensure_ascii=False),
            "run_id": run_id,
        }
        for claim_id, _ in CLAIM_DEFINITIONS
    ]


def summarize_latency(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for method in METHODS:
        values = [float(result["latency_ms_by_method"][method]) for result in results]
        rows.append(
            {
                "method": method,
                "p50_ms": _percentile(values, 0.50),
                "p95_ms": _percentile(values, 0.95),
                "n_cases": len(values),
            }
        )
    return rows


def build_artifact_payloads(
    results: list[dict[str, Any]],
    *,
    run_id: str,
    bootstrap_resamples: int = 10000,
) -> dict[str, Any]:
    metric_rows = aggregate_metrics(results, run_id=run_id)
    paired = calculate_paired_improvements(metric_rows, run_id=run_id)
    bootstrap = [
        bootstrap_paired_ci(
            results,
            baseline_method=baseline,
            seed=20260816,
            resamples=bootstrap_resamples,
        )
        for baseline in ("BM25", "Vector", "Hybrid-RRF")
    ]
    latency = summarize_latency(results)
    lookup = _metric_row_lookup(metric_rows)
    paper_rows = [
        {
            "experiment": "knowledge_retrieval_ablation",
            "method": row["method"],
            "metric": row["metric"],
            "k": row["k"],
            "value": row["value"],
            "n": row["n_cases"],
            "provenance_level": "A+B+C",
            "run_id": run_id,
        }
        for row in metric_rows
    ]
    table_rows = [
        {
            "method": method,
            "Recall@5": lookup[(method, "Recall", 5)],
            "Recall@10": lookup[(method, "Recall", 10)],
            "MRR@10": lookup[(method, "MRR", 10)],
            "nDCG@5": lookup[(method, "nDCG", 5)],
            "nDCG@10": lookup[(method, "nDCG", 10)],
            "DirectRecall@5": lookup[(method, "DirectRecall", 5)],
        }
        for method in METHODS
    ]
    claims = evaluate_claims(metric_rows, run_id=run_id)
    metrics_json = {
        "run_id": run_id,
        "n_cases": len(results),
        "macro_average": True,
        "metrics": metric_rows,
        "paired_improvements": paired,
        "bootstrap_ci": bootstrap,
        "latency": {
            "summary": latency,
            "latency_not_for_primary_claim": True,
            "warmup_performed": False,
        },
    }
    return {
        "metric_rows": metric_rows,
        "metrics_json": metrics_json,
        "paper_rows": paper_rows,
        "table_rows": table_rows,
        "paired_rows": paired,
        "bootstrap_ci": bootstrap,
        "latency_rows": latency,
        "claim_rows": claims,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


CLAIM_FIELDS = (
    "claim_id",
    "claim",
    "status",
    "evaluation_rule",
    "evidence",
    "run_id",
)


def write_pending_claim_registry(path: Path) -> None:
    rows = [
        {
            "claim_id": claim_id,
            "claim": claim,
            "status": "PENDING",
            "evaluation_rule": "preregistered; mechanically evaluated after all 24 cases",
            "evidence": "not_yet_measured",
            "run_id": "preregistered_before_run",
        }
        for claim_id, claim in CLAIM_DEFINITIONS
    ]
    _write_csv(path, rows, CLAIM_FIELDS)


def write_claim_registry(path: Path, rows: list[dict[str, Any]]) -> None:
    _write_csv(path, rows, CLAIM_FIELDS)


def write_evaluation_artifacts(
    run_dir: Path,
    *,
    results: list[dict[str, Any]],
    payloads: dict[str, Any],
    provenance: dict[str, Any],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(run_dir / "per_case_results.jsonl", results)
    _write_csv(
        run_dir / "metrics.csv",
        payloads["metric_rows"],
        ("method", "metric", "k", "value", "n_cases", "run_id"),
    )
    (run_dir / "metrics.json").write_text(
        json.dumps(payloads["metrics_json"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(
        run_dir / "paper_metrics.csv",
        payloads["paper_rows"],
        (
            "experiment",
            "method",
            "metric",
            "k",
            "value",
            "n",
            "provenance_level",
            "run_id",
        ),
    )
    _write_csv(
        run_dir / "retrieval_ablation_table.csv",
        payloads["table_rows"],
        (
            "method",
            "Recall@5",
            "Recall@10",
            "MRR@10",
            "nDCG@5",
            "nDCG@10",
            "DirectRecall@5",
        ),
    )
    _write_csv(
        run_dir / "paired_improvements.csv",
        payloads["paired_rows"],
        (
            "target_method",
            "baseline_method",
            "metric",
            "k",
            "target_value",
            "baseline_value",
            "absolute_difference",
            "relative_difference",
            "run_id",
        ),
    )
    (run_dir / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _hash_files(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unavailable:not-a-git-worktree"


def validate_index_corpus_snapshot(
    client,
    frozen_chunks: list[dict[str, Any]],
    *,
    knowledge_index: str = "health_knowledge_v1",
) -> dict[str, Any]:
    response = client.search(
        index=knowledge_index,
        size=100,
        query={"bool": {"filter": _knowledge_filters()}},
        source_includes=[
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
        ],
    )
    indexed = [hit["_source"] for hit in response["hits"]["hits"]]
    frozen_by_id = {chunk["chunk_id"]: chunk for chunk in frozen_chunks}
    indexed_by_id = {chunk["chunk_id"]: chunk for chunk in indexed}
    if len(indexed) != 27 or set(indexed_by_id) != set(frozen_by_id):
        raise RuntimeError("Filtered production index is not the frozen 27-chunk corpus")
    for chunk_id, frozen in frozen_by_id.items():
        actual = indexed_by_id[chunk_id]
        for field, expected in frozen.items():
            if actual.get(field) != expected:
                raise RuntimeError(f"Indexed corpus field mismatch: {chunk_id}.{field}")
        if (
            actual.get("embedding_model") != EMBEDDING_MODEL
            or actual.get("embedding_dim") != EMBEDDING_DIMENSION
            or len(actual.get("embedding", [])) != EMBEDDING_DIMENSION
        ):
            raise RuntimeError(f"Indexed embedding contract mismatch: {chunk_id}")
    return {
        "index": knowledge_index,
        "filtered_chunk_count": len(indexed),
        "id_set_matches_frozen_corpus": True,
        "content_and_metadata_match": True,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dim": EMBEDDING_DIMENSION,
    }


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()


def run_evaluation(
    *,
    client,
    api_key: str,
    gold_path: Path = DEFAULT_GOLD_PATH,
    corpus_path: Path = DEFAULT_CORPUS_PATH,
    corpus_manifest_path: Path = DEFAULT_CORPUS_MANIFEST_PATH,
    gold_manifest_path: Path = DEFAULT_GOLD_MANIFEST_PATH,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    claim_path: Path = DEFAULT_CLAIM_PATH,
    knowledge_index: str = "health_knowledge_v1",
    run_id: str | None = None,
) -> Path:
    created_at = datetime.now(UTC)
    run_id = run_id or created_at.strftime("%Y%m%dT%H%M%SZ_retrieval_ablation_v1")
    contract = validate_production_contract()
    frozen = load_frozen_inputs(
        gold_path=gold_path,
        corpus_path=corpus_path,
        corpus_manifest_path=corpus_manifest_path,
    )
    gold_manifest = json.loads(gold_manifest_path.read_text(encoding="utf-8"))
    if (
        gold_manifest.get("gold_sha256") != EXPECTED_GOLD_SHA256
        or gold_manifest.get("corpus_sha256") != EXPECTED_CORPUS_SHA256
        or gold_manifest.get("retrieval_results_seen_before_freeze") is not False
    ):
        raise RuntimeError("Frozen Gold manifest contract mismatch")
    index_snapshot = validate_index_corpus_snapshot(
        client, frozen["corpus_chunks"], knowledge_index=knowledge_index
    )

    source_tree_before = _hash_files(RELEVANT_PRODUCTION_SOURCES)
    runner_hash = file_sha256(Path(__file__))
    uv_lock_hash = file_sha256(Path("uv.lock"))
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    raw_path = run_dir / "per_case_results.jsonl"
    raw_path.write_text("", encoding="utf-8")

    write_pending_claim_registry(claim_path)
    results = []
    for case in frozen["cases"]:
        result = execute_case(
            case,
            client=client,
            api_key=api_key,
            knowledge_index=knowledge_index,
        )
        results.append(result)
        _append_jsonl(raw_path, result)

    model_call_counts = {
        key: sum(result["model_call_counts"][key] for result in results)
        for key in ("text_embedding_v4", "qwen3_rerank", "qwen_plus")
    }
    if model_call_counts != {
        "text_embedding_v4": 24,
        "qwen3_rerank": 24,
        "qwen_plus": 0,
    }:
        raise RuntimeError(f"Live model call budget mismatch: {model_call_counts}")

    frozen_after = load_frozen_inputs(
        gold_path=gold_path,
        corpus_path=corpus_path,
        corpus_manifest_path=corpus_manifest_path,
    )
    if _hash_files(RELEVANT_PRODUCTION_SOURCES) != source_tree_before:
        raise RuntimeError("Production source tree changed during retrieval evaluation")
    if (
        frozen_after["gold_sha256"] != frozen["gold_sha256"]
        or frozen_after["corpus_sha256"] != frozen["corpus_sha256"]
    ):
        raise RuntimeError("Gold or corpus changed after retrieval results were seen")

    payloads = build_artifact_payloads(results, run_id=run_id)
    provenance = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "gold_sha256": frozen["gold_sha256"],
        "corpus_sha256": frozen["corpus_sha256"],
        "source_tree_sha256": source_tree_before,
        "runner_sha256": runner_hash,
        "uv_lock_sha256": uv_lock_hash,
        "git_commit": _git_commit(),
        "python_version": platform.python_version(),
        **contract,
        "vector_similarity": contract["vector_similarity"],
        "RRF_evaluation_only": True,
        "RRF_production_ranking_semantics": False,
        "model_call_counts": model_call_counts,
        "cases_executed": len(results),
        "failed_cases": 0,
        "index_snapshot": index_snapshot,
        "latency_not_for_primary_claim": True,
        "warmup_performed": False,
        "gold_modified_after_results_seen": False,
        "corpus_modified": False,
        "production_semantics_modified": False,
        "rrf_added_to_production": False,
        "qwen_plus_executed": False,
    }
    write_evaluation_artifacts(
        run_dir,
        results=results,
        payloads=payloads,
        provenance=provenance,
    )
    write_claim_registry(claim_path, payloads["claim_rows"])
    return run_dir


def _ranking_ids(result: dict[str, Any], field: str) -> list[str]:
    return [row["chunk_id"] for row in result[field]]


def verify_run(
    run_dir: Path,
    *,
    gold_path: Path = DEFAULT_GOLD_PATH,
    corpus_path: Path = DEFAULT_CORPUS_PATH,
    corpus_manifest_path: Path = DEFAULT_CORPUS_MANIFEST_PATH,
    claim_path: Path = DEFAULT_CLAIM_PATH,
) -> dict[str, Any]:
    frozen = load_frozen_inputs(
        gold_path=gold_path,
        corpus_path=corpus_path,
        corpus_manifest_path=corpus_manifest_path,
    )
    results = _read_jsonl(run_dir / "per_case_results.jsonl")
    provenance = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    metrics_json = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    run_id = provenance["run_id"]
    case_by_id = {case["case_id"]: case for case in frozen["cases"]}
    if len(results) != 24 or [row["case_id"] for row in results] != list(case_by_id):
        raise RuntimeError("Raw results must contain all 24 Gold cases in frozen order")
    frozen_ids = {chunk["chunk_id"] for chunk in frozen["corpus_chunks"]}

    for result in results:
        case = case_by_id[result["case_id"]]
        if len(result["bm25_ranking"]) > 10 or len(result["vector_ranking"]) > 10:
            raise RuntimeError(f"Single-route Top K exceeded for {result['case_id']}")
        candidates = result["hybrid_candidate_ids"]
        if (
            len(candidates) != len(set(candidates))
            or len(candidates) != result["hybrid_candidate_count"]
        ):
            raise RuntimeError(f"Candidate pool is not deduplicated for {result['case_id']}")
        all_ranked = set(candidates)
        for field in ("bm25_ranking", "vector_ranking", "rrf_ranking", "rerank_ranking"):
            all_ranked.update(_ranking_ids(result, field))
        if all_ranked - frozen_ids:
            raise RuntimeError(f"Ranking references outside frozen corpus: {result['case_id']}")
        if set(_ranking_ids(result, "rerank_ranking")) != set(candidates):
            raise RuntimeError(f"Rerank does not cover full candidate pool: {result['case_id']}")

        recomputed_rrf = reciprocal_rank_fusion(
            [
                {"chunk_id": row["chunk_id"], "bm25_rank": row["rank"]}
                for row in result["bm25_ranking"]
            ],
            [
                {"chunk_id": row["chunk_id"], "vector_rank": row["rank"]}
                for row in result["vector_ranking"]
            ],
        )[:10]
        if [row["chunk_id"] for row in recomputed_rrf] != _ranking_ids(result, "rrf_ranking"):
            raise RuntimeError(f"RRF order is not deterministic for {result['case_id']}")

        method_fields = {
            "BM25": "bm25_ranking",
            "Vector": "vector_ranking",
            "Hybrid-RRF": "rrf_ranking",
            "Hybrid+Reranker": "rerank_ranking",
        }
        for method, field in method_fields.items():
            expected = calculate_ranking_metrics(
                _ranking_ids(result, field),
                relevance_2_ids=case["relevance_2_chunk_ids"],
                relevance_1_ids=case["relevance_1_chunk_ids"],
            )
            actual = result["per_method_metrics"][method]
            for metric, ks in expected.items():
                for k, value in ks.items():
                    if not math.isclose(_metric_at(actual, metric, k), value, abs_tol=1e-12):
                        raise RuntimeError(
                            f"Per-case metric mismatch: {result['case_id']} {method} {metric}@{k}"
                        )
        expected_pool_recall = hybrid_candidate_pool_recall(
            candidates,
            relevance_2_ids=case["relevance_2_chunk_ids"],
            relevance_1_ids=case["relevance_1_chunk_ids"],
        )
        if not math.isclose(
            result["hybrid_candidate_pool_recall"], expected_pool_recall, abs_tol=1e-12
        ):
            raise RuntimeError(f"Candidate pool recall mismatch: {result['case_id']}")

    call_counts = {
        key: sum(result["model_call_counts"][key] for result in results)
        for key in ("text_embedding_v4", "qwen3_rerank", "qwen_plus")
    }
    if call_counts != {"text_embedding_v4": 24, "qwen3_rerank": 24, "qwen_plus": 0}:
        raise RuntimeError(f"Raw model call counts invalid: {call_counts}")

    recomputed_payloads = build_artifact_payloads(results, run_id=run_id)
    stored_lookup = _metric_row_lookup(metrics_json["metrics"])
    recomputed_lookup = _metric_row_lookup(recomputed_payloads["metric_rows"])
    if set(stored_lookup) != set(recomputed_lookup) or any(
        not math.isclose(stored_lookup[key], recomputed_lookup[key], abs_tol=1e-12)
        for key in stored_lookup
    ):
        raise RuntimeError("Stored macro metrics do not match raw per-case results")

    if (
        provenance.get("gold_sha256") != EXPECTED_GOLD_SHA256
        or provenance.get("corpus_sha256") != EXPECTED_CORPUS_SHA256
        or provenance.get("source_tree_sha256") != _hash_files(RELEVANT_PRODUCTION_SOURCES)
        or provenance.get("runner_sha256") != file_sha256(Path(__file__))
        or provenance.get("uv_lock_sha256") != file_sha256(Path("uv.lock"))
        or provenance.get("model_call_counts") != call_counts
        or provenance.get("gold_modified_after_results_seen") is not False
        or provenance.get("corpus_modified") is not False
        or provenance.get("production_semantics_modified") is not False
        or provenance.get("rrf_added_to_production") is not False
        or provenance.get("qwen_plus_executed") is not False
    ):
        raise RuntimeError("Provenance verification failed")

    with claim_path.open("r", encoding="utf-8-sig", newline="") as handle:
        stored_claims = list(csv.DictReader(handle))
    expected_claims = recomputed_payloads["claim_rows"]
    if [row["claim_id"] for row in stored_claims] != [
        row["claim_id"] for row in expected_claims
    ] or any(
        stored["status"] != expected["status"] or stored["run_id"] != expected["run_id"]
        for stored, expected in zip(stored_claims, expected_claims, strict=True)
    ):
        raise RuntimeError("Claim registry does not match mechanical result rules")

    return {
        "validation_status": "PASS",
        "run_id": run_id,
        "cases_executed": len(results),
        "failed_cases": 0,
        "gold_sha256": frozen["gold_sha256"],
        "corpus_sha256": frozen["corpus_sha256"],
        "model_call_counts": call_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--verify-run", type=Path)
    args = parser.parse_args()
    if args.verify_run:
        print(json.dumps(verify_run(args.verify_run), ensure_ascii=False, indent=2))
        return

    env_file = Path(".env")
    api_key = load_api_key(env_file)
    es_url = _env_value("ELASTICSEARCH_URL", env_file) or "http://127.0.0.1:9200"
    client = Elasticsearch(es_url, request_timeout=60)
    try:
        if not client.ping():
            raise RuntimeError(f"Elasticsearch is not reachable: {es_url}")
        run_dir = run_evaluation(
            client=client,
            api_key=api_key,
            output_root=args.output_root,
        )
    finally:
        client.close()
    print(run_dir)


if __name__ == "__main__":
    main()
