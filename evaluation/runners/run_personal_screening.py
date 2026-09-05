"""Run Stage 6A-PERS Basic-only recommendation competition screening."""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from elasticsearch import Elasticsearch
from pydantic import ValidationError

from weilv import basic_rag
from weilv.api.schemas import RecommendationRequest
from weilv.dashscope_models import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    RERANK_MODEL,
)
from weilv.retrieval_slice import _env_value, load_api_key
from weilv.safety_rules import evaluate_input_risk, filter_task_by_safety, load_safety_rules

DATASET_NAME = "personal_rag_screening_v1"
DATASET_VERSION = "personal_rag_screening_v1"
DEFAULT_DATASET_PATH = Path("evaluation/datasets/personal_rag_screening_v1.jsonl")
DEFAULT_OUTPUT_ROOT = Path("evaluation/runs")
KNOWLEDGE_INDEX = "health_knowledge_v1"
TASK_INDEX = "micro_tasks_v1"
BM25_RECALL_K = inspect.signature(basic_rag.bm25_search).parameters["size"].default
VECTOR_RECALL_K = inspect.signature(basic_rag.vector_search).parameters["size"].default
# 非安全输入的 bool 开关（易启动偏好等）不进入冻结评估的安全字段集。
NON_SAFETY_BOOL_FIELDS = {"prefer_easy_start"}
SAFETY_INPUT_FIELDS = tuple(
    name
    for name, field in RecommendationRequest.model_fields.items()
    if field.annotation is bool
    and field.default is False
    and name not in NON_SAFETY_BOOL_FIELDS
)
MODEL_CALL_KEYS = (
    "text_embedding_v4",
    "qwen3_rerank",
    "qwen_plus",
    "memory_retrieval",
    "personalization",
)
CSV_FIELDS = (
    "case_id",
    "archetype_id",
    "status",
    "eligible_candidate_count",
    "rank_1_task_id",
    "rank_2_task_id",
    "rank_3_task_id",
    "rank_4_task_id",
    "rank_5_task_id",
    "selected_task_id",
    "matched_rule_ids",
    "latency_ms",
)


def _validated_request(case: dict) -> basic_rag.BasicRagRequest:
    safety_inputs = case.get("safety_inputs")
    if not isinstance(safety_inputs, dict) or set(safety_inputs) != set(SAFETY_INPUT_FIELDS):
        raise ValueError(
            f"{case.get('case_id', '<unknown>')} safety_inputs must contain exactly "
            f"{list(SAFETY_INPUT_FIELDS)}"
        )
    if any(type(value) is not bool for value in safety_inputs.values()):
        raise ValueError(f"{case.get('case_id', '<unknown>')} safety_inputs must be booleans")
    try:
        payload = RecommendationRequest(
            user_id=f"evaluation:{case['case_id']}",
            query=case["query"],
            target_stage=case["target_stage"],
            current_context=case["current_context"],
            activity_context=case["activity_context"],
            available_minutes=case["available_minutes"],
            **safety_inputs,
        )
    except (KeyError, ValidationError) as exc:
        raise ValueError(f"invalid formal request schema for {case.get('case_id')}: {exc}") from exc
    return basic_rag.BasicRagRequest(**payload.model_dump(exclude={"user_id"}))


