"""Phase B: Stage 6E-1 Frozen Task Recommendation Evaluation.

Evaluates only the Task recommendation selection (no qwen-plus explanation).
Uses the actual frozen production task retrieval/ranking semantics.
"""

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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch

from weilv.basic_rag import (
    BasicRagRequest,
    _matches_task_metadata,
    _task_document,
)
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
from weilv.safety_rules import (
    evaluate_input_risk,
    load_safety_rules,
    select_safe_tasks,
)

EXPECTED_CORPUS_SHA = "40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48"
EXPECTED_GOLD_PATH = Path("evaluation/datasets/task_recommendation_gold_v1.jsonl")
EXPECTED_MANIFEST_PATH = Path(
    "evaluation/manifests/task_recommendation_gold_v1_manifest.json"
)
TASK_CORPUS_PATH = Path("data/metadata/micro_tasks_v1.jsonl")
TASK_INDEX = "micro_tasks_v1"
BM25_RECALL_K = 10
VECTOR_RECALL_K = 10
TASK_RERANK_TOPN = 5

CLAIM_DEFINITIONS = (
    (
        "CR-TASK-001",
        "Valid@1",
        "On the frozen consensus-reviewed synthetic benchmark, Valid@1 >= 0.90.",
        "SUPPORTED iff Valid@1 >= 0.90; else NOT_SUPPORTED.",
        "support_threshold",
    ),
    (
        "CR-TASK-002",
        "Invalid Recommendation Rate",
        "Invalid Recommendation Rate <= 0.10.",
        "SUPPORTED iff Invalid Recommendation Rate <= 0.10; else NOT_SUPPORTED.",
        "support_threshold_reverse",
    ),
    (
        "CR-TASK-003",
        "Preferred@1",
        "Preferred@1 >= 0.70.",
        "SUPPORTED iff Preferred@1 >= 0.70; else NOT_SUPPORTED.",
        "support_threshold",
    ),
    (
        "CR-TASK-004",
        "All-Valid@3",
        "All-Valid@3 >= 0.80.",
        "SUPPORTED iff All-Valid@3 >= 0.80; else NOT_SUPPORTED.",
        "support_threshold",
    ),
    (
        "CR-TASK-REAL-001",
        "Real-Outcome Inference",
        "High offline task-recommendation metrics prove real adolescents will follow the recommendations or achieve better health outcomes.",
        "Always UNSUPPORTED because offline task-recommendation metrics do not measure real adolescent behavior or health outcomes.",
        "always_unsupported",
    ),
)

RELEVANT_PRODUCTION_SOURCES = (
    Path("src/weilv/basic_rag.py"),
    Path("src/weilv/dashscope_models.py"),
    Path("src/weilv/elasticsearch_indices.py"),
    Path("src/weilv/retrieval.py"),
    Path("src/weilv/safety_rules.py"),
    Path("src/weilv/output_guard.py"),
    Path("src/weilv/micro_tasks.py"),
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _load_task_corpus() -> tuple[list[dict[str, Any]], str]:
    tasks = _read_jsonl(TASK_CORPUS_PATH)
    if len(tasks) != 23:
        raise RuntimeError(f"task corpus must have 23 tasks, got {len(tasks)}")
    sorted_tasks = sorted(tasks, key=lambda task: task["task_id"])
    canonical = (
        "\n".join(
            json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for task in sorted_tasks
        )
        + "\n"
    )
    sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return tasks, sha


def _load_frozen_inputs() -> dict[str, Any]:
    tasks, corpus_sha = _load_task_corpus()
    if corpus_sha != EXPECTED_CORPUS_SHA:
        raise RuntimeError(
            f"task corpus SHA mismatch: expected {EXPECTED_CORPUS_SHA}, got {corpus_sha}"
        )

    manifest = json.loads(EXPECTED_MANIFEST_PATH.read_text(encoding="utf-8"))
    expected_gold_sha = manifest["gold_sha256"]
    actual_gold_sha = file_sha256(EXPECTED_GOLD_PATH)
    if actual_gold_sha != expected_gold_sha:
        raise RuntimeError(
            f"gold SHA mismatch: expected {expected_gold_sha}, got {actual_gold_sha}"
        )
    if (
        manifest.get("task_corpus_sha256") != EXPECTED_CORPUS_SHA
        or manifest.get("case_count") != 24
        or manifest.get("task_count") != 23
        or manifest.get("recommendation_results_seen_before_freeze") is not False
    ):
        raise RuntimeError("Frozen gold manifest contract mismatch")

    cases = _read_jsonl(EXPECTED_GOLD_PATH)
    if len(cases) != 24:
        raise RuntimeError(f"expected 24 cases, got {len(cases)}")

    return {
        "cases": cases,
        "tasks": tasks,
        "corpus_sha256": corpus_sha,
        "gold_sha256": actual_gold_sha,
        "manifest": manifest,
    }


def validate_production_contract() -> dict[str, Any]:
    bm25_default = inspect.signature(bm25_search).parameters["size"].default
    vector_default = inspect.signature(vector_search).parameters["size"].default
    vector_mapping = get_index_definitions()["micro_tasks_v1"]["mappings"]["properties"][
        "embedding"
    ]
    if bm25_default != BM25_RECALL_K or vector_default != VECTOR_RECALL_K:
        raise RuntimeError("Production task retrieval recall K no longer matches frozen constants")
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
    }


