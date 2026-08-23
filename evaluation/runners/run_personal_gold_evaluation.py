"""Run Stage 6B-PERS against a frozen Basic-only candidate baseline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch

from weilv import personal_memory_retrieval, personal_rag, user_memory
from weilv.dashscope_models import EMBEDDING_DIMENSION, EMBEDDING_MODEL, RERANK_MODEL
from weilv.retrieval_slice import _env_value, load_api_key

DATASET_VERSION = "personal_rag_gold_v1"
BASELINE_RUN_ID = "20260816T061751Z_personal_rag_screening_v1"
BASELINE_DATASET_SHA256 = "e173985aa44288888c8717d1b9ae47ee554dcfbf12000ec92e78d0540df8b66f"
DEFAULT_GOLD_PATH = Path("evaluation/datasets/personal_rag_gold_v1.jsonl")
DEFAULT_BASELINE_PATH = Path(
    f"evaluation/runs/{BASELINE_RUN_ID}/per_case_results.jsonl"
)
DEFAULT_SCENARIO_PATH = Path("evaluation/datasets/personal_rag_screening_v1.jsonl")
DEFAULT_TASK_PATH = Path("data/metadata/micro_tasks_v1.jsonl")
DEFAULT_OUTPUT_ROOT = Path("evaluation/runs")
DEFAULT_CLAIM_PATH = Path("evaluation/claims/claim_registry_personal_v1.csv")
RELEVANT_PRODUCTION_SOURCES = (
    Path("src/weilv/user_memory.py"),
    Path("src/weilv/personal_memory_retrieval.py"),
    Path("src/weilv/personal_rag.py"),
    Path("src/weilv/retrieval.py"),
    Path("src/weilv/dashscope_models.py"),
)
MODEL_CALL_KEYS = (
    "memory_document_embedding",
    "memory_query_embedding",
    "memory_embedding",
    "memory_reranker",
    "task_embedding",
    "task_reranker",
    "qwen_plus",
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_file_hash_unchanged(path: Path, frozen_sha256: str, label: str) -> None:
    if file_sha256(path) != frozen_sha256:
        raise RuntimeError(f"{label} changed after execution started")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_baseline(path: Path = DEFAULT_BASELINE_PATH) -> dict[str, dict[str, Any]]:
    rows = _read_jsonl(path)
    baseline = {row["case_id"]: row for row in rows}
    if len(rows) != len(baseline):
        raise ValueError("frozen baseline case_id values must be unique")
    for row in rows:
        ranking_ids = [item["task_id"] for item in row["candidate_ranking"]]
        ranks = [item["base_rank"] for item in row["candidate_ranking"]]
        if set(ranking_ids) != set(row["eligible_task_ids"]):
            raise ValueError(f"baseline eligible/ranking mismatch for {row['case_id']}")
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError(f"baseline base_rank sequence invalid for {row['case_id']}")
    return baseline


def build_memory_candidate(
    payload: dict[str, Any], user_id: str, timestamp: str
) -> user_memory.UserMemoryCandidate:
    memory_type = payload["memory_type"]
    source_type = (
        "structured_task_feedback"
        if memory_type == "task_feedback"
        else "explicit_user_setting"
    )
    return user_memory.UserMemoryCandidate(
        memory_id="",
        user_id=user_id,
        memory_type=memory_type,
        source_type=source_type,
        task_id=payload.get("task_id"),
        domain=None,
        memory_key=payload["memory_key"],
        memory_value=payload["memory_value"],
        created_at=timestamp,
        updated_at=timestamp,
    )


def load_gold(
    path: Path, baseline: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], str]:
    gold = _read_jsonl(path)
    expected_ids = [f"G{index:02d}" for index in range(1, 13)]
    if [case.get("gold_case_id") for case in gold] != expected_ids:
        raise ValueError("Gold must contain ordered unique IDs G01 through G12")

    all_formal_task_ids = {
        task_id
        for row in baseline.values()
        for task_id in [*row["eligible_task_ids"], *row["filtered_task_ids"]]
    }
    profile = user_memory.UserProfile("gold-validation", "junior_high", True, "now", "now")
    for case in gold:
        case_id = case["gold_case_id"]
        if case.get("dataset_version") != DATASET_VERSION:
            raise ValueError(f"invalid dataset_version for {case_id}")
        if case.get("provenance_level") != "B+C":
            raise ValueError(f"invalid provenance_level for {case_id}")
        source_id = case["source_scenario_id"]
        if source_id not in baseline:
            raise ValueError(f"unknown baseline scenario for {case_id}")
        base_ranks = {
            item["task_id"]: item["base_rank"]
            for item in baseline[source_id]["candidate_ranking"]
        }
        for target in case["gold_expectation"].get("target_ranks", []):
            if base_ranks.get(target["task_id"]) != target["base_rank"]:
                raise ValueError(f"Gold base_rank mismatch for {case_id}")
        for payload in case["synthetic_memories"]:
            candidate = build_memory_candidate(payload, profile.user_id, "now")
            validation = user_memory.validate_memory_candidate(
                profile, candidate, all_formal_task_ids
            )
            if not validation["valid"]:
                raise ValueError(
                    f"gold_input_invalid {case_id}: {validation['reason_codes']}"
                )
    return gold, file_sha256(path)


def evaluation_user_id(gold_case_id: str, run_id: str) -> str:
    safe_run_id = re.sub(r"[^a-z0-9]+", "_", run_id.lower()).strip("_")
    return f"eval_pers_{gold_case_id.lower()}_{safe_run_id}"


def personalize_frozen_candidates(
    base_ranking: list[dict[str, Any]], memories: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    tasks = [
        {
            "task_id": item["task_id"],
            "rerank_rank": item["base_rank"],
            **(
                {"rerank_score": item["rerank_score"]}
                if "rerank_score" in item
                else {}
            ),
        }
        for item in base_ranking
    ]
    personalized = personal_rag.personalize_task_candidates(tasks, memories)
    base_ids = [task["task_id"] for task in tasks]
    personal_ids = [task["task_id"] for task in personalized]
    if len(personal_ids) != len(base_ids) or set(personal_ids) != set(base_ids):
        raise RuntimeError("candidate set changed during personalization")
    return [
        {
            "task_id": task["task_id"],
            "base_rank": task["personalization"]["base_task_rank"],
            "personalization_delta": task["personalization"]["personalization_delta"],
            "adjusted_rank": task["personalization"]["adjusted_rank"],
            "personal_rank": position,
        }
        for position, task in enumerate(personalized, start=1)
    ]


def _controlled_top1_aligned(top1: str | None, rule: dict[str, str] | None) -> bool | None:
    if rule is None:
        return None
    if rule["operator"] == "equals":
        return top1 == rule["task_id"]
    if rule["operator"] == "not_equals":
        return top1 != rule["task_id"]
    raise ValueError(f"unsupported controlled_top1 operator: {rule['operator']}")


def _evaluate_expectation(
    gold: dict[str, Any],
    baseline: dict[str, Any],
    personal_ranking: list[dict[str, Any]],
    memory_retrieval_hit: bool,
) -> dict[str, Any]:
    expectation = gold["gold_expectation"]
    base_ids = [item["task_id"] for item in baseline["candidate_ranking"]]
    personal_ids = [item["task_id"] for item in personal_ranking]
    personal_ranks = {item["task_id"]: item["personal_rank"] for item in personal_ranking}
    candidate_set_unchanged = len(base_ids) == len(personal_ids) and set(base_ids) == set(
        personal_ids
    )
    checks = [candidate_set_unchanged, memory_retrieval_hit]
    promotion_gains = []
    demotion_changes = []
    for target in expectation.get("target_ranks", []):
        actual_rank = personal_ranks.get(target["task_id"])
        checks.append(actual_rank == target["expected_personal_rank"])
        if target["expected_direction"] == "promote":
            checks.append(actual_rank is not None and actual_rank < target["base_rank"])
            if target.get("metric_role") == "promotion" and actual_rank is not None:
                promotion_gains.append(target["base_rank"] - actual_rank)
        elif target["expected_direction"] == "demote":
            checks.append(actual_rank is not None and actual_rank > target["base_rank"])
            if target.get("metric_role") == "demotion" and actual_rank is not None:
                demotion_changes.append(actual_rank - target["base_rank"])

    base_top1 = base_ids[0] if base_ids else None
    personal_top1 = personal_ids[0] if personal_ids else None
    if expected_top1 := expectation.get("expected_top1"):
        checks.append(personal_top1 == expected_top1)
    checks.extend(
        personal_top1 != task_id
        for task_id in expectation.get("forbidden_top1_task_ids", [])
    )
    forbidden_ranked = expectation.get("forbidden_ranked_task_ids", [])
    filtered_target_still_absent = (
        all(task_id not in personal_ids for task_id in forbidden_ranked)
        if forbidden_ranked
        else None
    )
    if filtered_target_still_absent is not None:
        checks.append(filtered_target_still_absent)
    if expected_ids := expectation.get("expected_candidate_ids"):
        checks.append(personal_ids == expected_ids)
    ranking_unchanged = personal_ids == base_ids
    if expectation.get("ranking_unchanged"):
        checks.append(ranking_unchanged)

    controlled_rule = expectation.get("controlled_top1")
    safety_pass = (
        candidate_set_unchanged and bool(filtered_target_still_absent)
        if expectation.get("safety_invariance")
        else None
    )
    context_pass = (
        candidate_set_unchanged and bool(filtered_target_still_absent) and ranking_unchanged
        if expectation.get("context_non_resurrection")
        else None
    )
    irrelevant_noop = (
        candidate_set_unchanged and ranking_unchanged
        if expectation.get("irrelevant_memory_noop")
        else None
    )
    unsupported_noop = (
        candidate_set_unchanged and ranking_unchanged
        if expectation.get("unsupported_memory_noop")
        else None
    )
    bounded_pass = (
        personal_ranks.get("MT-REC-002") == 2 and personal_top1 == "MT-BREAK-001"
        if expectation.get("bounded_personalization")
        else None
    )
    for optional_check in (safety_pass, context_pass, irrelevant_noop, unsupported_noop, bounded_pass):
        if optional_check is not None:
            checks.append(optional_check)
    return {
        "gold_pass": all(checks),
        "candidate_set_unchanged": candidate_set_unchanged,
        "filtered_target_still_absent": filtered_target_still_absent,
        "base_top1": base_top1,
        "personal_top1": personal_top1,
        "promotion_rank_gains": promotion_gains,
        "demotion_rank_changes": demotion_changes,
        "basic_controlled_top1_aligned": _controlled_top1_aligned(
            base_top1, controlled_rule
        ),
        "personal_controlled_top1_aligned": _controlled_top1_aligned(
            personal_top1, controlled_rule
        ),
        "safety_invariance_pass": safety_pass,
        "context_non_resurrection_pass": context_pass,
        "irrelevant_memory_noop_pass": irrelevant_noop,
        "unsupported_memory_noop_pass": unsupported_noop,
        "bounded_personalization_pass": bounded_pass,
    }


def _zero_model_calls() -> dict[str, int]:
    return dict.fromkeys(MODEL_CALL_KEYS, 0)


def execute_gold_case(
    gold: dict[str, Any],
    scenario: dict[str, Any],
    baseline: dict[str, Any],
    *,
    eval_user_id: str,
    client,
    api_key: str,
    valid_task_ids: set[str],
) -> dict[str, Any]:
    started = time.perf_counter()
    now = datetime.now(UTC).isoformat()
    profile = user_memory.UserProfile(
        eval_user_id, scenario["target_stage"], True, now, now
    )
    user_memory.upsert_user_profile(client, profile)
    memory_ids = []
    payloads = gold["synthetic_memories"]
    for payload in payloads:
        candidate = build_memory_candidate(payload, eval_user_id, now)
        created = user_memory.create_memory(client, profile, candidate, valid_task_ids)
        if created["status"] != "created":
            raise RuntimeError(
                f"memory creation failed for {gold['gold_case_id']}: {created}"
            )
        memory_id = created["memory_id"]
        memory_ids.append(memory_id)
        embedded = personal_memory_retrieval.embed_memory(
            client, eval_user_id, memory_id, api_key
        )
        if embedded["status"] != "embedded":
            raise RuntimeError(
                f"memory embedding failed for {gold['gold_case_id']}: {embedded}"
            )

    retrieved = personal_memory_retrieval.retrieve_personal_memories(
        client, profile, scenario["query"], api_key
    )
    retrieved_ids = [memory["memory_id"] for memory in retrieved]
    memory_retrieval_hit = set(memory_ids).issubset(retrieved_ids)
    personal_ranking = personalize_frozen_candidates(
        baseline["candidate_ranking"], retrieved
    )
    evaluation = _evaluate_expectation(
        gold, baseline, personal_ranking, memory_retrieval_hit
    )
    return {
        "gold_case_id": gold["gold_case_id"],
        "source_scenario_id": gold["source_scenario_id"],
        "eval_user_id": eval_user_id,
        "baseline_run_id": BASELINE_RUN_ID,
        "valid": True,
        "base_candidate_ids": baseline["eligible_task_ids"],
        "base_ranking": baseline["candidate_ranking"],
        "synthetic_memory_payload": payloads,
        "memory_id": memory_ids[0] if len(memory_ids) == 1 else memory_ids,
        "memory_ids": memory_ids,
        "retrieved_memory_ids": retrieved_ids,
        "retrieved_memory_types": [memory["memory_type"] for memory in retrieved],
        "retrieved_task_ids": [memory.get("task_id") for memory in retrieved],
        "retrieved_memories": [
            {
                "memory_id": memory["memory_id"],
                "memory_type": memory["memory_type"],
                "task_id": memory.get("task_id"),
                "memory_rank": memory.get("rerank_rank"),
                **(
                    {"memory_rerank_score": memory["rerank_score"]}
                    if "rerank_score" in memory
                    else {}
                ),
            }
            for memory in retrieved
        ],
        "memory_retrieval_hit": memory_retrieval_hit,
        "memory_retrieval_miss": not memory_retrieval_hit,
        "personalization_delta_by_task": {
            item["task_id"]: item["personalization_delta"] for item in personal_ranking
        },
        "adjusted_rank_by_task": {
            item["task_id"]: item["adjusted_rank"] for item in personal_ranking
        },
        "personal_ranking": personal_ranking,
        "gold_expectation": gold["gold_expectation"],
        **evaluation,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "model_call_counts": _zero_model_calls(),
    }


class MemoryModelCallCounter:
    def __init__(self) -> None:
        self.counts = _zero_model_calls()
        self._embed = None
        self._rerank = None

    def __enter__(self):
        self._embed = personal_memory_retrieval.embed_texts
        self._rerank = personal_memory_retrieval.rerank_texts

        def counted_embed(texts, api_key, text_type):
            key = (
                "memory_document_embedding"
                if text_type == "document"
                else "memory_query_embedding"
            )
            self.counts[key] += 1
            self.counts["memory_embedding"] += 1
            return self._embed(texts, api_key, text_type)

        def counted_rerank(query, documents, api_key):
            self.counts["memory_reranker"] += 1
            return self._rerank(query, documents, api_key)

        personal_memory_retrieval.embed_texts = counted_embed
        personal_memory_retrieval.rerank_texts = counted_rerank
        return self

    def __exit__(self, *_args):
        personal_memory_retrieval.embed_texts = self._embed
        personal_memory_retrieval.rerank_texts = self._rerank

    def snapshot(self) -> dict[str, int]:
        return dict(self.counts)


def _counter_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {key: after[key] - before[key] for key in MODEL_CALL_KEYS}


def _metric(
    name: str,
    numerator: float,
    denominator: int,
    value: float | str,
    case_ids: list[str],
    run_id: str,
    *,
    per_case: dict[str, float] | None = None,
) -> dict[str, Any]:
    result = {
        "metric_name": name,
        "numerator": numerator,
        "denominator": denominator,
        "value": value,
        "applicable_case_ids": case_ids,
        "run_id": run_id,
    }
    if per_case is not None:
        result["per_case"] = per_case
    return result


def calculate_metrics(
    results: list[dict[str, Any]], run_id: str
) -> dict[str, dict[str, Any]]:
    valid = [result for result in results if result.get("valid")]

    def observations(field: str) -> list[tuple[str, float]]:
        return [
            (result["gold_case_id"], value)
            for result in valid
            for value in result.get(field, [])
        ]

    def boolean_observations(field: str) -> list[tuple[str, bool]]:
        return [
            (result["gold_case_id"], result[field])
            for result in valid
            if result.get(field) is not None
        ]

    promotion = observations("promotion_rank_gains")
    demotion = observations("demotion_rank_changes")
    metrics = {}

    def add_rate(name: str, values: list[tuple[str, bool]]) -> None:
        numerator = sum(bool(value) for _, value in values)
        metrics[name] = _metric(
            name,
            numerator,
            len(values),
            numerator / len(values) if values else "not_measured",
            [case_id for case_id, _ in values],
            run_id,
        )

    add_rate("Promotion Success Rate", [(case_id, gain > 0) for case_id, gain in promotion])
    add_rate("Demotion Success Rate", [(case_id, change > 0) for case_id, change in demotion])
    add_rate(
        "Basic Controlled Synthetic Preference-aligned Top1 Rate",
        boolean_observations("basic_controlled_top1_aligned"),
    )
    add_rate(
        "Personal Controlled Synthetic Preference-aligned Top1 Rate",
        boolean_observations("personal_controlled_top1_aligned"),
    )

    for name, values, reducer in (
        ("Mean Promotion Rank Gain", promotion, statistics.mean),
        ("Median Promotion Rank Gain", promotion, statistics.median),
        ("Mean Demotion Rank Change", demotion, statistics.mean),
        ("Median Demotion Rank Change", demotion, statistics.median),
    ):
        numeric = [value for _, value in values]
        metrics[name] = _metric(
            name,
            sum(numeric),
            len(numeric),
            reducer(numeric) if numeric else "not_measured",
            [case_id for case_id, _ in values],
            run_id,
            per_case={case_id: value for case_id, value in values},
        )

    for name, field in (
        ("Safety Invariance Rate", "safety_invariance_pass"),
        ("Context Non-resurrection Rate", "context_non_resurrection_pass"),
        ("Irrelevant-memory No-op Rate", "irrelevant_memory_noop_pass"),
        ("Unsupported-memory No-op Rate", "unsupported_memory_noop_pass"),
        ("Candidate-set Invariance Rate", "candidate_set_unchanged"),
        ("G12 Bounded Personalization Pass", "bounded_personalization_pass"),
    ):
        add_rate(name, boolean_observations(field))
    return metrics


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
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unavailable:not-a-git-worktree"
    return completed.stdout.strip()


def _write_metrics_csv(path: Path, metrics: dict[str, dict[str, Any]]) -> None:
    fields = (
        "metric_name",
        "numerator",
        "denominator",
        "value",
        "applicable_case_ids",
        "run_id",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for metric in metrics.values():
            row = {field: metric[field] for field in fields}
            row["applicable_case_ids"] = "|".join(row["applicable_case_ids"])
            writer.writerow(row)


def _paper_rows(metrics: dict[str, dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    rows = []
    mapping = (
        (
            "Basic Controlled Synthetic Preference-aligned Top1 Rate",
            "controlled_preference_top1",
            "Basic RAG",
        ),
        (
            "Personal Controlled Synthetic Preference-aligned Top1 Rate",
            "controlled_preference_top1",
            "Personal RAG",
        ),
        ("Promotion Success Rate", "promotion_success", "Personal RAG"),
        ("Demotion Success Rate", "demotion_success", "Personal RAG"),
        ("Mean Promotion Rank Gain", "mean_promotion_rank_gain", "Personal RAG"),
        ("Mean Demotion Rank Change", "mean_demotion_rank_change", "Personal RAG"),
        ("Safety Invariance Rate", "safety_invariance", "Personal RAG"),
        ("Candidate-set Invariance Rate", "candidate_set_invariance", "Personal RAG"),
    )
    for source_name, metric_name, method in mapping:
        metric = metrics[source_name]
        rows.append(
            {
                "experiment": "personalization",
                "metric": metric_name,
                "method": method,
                "value": metric["value"],
                "n": metric["denominator"],
                "provenance_level": "A+B+C",
                "run_id": run_id,
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _claim_rows(
    metrics: dict[str, dict[str, Any]], run_id: str
) -> list[dict[str, Any]]:
    definitions = (
        (
            "CR-PERS-001",
            "Structured positive User Memory promotes the corresponding eligible MicroTask ranking in the controlled Gold Set.",
            "Promotion Success Rate",
            "G01|G03|G05|G12",
            metrics["Promotion Success Rate"]["value"] == 1.0,
        ),
        (
            "CR-PERS-002",
            "Structured negative User Memory demotes the corresponding eligible MicroTask ranking.",
            "Demotion Success Rate",
            "G02|G04|G05",
            metrics["Demotion Success Rate"]["value"] == 1.0,
        ),
        (
            "CR-PERS-003",
            "Personal RAG improves Top1 alignment with controlled synthetic preference interventions relative to the frozen Basic ranking.",
            "Personal Controlled Synthetic Preference-aligned Top1 Rate",
            "G01|G02|G03|G04|G05",
            metrics["Personal Controlled Synthetic Preference-aligned Top1 Rate"]["value"]
            > metrics["Basic Controlled Synthetic Preference-aligned Top1 Rate"]["value"],
        ),
        (
            "CR-PERS-004",
            "Personalization does not resurrect Safety-filtered tasks.",
            "Safety Invariance Rate",
            "G06|G07",
            metrics["Safety Invariance Rate"]["value"] == 1.0,
        ),
        (
            "CR-PERS-005",
            "A valid Memory unrelated to the current candidate pool does not disturb current ranking.",
            "Irrelevant-memory No-op Rate",
            "G09",
            metrics["Irrelevant-memory No-op Rate"]["value"] == 1.0,
        ),
        (
            "CR-PERS-006",
            "Memory types without ranking semantics in v0.1 do not affect task ranking.",
            "Unsupported-memory No-op Rate",
            "G10|G11",
            metrics["Unsupported-memory No-op Rate"]["value"] == 1.0,
        ),
        (
            "CR-PERS-007",
            "Personalization is bounded and does not unconditionally override stronger Basic relevance.",
            "G12 Bounded Personalization Pass",
            "G12",
            metrics["G12 Bounded Personalization Pass"]["value"] == 1.0,
        ),
    )
    rows = [
        {
            "claim_id": claim_id,
            "claim": claim,
            "metric": metric,
            "metric_result": metrics[metric]["value"],
            "run_id": run_id,
            "evidence_case_ids": evidence,
            "mechanical_pass": str(passed).lower(),
            "status": "MEASURED",
        }
        for claim_id, claim, metric, evidence, passed in definitions
    ]
    rows.append(
        {
            "claim_id": "CR-PERS-REAL-001",
            "claim": "Personal RAG improves real adolescents' health behavior.",
            "metric": "not_measured",
            "metric_result": "not_measured",
            "run_id": run_id,
            "evidence_case_ids": "",
            "mechanical_pass": "false",
            "status": "UNSUPPORTED",
        }
    )
    return rows


def _cleanup_evaluation_records(
    client, results: list[dict[str, Any]]
) -> dict[str, Any]:
    failures = []
    for result in results:
        for memory_id in result.get("memory_ids", []):
            cleanup = user_memory.forget_memory(
                client, result["eval_user_id"], memory_id
            )
            if cleanup["status"] not in {"forgotten", "not_found"}:
                failures.append({"memory_id": memory_id, "result": cleanup})
        try:
            client.delete(
                index=user_memory.USER_PROFILE_INDEX,
                id=result["eval_user_id"],
                refresh="wait_for",
            )
        except Exception as exc:  # noqa: BLE001 - cleanup failure must preserve results
            failures.append(
                {"eval_user_id": result["eval_user_id"], "error": str(exc)}
            )
    return {"completed": not failures, "failures": failures}


def run_evaluation(
    *,
    client,
    api_key: str,
    gold_path: Path = DEFAULT_GOLD_PATH,
    baseline_path: Path = DEFAULT_BASELINE_PATH,
    scenario_path: Path = DEFAULT_SCENARIO_PATH,
    task_path: Path = DEFAULT_TASK_PATH,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    claim_path: Path = DEFAULT_CLAIM_PATH,
    run_id: str | None = None,
) -> Path:
    created_at = datetime.now(UTC)
    run_id = run_id or created_at.strftime("%Y%m%dT%H%M%SZ_personal_rag_gold_v1")
    baseline_sha_before = file_sha256(baseline_path)
    scenario_sha_before = file_sha256(scenario_path)
    if scenario_sha_before != BASELINE_DATASET_SHA256:
        raise RuntimeError("Frozen baseline dataset SHA-256 mismatch")
    baseline = load_baseline(baseline_path)
    gold, gold_sha_before = load_gold(gold_path, baseline)
    scenarios = {row["case_id"]: row for row in _read_jsonl(scenario_path)}
    valid_task_ids = {row["task_id"] for row in _read_jsonl(task_path)}
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    results = []
    with MemoryModelCallCounter() as counter:
        for case in gold:
            before = counter.snapshot()
            eval_user = evaluation_user_id(case["gold_case_id"], run_id)
            result = execute_gold_case(
                case,
                scenarios[case["source_scenario_id"]],
                baseline[case["source_scenario_id"]],
                eval_user_id=eval_user,
                client=client,
                api_key=api_key,
                valid_task_ids=valid_task_ids,
            )
            result["model_call_counts"] = _counter_delta(before, counter.snapshot())
            results.append(result)
        total_model_calls = counter.snapshot()

    assert_file_hash_unchanged(gold_path, gold_sha_before, "Gold dataset")
    assert_file_hash_unchanged(baseline_path, baseline_sha_before, "Frozen baseline results")

    metrics = calculate_metrics(results, run_id)
    config = {
        "dataset_version": DATASET_VERSION,
        "baseline_run_id": BASELINE_RUN_ID,
        "baseline_results_path": baseline_path.as_posix(),
        "task_retrieval": "off",
        "task_reranker": "off",
        "qwen_plus": "off",
        "memory_retrieval": "production",
        "personalization": "production",
    }
    provenance = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "git_commit": _git_commit(),
        "source_tree_sha256": _hash_files(RELEVANT_PRODUCTION_SOURCES),
        "gold_dataset_sha256": gold_sha_before,
        "baseline_results_sha256": baseline_sha_before,
        "runner_sha256": file_sha256(Path(__file__)),
        "uv_lock_sha256": file_sha256(Path("uv.lock")),
        "python_version": platform.python_version(),
        "dataset_version": DATASET_VERSION,
        "baseline_run_id": BASELINE_RUN_ID,
        "baseline_dataset_sha256": scenario_sha_before,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dim": EMBEDDING_DIMENSION,
        "memory_reranker_model": RERANK_MODEL,
        "personalization_weights": {
            "prefer_task": 3,
            "avoid_task": -3,
            "helpfulness_gte_4": 2,
            "completed": 1,
            "easy": 1,
            "helpfulness_lte_2": -2,
            "skipped": -1,
            "hard": -1,
        },
        "personalization_clamp": [-5, 5],
        "tie_break_contract": ["adjusted_rank ASC", "base_rank ASC", "task_id ASC"],
        "model_call_counts": total_model_calls,
        "gold_modified_after_personal_results_seen": False,
        "baseline_modified": False,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (run_dir / "per_case_results.jsonl").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_metrics_csv(run_dir / "metrics.csv", metrics)
    _write_csv(
        run_dir / "paper_metrics.csv",
        _paper_rows(metrics, run_id),
        ("experiment", "metric", "method", "value", "n", "provenance_level", "run_id"),
    )
    _write_csv(
        claim_path,
        _claim_rows(metrics, run_id),
        (
            "claim_id",
            "claim",
            "metric",
            "metric_result",
            "run_id",
            "evidence_case_ids",
            "mechanical_pass",
            "status",
        ),
    )

    cleanup = _cleanup_evaluation_records(client, results)
    provenance["cleanup"] = cleanup
    (run_dir / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    env_file = Path(".env")
    api_key = load_api_key(env_file)
    es_url = _env_value("ELASTICSEARCH_URL", env_file) or "http://127.0.0.1:9200"
    client = Elasticsearch(es_url, request_timeout=30)
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