def load_dataset(
    path: Path = DEFAULT_DATASET_PATH,
    *,
    expected_case_count: int | None = 24,
    expected_archetype_count: int | None = 12,
) -> list[dict]:
    cases = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    case_ids = [case.get("case_id") for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case_id values must be unique")
    if expected_case_count is not None and len(cases) != expected_case_count:
        raise ValueError(f"expected {expected_case_count} cases, found {len(cases)}")

    counts = Counter(case.get("archetype_id") for case in cases)
    if expected_archetype_count is not None:
        expected_ids = {f"CA-{index:02d}" for index in range(1, expected_archetype_count + 1)}
        if set(counts) != expected_ids or any(count != 2 for count in counts.values()):
            raise ValueError("dataset must contain exactly two cases for each CA-01 through CA-12")

    for case in cases:
        if case.get("dataset_version") != DATASET_VERSION:
            raise ValueError(f"invalid dataset_version for {case.get('case_id')}")
        if case.get("provenance_level") != "C":
            raise ValueError(f"invalid provenance_level for {case.get('case_id')}")
        if not case.get("description"):
            raise ValueError(f"description is required for {case.get('case_id')}")
        _validated_request(case)
    return cases


def _empty_counts() -> dict[str, int]:
    return dict.fromkeys(MODEL_CALL_KEYS, 0)


def screen_case(case: dict, client, api_key: str) -> dict:
    started = time.perf_counter()
    request = _validated_request(case)
    rules = load_safety_rules()
    safety_context = basic_rag._safety_context(request)
    input_result = evaluate_input_risk(safety_context, rules)
    counts = _empty_counts()

    if input_result["status"] in {"blocked", "help_seeking"}:
        return _case_result(
            case,
            input_result,
            [],
            [],
            {},
            counts,
            started,
        )

    counts["text_embedding_v4"] += 1
    query_vector = basic_rag.embed_texts(
        [request.query], api_key=api_key, text_type="query"
    )[0]
    task_filters = basic_rag._task_filters(request)
    bm25 = basic_rag.bm25_search(
        client,
        request.query,
        TASK_INDEX,
        size=BM25_RECALL_K,
        raw_filters=task_filters,
        search_fields=["title^2", "instruction", "trigger", "domain", "context_tags"],
    )
    vector = basic_rag.vector_search(
        client,
        query_vector,
        TASK_INDEX,
        size=VECTOR_RECALL_K,
        raw_filters=task_filters,
    )
    task_candidates = basic_rag.merge_candidates(
        bm25, vector, identity_field="task_id"
    )
    metadata_tasks = [
        task for task in task_candidates if basic_rag._matches_task_metadata(task, request)
    ]
    safe_result = basic_rag.select_safe_tasks(metadata_tasks, safety_context, rules)
    safe_ids = {task["task_id"] for task in safe_result["tasks"]}
    filtered_reasons = {}
    for task in task_candidates:
        task_id = task["task_id"]
        if task not in metadata_tasks:
            filtered_reasons[task_id] = ["metadata_filter_mismatch"]
        elif task_id not in safe_ids:
            filtered_reasons[task_id] = filter_task_by_safety(
                task, safety_context, rules
            )["reason_codes"]

    reranked_tasks = []
    if safe_result["tasks"]:
        counts["qwen3_rerank"] += 1
        reranked_tasks = basic_rag._rerank(
            request.query,
            safe_result["tasks"],
            [basic_rag._task_document(task) for task in safe_result["tasks"]],
            api_key,
        )

    status_result = safe_result
    if not reranked_tasks and safe_result["status"] == "allowed":
        status_result = {
            "status": "no_safe_task",
            "matched_rule_ids": ["SR-012"],
            "reason_codes": ["no_safe_whitelist_task"],
        }
    return _case_result(
        case,
        status_result,
        reranked_tasks,
        [task["task_id"] for task in safe_result["tasks"]],
        filtered_reasons,
        counts,
        started,
    )


def _case_result(
    case: dict,
    status_result: dict,
    reranked_tasks: list[dict],
    eligible_task_ids: list[str],
    filtered_reasons: dict[str, list[str]],
    counts: dict[str, int],
    started: float,
) -> dict:
    ranking = [
        {
            "task_id": task["task_id"],
            "base_rank": position,
            **(
                {"rerank_score": task["rerank_score"]}
                if "rerank_score" in task
                else {}
            ),
        }
        for position, task in enumerate(reranked_tasks, start=1)
    ]
    return {
        "case_id": case["case_id"],
        "archetype_id": case["archetype_id"],
        "status": status_result["status"],
        "matched_rule_ids": status_result["matched_rule_ids"],
        "eligible_candidate_count": len(eligible_task_ids),
        "eligible_task_ids": eligible_task_ids,
        "candidate_ranking": ranking,
        "selected_task_id": ranking[0]["task_id"] if ranking else None,
        "filtered_task_ids": list(filtered_reasons),
        "filter_reason_codes": filtered_reasons,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "model_call_counts": counts,
    }


def _dataset_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unavailable:not-a-git-worktree"
    return completed.stdout.strip()


def _summed_counts(results: list[dict]) -> dict[str, int]:
    return {
        key: sum(result["model_call_counts"][key] for result in results)
        for key in MODEL_CALL_KEYS
    }


def run_screening(
    cases: list[dict],
    client,
    api_key: str,
    dataset_path: Path = DEFAULT_DATASET_PATH,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    run_id: str | None = None,
) -> Path:
    created_at = datetime.now(UTC)
    run_id = run_id or created_at.strftime("%Y%m%dT%H%M%SZ_personal_rag_screening_v1")
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    results = [screen_case(case, client, api_key) for case in cases]
    call_counts = _summed_counts(results)
    config = {
        "dataset_name": DATASET_NAME,
        "dataset_version": DATASET_VERSION,
        "pipeline": "basic_rag_screening",
        "memory": "off",
        "personalization": "off",
        "knowledge_retrieval": "off_not_required_by_task_ranking",
        "knowledge_index": KNOWLEDGE_INDEX,
        "task_index": TASK_INDEX,
        "BM25_RECALL_K": BM25_RECALL_K,
        "VECTOR_RECALL_K": VECTOR_RECALL_K,
    }
    provenance = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "git_commit": _git_commit(),
        "dataset_name": DATASET_NAME,
        "dataset_version": DATASET_VERSION,
        "dataset_sha256": _dataset_sha256(dataset_path),
        "pipeline": "basic_rag_screening",
        "memory": "off",
        "personalization": "off",
        "BM25_RECALL_K": BM25_RECALL_K,
        "VECTOR_RECALL_K": VECTOR_RECALL_K,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dim": EMBEDDING_DIMENSION,
        "reranker_model": RERANK_MODEL,
        "qwen_plus_used": False,
        "model_call_counts": call_counts,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (run_dir / "per_case_results.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
    with (run_dir / "screening_summary.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for result in results:
            ranks = [item["task_id"] for item in result["candidate_ranking"][:5]]
            writer.writerow(
                {
                    "case_id": result["case_id"],
                    "archetype_id": result["archetype_id"],
                    "status": result["status"],
                    "eligible_candidate_count": result["eligible_candidate_count"],
                    **{
                        f"rank_{position}_task_id": (
                            ranks[position - 1] if len(ranks) >= position else ""
                        )
                        for position in range(1, 6)
                    },
                    "selected_task_id": result["selected_task_id"] or "",
                    "matched_rule_ids": "|".join(result["matched_rule_ids"]),
                    "latency_ms": result["latency_ms"],
                }
            )
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    cases = load_dataset(args.dataset)
    env_file = Path(".env")
    api_key = load_api_key(env_file)
    es_url = _env_value("ELASTICSEARCH_URL", env_file) or "http://127.0.0.1:9200"
    client = Elasticsearch(es_url, request_timeout=30)
    try:
        if not client.ping():
            raise RuntimeError(f"Elasticsearch is not reachable: {es_url}")
        run_dir = run_screening(
            cases,
            client,
            api_key,
            dataset_path=args.dataset,
            output_root=args.output_root,
        )
    finally:
        client.close()
    print(run_dir)


if __name__ == "__main__":
    main()