def _build_request(case: dict[str, Any]) -> BasicRagRequest:
    safety_flags = case.get("safety_flags", {})
    return BasicRagRequest(
        query=case["query"],
        target_stage=case["target_stage"],
        current_context=case["current_context"],
        available_minutes=case.get("available_minutes"),
        activity_context=case.get("activity_context", "other"),
        vision_abnormal=bool(safety_flags.get("vision_abnormal", False)),
        physical_discomfort=bool(safety_flags.get("physical_discomfort", False)),
        medical_request=bool(safety_flags.get("medical_request", False)),
        cannot_move=bool(safety_flags.get("cannot_move", False)),
        unstable_environment=bool(safety_flags.get("unstable_environment", False)),
        sleep_being_crowded=bool(safety_flags.get("sleep_being_crowded", False)),
    )


def _safety_context(request: BasicRagRequest) -> dict[str, Any]:
    payload = {
        "vision_abnormal": request.vision_abnormal,
        "physical_discomfort": request.physical_discomfort,
        "medical_request": request.medical_request,
        "cannot_move": request.cannot_move,
        "unstable_environment": request.unstable_environment,
        "sleep_being_crowded": request.sleep_being_crowded,
        "target_stage": request.target_stage,
        "current_context": None if request.current_context == "unknown" else request.current_context,
        "activity_context": request.activity_context,
        "available_minutes": request.available_minutes,
    }
    payload["unstable_reading_or_screen"] = (
        request.unstable_environment and request.activity_context in {"reading", "writing", "screen"}
    )
    payload["sleep_displaced_by_study"] = request.sleep_being_crowded
    return payload


def _task_filters(request: BasicRagRequest) -> list[dict[str, Any]]:
    filters = [
        {"term": {"review_status": "content_reviewed"}},
        {"term": {"target_stage": request.target_stage}},
    ]
    if request.current_context != "unknown":
        filters.append({"term": {"execution_contexts": request.current_context}})
    if request.available_minutes is not None:
        filters.append({"range": {"estimated_minutes": {"lte": request.available_minutes}}})
    return filters


def _label_top1(top1_id: str | None, case: dict[str, Any]) -> str:
    if top1_id is None:
        return "no_task"
    if top1_id in case["preferred_task_ids"]:
        return "preferred"
    if top1_id in case["acceptable_task_ids"]:
        return "acceptable"
    return "invalid"


