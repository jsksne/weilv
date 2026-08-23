import csv
import json
import math
from pathlib import Path

import pytest

from evaluation.runners.run_retrieval_ablation_evaluation import (
    BM25_RECALL_K,
    EXPECTED_CORPUS_SHA256,
    EXPECTED_GOLD_SHA256,
    RRF_K,
    VECTOR_RECALL_K,
    aggregate_metrics,
    bootstrap_paired_ci,
    build_artifact_payloads,
    build_hybrid_candidate_pool,
    calculate_paired_improvements,
    calculate_ranking_metrics,
    evaluate_claims,
    execute_case,
    hybrid_candidate_pool_recall,
    load_frozen_inputs,
    reciprocal_rank_fusion,
    validate_production_contract,
    write_evaluation_artifacts,
    write_pending_claim_registry,
)


def test_frozen_inputs_load_all_24_cases_and_27_corpus_chunks():
    frozen = load_frozen_inputs(
        gold_path=Path("evaluation/datasets/retrieval_gold_v1.jsonl"),
        corpus_path=Path("data/metadata/health_knowledge_v1.jsonl"),
        corpus_manifest_path=Path("evaluation/manifests/retrieval_knowledge_corpus_v1.json"),
    )

    assert EXPECTED_GOLD_SHA256 == (
        "2fb07424641826c98f2c722e3e13dedf5a95c12fccad726fa32ddb9f3f9599b0"
    )
    assert EXPECTED_CORPUS_SHA256 == (
        "e04e27a27175211d32c57f36b715bc19faf45ca6be7ccd8e993a86a668392938"
    )
    assert len(frozen["cases"]) == 24
    assert len(frozen["corpus_chunks"]) == 27
    assert len({case["case_id"] for case in frozen["cases"]}) == 24


def test_frozen_input_loader_stops_on_gold_hash_drift(tmp_path):
    changed_gold = tmp_path / "retrieval_gold_v1.jsonl"
    changed_gold.write_bytes(
        Path("evaluation/datasets/retrieval_gold_v1.jsonl").read_bytes() + b"\n"
    )

    with pytest.raises(RuntimeError, match="Gold SHA-256 mismatch"):
        load_frozen_inputs(
            gold_path=changed_gold,
            corpus_path=Path("data/metadata/health_knowledge_v1.jsonl"),
            corpus_manifest_path=Path("evaluation/manifests/retrieval_knowledge_corpus_v1.json"),
        )


def test_rrf_uses_fixed_60_and_deterministic_tie_breaking():
    bm25 = [
        {"chunk_id": "A", "bm25_rank": 1},
        {"chunk_id": "B", "bm25_rank": 2},
    ]
    vector = [
        {"chunk_id": "B", "vector_rank": 1},
        {"chunk_id": "C", "vector_rank": 2},
    ]

    ranking = reciprocal_rank_fusion(bm25, vector)
    tied = reciprocal_rank_fusion(
        [{"chunk_id": "A", "bm25_rank": 1}],
        [{"chunk_id": "B", "vector_rank": 1}],
    )

    assert RRF_K == 60
    assert [row["chunk_id"] for row in ranking] == ["B", "A", "C"]
    assert ranking[0]["rrf_score"] == pytest.approx(1 / 62 + 1 / 61)
    assert [row["chunk_id"] for row in tied] == ["A", "B"]
    assert [row["rrf_rank"] for row in tied] == [1, 2]


def test_metrics_use_binary_recall_direct_recall_and_graded_ndcg():
    metrics = calculate_ranking_metrics(
        ["support", "direct", "irrelevant"],
        relevance_2_ids=["direct"],
        relevance_1_ids=["support"],
    )
    expected_dcg_at_3 = 1 + 3 / math.log2(3)
    expected_idcg_at_3 = 3 + 1 / math.log2(3)

    assert metrics["Recall"][1] == pytest.approx(0.5)
    assert metrics["Recall"][3] == pytest.approx(1.0)
    assert metrics["DirectRecall"][1] == pytest.approx(0.0)
    assert metrics["DirectRecall"][3] == pytest.approx(1.0)
    assert metrics["MRR"][10] == pytest.approx(1.0)
    assert metrics["nDCG"][3] == pytest.approx(expected_dcg_at_3 / expected_idcg_at_3)
    assert metrics["nDCG"][5] == pytest.approx(expected_dcg_at_3 / expected_idcg_at_3)


def test_hybrid_candidate_pool_recall_is_set_based_not_recall_at_10():
    value = hybrid_candidate_pool_recall(
        ["direct", "direct", "other", "support"],
        relevance_2_ids=["direct"],
        relevance_1_ids=["support", "missing"],
    )

    assert value == pytest.approx(2 / 3)


def test_production_contract_fixes_recall_models_dimension_and_similarity():
    contract = validate_production_contract()

    assert BM25_RECALL_K == VECTOR_RECALL_K == 10
    assert contract == {
        "BM25_RECALL_K": 10,
        "VECTOR_RECALL_K": 10,
        "embedding_model": "text-embedding-v4",
        "embedding_dim": 1024,
        "vector_similarity": "cosine",
        "reranker_model": "qwen3-rerank",
        "RRF_K": 60,
        "RRF_semantics": "evaluation_only_not_production_ranking",
    }


def test_hybrid_candidate_pool_reuses_production_merge_and_deduplicates():
    bm25 = [
        {"chunk_id": "A", "content": "a", "bm25_rank": 1, "bm25_score": 2.0},
        {"chunk_id": "B", "content": "b", "bm25_rank": 2, "bm25_score": 1.0},
    ]
    vector = [
        {"chunk_id": "B", "content": "b", "vector_rank": 1, "vector_score": 0.9},
        {"chunk_id": "C", "content": "c", "vector_rank": 2, "vector_score": 0.8},
    ]

    merged = build_hybrid_candidate_pool(bm25, vector)

    assert [row["chunk_id"] for row in merged] == ["A", "B", "C"]
    assert len({row["chunk_id"] for row in merged}) == 3
    assert merged[1]["bm25_score"] == 1.0
    assert merged[1]["vector_score"] == 0.9


def test_execute_case_reuses_routes_once_and_records_complete_raw_results():
    calls = {"embed": [], "bm25": [], "vector": [], "rerank": []}
    bm25_hits = [
        {
            "chunk_id": "A",
            "document_id": "SRC-A",
            "content": "direct",
            "bm25_rank": 1,
            "bm25_score": 3.0,
        },
        {
            "chunk_id": "B",
            "document_id": "SRC-B",
            "content": "support",
            "bm25_rank": 2,
            "bm25_score": 2.0,
        },
    ]
    vector_hits = [
        {
            "chunk_id": "B",
            "document_id": "SRC-B",
            "content": "support",
            "vector_rank": 1,
            "vector_score": 0.9,
        },
        {
            "chunk_id": "C",
            "document_id": "SRC-C",
            "content": "other",
            "vector_rank": 2,
            "vector_score": 0.8,
        },
    ]

    def embed(texts, api_key, text_type):
        calls["embed"].append((texts, api_key, text_type))
        return [[0.1] * 1024]

    def bm25(client, query, index_name, **kwargs):
        calls["bm25"].append((client, query, index_name, kwargs))
        return bm25_hits

    def vector(client, query_vector, index_name, **kwargs):
        calls["vector"].append((client, query_vector, index_name, kwargs))
        return vector_hits

    def rerank(query, documents, api_key):
        calls["rerank"].append((query, documents, api_key))
        return [
            {"index": 2, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.8},
            {"index": 1, "relevance_score": 0.7},
        ]

    case = {
        "case_id": "KRG-T01",
        "case_family_id": "test-family",
        "domain": "sleep",
        "query": "测试查询",
        "relevance_2_chunk_ids": ["A"],
        "relevance_1_chunk_ids": ["B"],
    }
    result = execute_case(
        case,
        client=object(),
        api_key="key",
        embed_fn=embed,
        bm25_fn=bm25,
        vector_fn=vector,
        rerank_fn=rerank,
    )

    assert len(calls["embed"]) == len(calls["bm25"]) == len(calls["vector"]) == 1
    assert len(calls["rerank"]) == 1
    assert calls["embed"][0] == (["测试查询"], "key", "query")
    assert calls["bm25"][0][3]["size"] == 10
    assert calls["vector"][0][3]["size"] == 10
    assert calls["bm25"][0][3]["raw_filters"] == calls["vector"][0][3]["raw_filters"]
    assert len(result["bm25_ranking"]) <= 10
    assert len(result["vector_ranking"]) <= 10
    assert result["hybrid_candidate_ids"] == ["A", "B", "C"]
    assert result["hybrid_candidate_count"] == 3
    assert [row["chunk_id"] for row in result["rerank_ranking"]] == ["C", "A", "B"]
    assert set(result["per_method_metrics"]) == {
        "BM25",
        "Vector",
        "Hybrid-RRF",
        "Hybrid+Reranker",
    }
    assert result["hybrid_candidate_pool_recall"] == pytest.approx(1.0)
    assert set(result["latency_ms_by_method"]) == {
        "BM25",
        "Vector",
        "Hybrid-RRF",
        "Hybrid+Reranker",
    }
    assert result["model_call_counts"] == {
        "text_embedding_v4": 1,
        "qwen3_rerank": 1,
        "qwen_plus": 0,
    }


def _method_metrics(value):
    return {
        "Recall": {1: value, 3: value, 5: value, 10: value},
        "DirectRecall": {1: value, 3: value, 5: value, 10: value},
        "MRR": {10: value},
        "nDCG": {3: value, 5: value, 10: value},
    }


def _aggregate_case(case_id, bm25, vector, rrf, reranker, pool=1.0):
    return {
        "case_id": case_id,
        "per_method_metrics": {
            "BM25": _method_metrics(bm25),
            "Vector": _method_metrics(vector),
            "Hybrid-RRF": _method_metrics(rrf),
            "Hybrid+Reranker": _method_metrics(reranker),
        },
        "hybrid_candidate_pool_recall": pool,
        "latency_ms_by_method": {
            "BM25": 1.0,
            "Vector": 2.0,
            "Hybrid-RRF": 0.1,
            "Hybrid+Reranker": 3.0,
        },
    }