def execute_case(
    case: dict[str, Any],
    *,
    client,
    api_key: str,
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

    request = _build_request(case)
    rules = load_safety_rules()
    safety_ctx = _safety_context(request)

    candidate_pool_before_filter: list[dict[str, Any]] = []
    candidate_pool_after_filter: list[dict[str, Any]] = []
    ranked_task_ids: list[str] = []
    top1_task_id: str | None = None
    safety_status = "allowed"
    matched_rule_ids: list[str] = []
    reason_codes: list[str] = []
    embed_calls = 0
    rerank_calls = 0
    qwen_plus_calls = 0

    input_result = evaluate_input_risk(safety_ctx, rules)
    if input_result["status"] in {"blocked", "help_seeking"}:
        safety_status = input_result["status"]
        matched_rule_ids = input_result["matched_rule_ids"]
        reason_codes = input_result["reason_codes"]
    else:
        embed_started = clock_fn()
        query_vector = embed_fn([request.query], api_key=api_key, text_type="query")[0]
        embed_calls = 1
        embed_ms = (clock_fn() - embed_started) * 1000

        task_bm25 = bm25_fn(
            client,
            request.query,
            TASK_INDEX,
            size=BM25_RECALL_K,
            raw_filters=_task_filters(request),
            search_fields=["title^2", "instruction", "trigger", "domain", "context_tags"],
        )
        if len(task_bm25) > BM25_RECALL_K:
            raise RuntimeError("BM25 returned more than frozen Top 10")
        task_vector = vector_fn(
            client,
            query_vector,
            TASK_INDEX,
            size=VECTOR_RECALL_K,
            raw_filters=_task_filters(request),
        )
        if len(task_vector) > VECTOR_RECALL_K:
            raise RuntimeError("Vector retrieval returned more than frozen Top 10")

        candidate_pool_before_filter = merge_candidates(task_bm25, task_vector, identity_field="task_id")
        metadata_tasks = [
            task for task in candidate_pool_before_filter if _matches_task_metadata(task, request)
        ]
        safe_result = select_safe_tasks(metadata_tasks, safety_ctx, rules)
        matched_rule_ids = safe_result["matched_rule_ids"]
        reason_codes = safe_result["reason_codes"]
        if safe_result["status"] != "allowed":
            safety_status = safe_result["status"]
        else:
            safe_tasks = safe_result["tasks"]
            candidate_pool_after_filter = list(safe_tasks)
            if safe_tasks:
                rerank_started = clock_fn()
                rerank_results = rerank_fn(
                    request.query,
                    [_task_document(task) for task in safe_tasks],
                    api_key,
                )
                indices = [row["index"] for row in rerank_results]
                if len(indices) != len(safe_tasks) or set(indices) != set(range(len(safe_tasks))):
                    raise RuntimeError("Reranker did not return complete unique ordering")
                reranked = apply_rerank(safe_tasks, rerank_results)
                rerank_calls = 1
                ranked = reranked[:TASK_RERANK_TOPN]
                ranked_task_ids = [task["task_id"] for task in ranked]
                top1_task_id = ranked_task_ids[0] if ranked_task_ids else None

    top1_label = _label_top1(top1_task_id, case)
    top3_task_ids = ranked_task_ids[:3]

    preferred = set(case["preferred_task_ids"])
    acceptable = set(case["acceptable_task_ids"])

    if top1_task_id is None:
        valid_at_1 = False
        preferred_at_1 = False
    else:
        valid_at_1 = (top1_task_id in preferred) or (top1_task_id in acceptable)
        preferred_at_1 = top1_task_id in preferred

    if top3_task_ids:
        valid_in_top3 = sum(1 for tid in top3_task_ids if tid in preferred or tid in acceptable)
        valid_at_3 = valid_in_top3 / min(3, len(top3_task_ids))
        all_valid_at_3 = valid_in_top3 == len(top3_task_ids)
        preferred_in_top3 = sum(1 for tid in top3_task_ids if tid in preferred) / len(top3_task_ids)
    else:
        valid_at_3 = 0.0
        all_valid_at_3 = False
        preferred_in_top3 = 0.0

    return {
        "case_id": case["case_id"],
        "case_family_id": case["case_family_id"],
        "query_style": case["query_style"],
        "preferred_task_ids": case["preferred_task_ids"],
        "acceptable_task_ids": case["acceptable_task_ids"],
        "invalid_task_ids": case["invalid_task_ids"],
        "candidate_pool_before_filter_size": len(candidate_pool_before_filter),
        "candidate_pool_after_filter_size": len(candidate_pool_after_filter),
        "ranked_task_ids": ranked_task_ids,
        "top1_task_id": top1_task_id,
        "top3_task_ids": top3_task_ids,
        "top1_label": top1_label,
        "safety_status": safety_status,
        "matched_rule_ids": matched_rule_ids,
        "reason_codes": reason_codes,
        "valid_at_1": valid_at_1,
        "preferred_at_1": preferred_at_1,
        "valid_at_3": valid_at_3,
        "all_valid_at_3": all_valid_at_3,
        "preferred_in_top3": preferred_in_top3,
        "model_call_counts": {
            "text_embedding_v4": embed_calls,
            "qwen3_rerank": rerank_calls,
            "qwen_plus": qwen_plus_calls,
        },
    }


def _wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    phat = successes / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


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


def aggregate_metrics(
    results: list[dict[str, Any]],
    *,
    run_id: str,
    seed: int = 20260816,
    bootstrap_iterations: int = 10000,
) -> dict[str, Any]:
    n = len(results)
    valid_at_1_values = [1.0 if r["valid_at_1"] else 0.0 for r in results]
    invalid_top1_values = [1.0 if r["top1_label"] == "invalid" else 0.0 for r in results]
    preferred_at_1_values = [1.0 if r["preferred_at_1"] else 0.0 for r in results]
    all_valid_at_3_values = [1.0 if r["all_valid_at_3"] else 0.0 for r in results]
    preferred_in_top3_values = [r["preferred_in_top3"] for r in results]
    valid_at_3_values = [r["valid_at_3"] for r in results]
    no_task_values = [1.0 if r["top1_label"] == "no_task" else 0.0 for r in results]

    valid_at_1_rate = statistics.mean(valid_at_1_values)
    invalid_rate = statistics.mean(invalid_top1_values)
    preferred_at_1_rate = statistics.mean(preferred_at_1_values)
    all_valid_at_3_rate = statistics.mean(all_valid_at_3_values)
    mean_preferred_in_top3 = statistics.mean(preferred_in_top3_values)
    mean_valid_at_3 = statistics.mean(valid_at_3_values)
    no_task_rate = statistics.mean(no_task_values)

    eligible_counts_before = [r["candidate_pool_before_filter_size"] for r in results]
    eligible_counts_after = [r["candidate_pool_after_filter_size"] for r in results]
    mean_eligible_before = statistics.mean(eligible_counts_before)
    mean_eligible_after = statistics.mean(eligible_counts_after)
    median_eligible_before = statistics.median(eligible_counts_before)
    median_eligible_after = statistics.median(eligible_counts_after)

    def _ci(values: list[float]) -> tuple[float, float]:
        return _wilson_ci(int(round(sum(values))), n)

    valid_at_1_ci = _ci(valid_at_1_values)
    invalid_ci = _ci(invalid_top1_values)
    preferred_at_1_ci = _ci(preferred_at_1_values)

    rng = random.Random(seed)
    valid_at_3_bootstrap = []
    preferred_in_top3_bootstrap = []
    for _ in range(bootstrap_iterations):
        valid_sample = [rng.choice(valid_at_3_values) for _ in range(n)]
        valid_at_3_bootstrap.append(statistics.mean(valid_sample))
        preferred_sample = [rng.choice(preferred_in_top3_values) for _ in range(n)]
        preferred_in_top3_bootstrap.append(statistics.mean(preferred_sample))
    valid_at_3_ci = (
        _percentile(valid_at_3_bootstrap, 0.025),
        _percentile(valid_at_3_bootstrap, 0.975),
    )
    preferred_in_top3_ci = (
        _percentile(preferred_in_top3_bootstrap, 0.025),
        _percentile(preferred_in_top3_bootstrap, 0.975),
    )

    rows: list[dict[str, Any]] = [
        {
            "metric": "Valid@1",
            "value": valid_at_1_rate,
            "ci_lower": valid_at_1_ci[0],
            "ci_upper": valid_at_1_ci[1],
            "n": n,
            "ci_method": "wilson_95",
        },
        {
            "metric": "Invalid Recommendation Rate",
            "value": invalid_rate,
            "ci_lower": invalid_ci[0],
            "ci_upper": invalid_ci[1],
            "n": n,
            "ci_method": "wilson_95",
        },
        {
            "metric": "Preferred@1",
            "value": preferred_at_1_rate,
            "ci_lower": preferred_at_1_ci[0],
            "ci_upper": preferred_at_1_ci[1],
            "n": n,
            "ci_method": "wilson_95",
        },
        {
            "metric": "All-Valid@3",
            "value": all_valid_at_3_rate,
            "ci_lower": (0.0, 0.0),
            "ci_upper": (0.0, 0.0),
            "n": n,
            "ci_method": "not_measured_for_ci",
        },
        {
            "metric": "Valid@3",
            "value": mean_valid_at_3,
            "ci_lower": valid_at_3_ci[0],
            "ci_upper": valid_at_3_ci[1],
            "n": n,
            "ci_method": "case_bootstrap_95_seed_20260816_iterations_10000",
        },
        {
            "metric": "Preferred-in-Top3",
            "value": mean_preferred_in_top3,
            "ci_lower": preferred_in_top3_ci[0],
            "ci_upper": preferred_in_top3_ci[1],
            "n": n,
            "ci_method": "case_bootstrap_95_seed_20260816_iterations_10000",
        },
        {
            "metric": "No-Task Rate",
            "value": no_task_rate,
            "ci_lower": (0.0, 0.0),
            "ci_upper": (0.0, 0.0),
            "n": n,
            "ci_method": "not_measured_for_ci",
        },
        {
            "metric": "Mean Eligible Candidate Count (before filter)",
            "value": mean_eligible_before,
            "ci_lower": (0.0, 0.0),
            "ci_upper": (0.0, 0.0),
            "n": n,
            "ci_method": "not_measured_for_ci",
        },
        {
            "metric": "Mean Eligible Candidate Count (after filter)",
            "value": mean_eligible_after,
            "ci_lower": (0.0, 0.0),
            "ci_upper": (0.0, 0.0),
            "n": n,
            "ci_method": "not_measured_for_ci",
        },
        {
            "metric": "Median Eligible Candidate Count (before filter)",
            "value": float(median_eligible_before),
            "ci_lower": (0.0, 0.0),
            "ci_upper": (0.0, 0.0),
            "n": n,
            "ci_method": "not_measured_for_ci",
        },
        {
            "metric": "Median Eligible Candidate Count (after filter)",
            "value": float(median_eligible_after),
            "ci_lower": (0.0, 0.0),
            "ci_upper": (0.0, 0.0),
            "n": n,
            "ci_method": "not_measured_for_ci",
        },
    ]

    subgroups: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        subgroups.setdefault(result["query_style"], []).append(result)

    subgroup_rows: list[dict[str, Any]] = []
    for style, items in sorted(subgroups.items()):
        n_sub = len(items)
        valid_at_1 = statistics.mean([1.0 if r["valid_at_1"] else 0.0 for r in items])
        invalid = statistics.mean([1.0 if r["top1_label"] == "invalid" else 0.0 for r in items])
        preferred_at_1 = statistics.mean([1.0 if r["preferred_at_1"] else 0.0 for r in items])
        preferred_in_top3 = statistics.mean([r["preferred_in_top3"] for r in items])
        valid_at_3 = statistics.mean([r["valid_at_3"] for r in items])
        subgroup_rows.extend(
            [
                {
                    "subgroup": style,
                    "metric": "Valid@1",
                    "value": valid_at_1,
                    "n": n_sub,
                },
                {
                    "subgroup": style,
                    "metric": "Invalid Recommendation Rate",
                    "value": invalid,
                    "n": n_sub,
                },
                {
                    "subgroup": style,
                    "metric": "Preferred@1",
                    "value": preferred_at_1,
                    "n": n_sub,
                },
                {
                    "subgroup": style,
                    "metric": "Valid@3",
                    "value": valid_at_3,
                    "n": n_sub,
                },
                {
                    "subgroup": style,
                    "metric": "Preferred-in-Top3",
                    "value": preferred_in_top3,
                    "n": n_sub,
                },
            ]
        )

    return {
        "rows": rows,
        "subgroup_rows": subgroup_rows,
        "diagnostics": {
            "n": n,
            "eligible_before_values": eligible_counts_before,
            "eligible_after_values": eligible_counts_after,
        },
    }


def _evaluate_claims(metrics_by_name: dict[str, float], run_id: str) -> list[dict[str, Any]]:
    claim_rows: list[dict[str, Any]] = []
    for claim_id, metric_short, claim_text, rule, kind in CLAIM_DEFINITIONS:
        metric_value = metrics_by_name.get(metric_short)
        if kind == "always_unsupported":
            status = "UNSUPPORTED"
            evidence = json.dumps(["not_measured"])
        elif kind == "support_threshold":
            threshold = 0.90 if metric_short == "Valid@1" else 0.70 if metric_short == "Preferred@1" else 0.80
            status = "SUPPORTED" if metric_value is not None and metric_value >= threshold else "NOT_SUPPORTED"
            evidence = json.dumps({"value": metric_value, "threshold": threshold})
        elif kind == "support_threshold_reverse":
            threshold = 0.10
            status = "SUPPORTED" if metric_value is not None and metric_value <= threshold else "NOT_SUPPORTED"
            evidence = json.dumps({"value": metric_value, "threshold": threshold})
        else:
            status = "PENDING"
            evidence = json.dumps(["unknown_kind"])
        claim_rows.append(
            {
                "claim_id": claim_id,
                "claim": claim_text,
                "status": status,
                "evaluation_rule": rule,
                "evidence": evidence,
                "run_id": run_id,
            }
        )
    return claim_rows


def write_pending_claims(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        handle.write("claim_id,claim,status,evaluation_rule,evidence,run_id\n")
        for claim_id, metric_short, claim_text, rule, _kind in CLAIM_DEFINITIONS:
            handle.write(
                f"{claim_id},{claim_text},PENDING,preregistered_before_run; mechanically evaluated after 24 cases,not_yet_measured,preregistered_before_run\n"
            )


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


def run_evaluation(
    *,
    client,
    api_key: str,
    output_root: Path = Path("evaluation/runs"),
    claim_path: Path = Path("evaluation/claims/claim_registry_task_v1.csv"),
) -> Path:
    import time

    created_at = datetime.now(UTC)
    run_id = created_at.strftime("%Y%m%dT%H%M%SZ_task_recommendation_v1")
    contract = validate_production_contract()
    frozen = _load_frozen_inputs()
    cases = frozen["cases"]

    source_tree_before = _hash_files(RELEVANT_PRODUCTION_SOURCES)
    runner_hash = file_sha256(Path(__file__))
    uv_lock_hash = (
        file_sha256(Path("uv.lock")) if Path("uv.lock").exists() else "not_present"
    )
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    raw_path = run_dir / "per_case_results.jsonl"
    raw_path.write_text("", encoding="utf-8")

    write_pending_claims(claim_path)
    results: list[dict[str, Any]] = []
    with raw_path.open("a", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            result = execute_case(
                case, client=client, api_key=api_key, clock_fn=time.perf_counter
            )
            results.append(result)
            handle.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()

    model_call_counts = {
        key: sum(result["model_call_counts"][key] for result in results)
        for key in ("text_embedding_v4", "qwen3_rerank", "qwen_plus")
    }

    if model_call_counts["qwen_plus"] != 0:
        raise RuntimeError(f"qwen-plus was called: {model_call_counts['qwen_plus']}")

    if model_call_counts["text_embedding_v4"] > 24:
        raise RuntimeError(f"too many embedding calls: {model_call_counts['text_embedding_v4']}")
    if model_call_counts["qwen3_rerank"] > 24:
        raise RuntimeError(f"too many rerank calls: {model_call_counts['qwen3_rerank']}")

    post = _load_frozen_inputs()
    if (
        post["gold_sha256"] != frozen["gold_sha256"]
        or post["corpus_sha256"] != frozen["corpus_sha256"]
    ):
        raise RuntimeError("Gold or task corpus changed after recommendation results were seen")
    if _hash_files(RELEVANT_PRODUCTION_SOURCES) != source_tree_before:
        raise RuntimeError("Production source tree changed during task evaluation")

    aggregates = aggregate_metrics(results, run_id=run_id)
    metrics_by_name = {row["metric"]: row["value"] for row in aggregates["rows"]}
    claim_rows = _evaluate_claims(metrics_by_name, run_id)

    metrics_json = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "gold_sha256": frozen["gold_sha256"],
        "task_corpus_sha256": frozen["corpus_sha256"],
        "case_count": len(results),
        "failed_cases": 0,
        "metrics": aggregates["rows"],
        "subgroup_metrics": aggregates["subgroup_rows"],
        "diagnostics": aggregates["diagnostics"],
        "model_call_counts": model_call_counts,
        "production_contract": contract,
        "memory_enabled": False,
        "personalization_enabled": False,
        "qwen_plus_executed": False,
        "gold_modified_after_results_seen": False,
        "task_corpus_modified": False,
        "production_semantics_modified": False,
    }
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_csv(
        run_dir / "metrics.csv",
        [
            {**row, "ci_lower": row["ci_lower"], "ci_upper": row["ci_upper"]}
            for row in aggregates["rows"]
        ],
        ("metric", "value", "ci_lower", "ci_upper", "n", "ci_method"),
    )
    paper_rows = [
        {
            "experiment": "task_recommendation_v1",
            "metric": row["metric"],
            "value": row["value"],
            "n": row["n"],
            "provenance_level": "A+B+C",
            "run_id": run_id,
        }
        for row in aggregates["rows"]
    ]
    _write_csv(
        run_dir / "paper_metrics.csv",
        paper_rows,
        ("experiment", "metric", "value", "n", "provenance_level", "run_id"),
    )
    table_rows = [
        {
            "metric": row["metric"],
            "value": row["value"],
            "ci_lower": row["ci_lower"],
            "ci_upper": row["ci_upper"],
            "n": row["n"],
        }
        for row in aggregates["rows"]
    ]
    _write_csv(
        run_dir / "task_recommendation_table.csv",
        table_rows,
        ("metric", "value", "ci_lower", "ci_upper", "n"),
    )
    _write_csv(
        run_dir / "subgroup_metrics.csv",
        aggregates["subgroup_rows"],
        ("subgroup", "metric", "value", "n"),
    )

    provenance = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "gold_sha256": frozen["gold_sha256"],
        "task_corpus_sha256": frozen["corpus_sha256"],
        "source_tree_sha256": source_tree_before,
        "runner_sha256": runner_hash,
        "lockfile_sha256": uv_lock_hash,
        "git_commit": _git_commit(),
        "python_version": platform.python_version(),
        **contract,
        "memory_enabled": False,
        "personalization_enabled": False,
        "qwen_plus_executed": False,
        "gold_modified_after_results_seen": False,
        "task_corpus_modified": False,
        "production_semantics_modified": False,
        "model_call_counts": model_call_counts,
        "cases_executed": len(results),
        "failed_cases": 0,
    }
    (run_dir / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    claim_path.parent.mkdir(parents=True, exist_ok=True)
    with claim_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("claim_id", "claim", "status", "evaluation_rule", "evidence", "run_id"),
        )
        writer.writeheader()
        writer.writerows(claim_rows)

    print(json.dumps({"run_id": run_id, "run_dir": str(run_dir)}, ensure_ascii=False))
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()
    env_file = Path(".env")
    api_key = load_api_key(env_file)
    es_url = _env_value("ELASTICSEARCH_URL", env_file) or "http://127.0.0.1:9200"
    client = Elasticsearch(es_url, request_timeout=60)
    try:
        if not client.ping():
            raise RuntimeError(f"Elasticsearch is not reachable: {es_url}")
        run_evaluation(client=client, api_key=api_key)
    finally:
        client.close()


if __name__ == "__main__":
    main()