def test_aggregation_is_macro_over_cases_and_paired_deltas_keep_raw_values():
    results = [
        _aggregate_case("C1", 0.2, 0.4, 0.5, 0.8),
        _aggregate_case("C2", 0.4, 0.6, 0.7, 1.0),
    ]
    rows = aggregate_metrics(results, run_id="run")
    lookup = {(row["method"], row["metric"], row["k"]): row for row in rows}
    paired = calculate_paired_improvements(rows, run_id="run")
    bm25_ndcg = next(
        row
        for row in paired
        if row["baseline_method"] == "BM25" and row["metric"] == "nDCG" and row["k"] == 5
    )

    assert lookup[("BM25", "Recall", 5)]["value"] == pytest.approx(0.3)
    assert lookup[("Hybrid+Reranker", "nDCG", 5)]["value"] == pytest.approx(0.9)
    assert lookup[("Hybrid Candidate Pool", "Hybrid Candidate Pool Recall", None)][
        "value"
    ] == pytest.approx(1.0)
    assert bm25_ndcg["baseline_value"] == pytest.approx(0.3)
    assert bm25_ndcg["target_value"] == pytest.approx(0.9)
    assert bm25_ndcg["absolute_difference"] == pytest.approx(0.6)
    assert bm25_ndcg["relative_difference"] == pytest.approx(2.0)


def test_bootstrap_ci_resamples_cases_with_fixed_seed():
    results = [
        _aggregate_case("C1", 0.1, 0.2, 0.3, 0.5),
        _aggregate_case("C2", 0.2, 0.3, 0.4, 0.6),
        _aggregate_case("C3", 0.3, 0.4, 0.5, 0.7),
    ]

    ci = bootstrap_paired_ci(
        results,
        baseline_method="Hybrid-RRF",
        seed=20260816,
        resamples=100,
    )

    assert ci["observed_absolute_difference"] == pytest.approx(0.2)
    assert ci["ci_lower"] == pytest.approx(0.2)
    assert ci["ci_upper"] == pytest.approx(0.2)
    assert ci["seed"] == 20260816
    assert ci["resamples"] == 100
    assert ci["n_cases"] == 3


def test_claim_statuses_are_mechanical_and_real_outcome_claim_is_unsupported():
    results = [
        _aggregate_case("C1", 0.2, 0.4, 0.5, 0.8, pool=1.0),
        _aggregate_case("C2", 0.4, 0.6, 0.7, 1.0, pool=1.0),
    ]
    rows = aggregate_metrics(results, run_id="run")

    claims = {row["claim_id"]: row for row in evaluate_claims(rows, run_id="run")}

    assert claims["CR-RET-001"]["status"] == "SUPPORTED"
    assert claims["CR-RET-002"]["status"] == "SUPPORTED"
    assert claims["CR-RET-003"]["status"] == "SUPPORTED"
    assert claims["CR-RET-REAL-001"]["status"] == "UNSUPPORTED"


def test_claims_are_preregistered_pending_before_results(tmp_path):
    path = tmp_path / "claim_registry_retrieval_v1.csv"

    write_pending_claim_registry(path)

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["claim_id"] for row in rows] == [
        "CR-RET-001",
        "CR-RET-002",
        "CR-RET-003",
        "CR-RET-REAL-001",
    ]
    assert {row["status"] for row in rows} == {"PENDING"}
    assert {row["run_id"] for row in rows} == {"preregistered_before_run"}


def test_artifact_payload_and_writer_emit_all_required_outputs(tmp_path):
    results = [
        _aggregate_case("C1", 0.2, 0.4, 0.5, 0.8),
        _aggregate_case("C2", 0.4, 0.6, 0.7, 1.0),
    ]
    payloads = build_artifact_payloads(
        results,
        run_id="run",
        bootstrap_resamples=100,
    )
    provenance = {
        "run_id": "run",
        "gold_sha256": EXPECTED_GOLD_SHA256,
        "corpus_sha256": EXPECTED_CORPUS_SHA256,
    }

    write_evaluation_artifacts(
        tmp_path,
        results=results,
        payloads=payloads,
        provenance=provenance,
    )

    assert {path.name for path in tmp_path.iterdir()} == {
        "per_case_results.jsonl",
        "metrics.csv",
        "metrics.json",
        "paper_metrics.csv",
        "retrieval_ablation_table.csv",
        "paired_improvements.csv",
        "provenance.json",
    }
    metrics_json = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics_json["run_id"] == "run"
    assert len(metrics_json["bootstrap_ci"]) == 3
    with (tmp_path / "paper_metrics.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        paper_rows = list(csv.DictReader(handle))
    assert paper_rows
    assert {row["provenance_level"] for row in paper_rows} == {"A+B+C"}
