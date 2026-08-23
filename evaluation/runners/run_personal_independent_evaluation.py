"""Run the preregistered Stage 6C independent synthetic preference benchmark."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import random
import re
import shutil
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch
from pydantic import ValidationError

from evaluation.runners.run_personal_gold_evaluation import (
    MemoryModelCallCounter,
    assert_file_hash_unchanged,
    build_memory_candidate,
    file_sha256,
    personalize_frozen_candidates,
)
from evaluation.runners.run_personal_screening import SAFETY_INPUT_FIELDS, screen_case
from weilv import personal_memory_retrieval, user_memory
from weilv.api.schemas import RecommendationRequest
from weilv.dashscope_models import EMBEDDING_DIMENSION, EMBEDDING_MODEL, RERANK_MODEL
from weilv.retrieval_slice import _env_value, load_api_key

PROFILE_VERSION = "personal_rag_users_v1"
SCENARIO_VERSION = "personal_rag_independent_scenarios_v1"
MATRIX_VERSION = "personal_rag_independent_matrix_v1"
MANIFEST_VERSION = "personal_rag_independent_v1"
DEFAULT_PROFILE_PATH = Path("evaluation/datasets/personal_rag_users_v1.jsonl")
DEFAULT_SCENARIO_PATH = Path(
    "evaluation/datasets/personal_rag_independent_scenarios_v1.jsonl"
)
DEFAULT_MATRIX_PATH = Path("evaluation/datasets/personal_rag_independent_matrix_v1.jsonl")
DEFAULT_MANIFEST_PATH = Path("evaluation/manifests/personal_rag_independent_v1.json")
DEFAULT_TASK_PATH = Path("data/metadata/micro_tasks_v1.jsonl")
DEFAULT_OUTPUT_ROOT = Path("evaluation/runs")
DEFAULT_CLAIM_PATH = Path(
    "evaluation/claims/claim_registry_personal_independent_v1.csv"
)
RELEVANT_PRODUCTION_SOURCES = (
    Path("src/weilv/basic_rag.py"),
    Path("src/weilv/safety_rules.py"),
    Path("src/weilv/retrieval.py"),
    Path("src/weilv/dashscope_models.py"),
    Path("src/weilv/user_memory.py"),
    Path("src/weilv/personal_memory_retrieval.py"),
    Path("src/weilv/personal_rag.py"),
)
CALL_KEYS = (
    "task_embedding",
    "task_reranker",
    "memory_document_embedding",
    "memory_query_embedding",
    "memory_reranker",
    "qwen_plus",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def false_safety_inputs() -> dict[str, bool]:
    return dict.fromkeys(SAFETY_INPUT_FIELDS, False)


def load_profiles(path: Path, valid_task_ids: set[str]) -> list[dict[str, Any]]:
    profiles = _read_jsonl(path)
    if [row.get("profile_id") for row in profiles] != [f"P0{i}" for i in range(1, 7)]:
        raise ValueError("profiles must be ordered unique P01 through P06")
    for row in profiles:
        if row.get("dataset_version") != PROFILE_VERSION or row.get("provenance_level") != "C":
            raise ValueError(f"invalid profile dataset contract for {row.get('profile_id')}")
        if row.get("memory_enabled") is not True or len(row.get("memories", [])) != 2:
            raise ValueError(f"profile must have exactly two enabled memories: {row['profile_id']}")
        roles = {memory.get("preference_role") for memory in row["memories"]}
        if roles != {"preferred", "avoided"}:
            raise ValueError(f"profile preference roles invalid: {row['profile_id']}")
        profile = user_memory.UserProfile(
            row["profile_id"], row["target_stage"], True, "now", "now"
        )
        for payload in row["memories"]:
            candidate = build_memory_candidate(payload, profile.user_id, "now")
            validation = user_memory.validate_memory_candidate(
                profile, candidate, valid_task_ids
            )
            if not validation["valid"]:
                raise ValueError(
                    f"invalid task_preference for {row['profile_id']}: "
                    f"{validation['reason_codes']}"
                )
    return profiles


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    scenarios = _read_jsonl(path)
    if [row.get("scenario_id") for row in scenarios] != [f"S0{i}" for i in range(1, 9)]:
        raise ValueError("scenarios must be ordered unique S01 through S08")
    for row in scenarios:
        if row.get("dataset_version") != SCENARIO_VERSION or row.get("provenance_level") != "C":
            raise ValueError(f"invalid scenario dataset contract for {row.get('scenario_id')}")
        safety = row.get("safety_inputs")
        if set(safety or {}) != set(SAFETY_INPUT_FIELDS) or any(
            type(value) is not bool for value in (safety or {}).values()
        ):
            raise ValueError(f"invalid safety_inputs for {row['scenario_id']}")
        try:
            RecommendationRequest(
                user_id=f"evaluation:{row['scenario_id']}",
                query=row["query"],
                target_stage=row["target_stage"],
                current_context=row["current_context"],
                activity_context=row["activity_context"],
                available_minutes=row["available_minutes"],
                **safety,
            )
        except ValidationError as exc:
            raise ValueError(f"invalid formal scenario {row['scenario_id']}: {exc}") from exc
    return scenarios


def load_matrix(
    path: Path,
    profiles: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matrix = _read_jsonl(path)
    expected_pairs = [
        *[(f"P0{profile}", f"S0{scenario}") for profile in range(1, 6) for scenario in range(1, 5)],
        *[("P06", f"S0{scenario}") for scenario in range(5, 9)],
    ]
    actual_pairs = [(row.get("profile_id"), row.get("scenario_id")) for row in matrix]
    if actual_pairs != expected_pairs or len({row.get("case_id") for row in matrix}) != 24:
        raise ValueError("benchmark matrix must contain the frozen 24 cases")
    profile_map = {row["profile_id"]: row for row in profiles}
    scenario_ids = {row["scenario_id"] for row in scenarios}
    for row in matrix:
        if row.get("dataset_version") != MATRIX_VERSION or row.get("provenance_level") != "C":
            raise ValueError(f"invalid matrix contract for {row.get('case_id')}")
        if row["scenario_id"] not in scenario_ids:
            raise ValueError(f"unknown scenario for {row['case_id']}")
        memories = {
            item["preference_role"]: item["task_id"]
            for item in profile_map[row["profile_id"]]["memories"]
        }
        if row["preferred_task_id"] != memories["preferred"] or row[
            "avoided_task_id"
        ] != memories["avoided"]:
            raise ValueError(f"matrix preference Gold mismatch for {row['case_id']}")
    return matrix


def load_manifest(
    path: Path,
    *,
    profile_path: Path,
    scenario_path: Path,
    matrix_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError("unsupported preregistration manifest")
    if manifest.get("preregistered_before_basic_run") is not True:
        raise RuntimeError("benchmark was not preregistered before Basic run")
    expected = {
        "profile_dataset_sha256": file_sha256(profile_path),
        "scenario_dataset_sha256": file_sha256(scenario_path),
        "benchmark_matrix_sha256": file_sha256(matrix_path),
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            raise RuntimeError(f"preregistration hash mismatch: {field}")
    return manifest


def evaluation_user_id(profile_id: str, run_id: str) -> str:
    safe_run_id = re.sub(r"[^a-z0-9]+", "_", run_id.lower()).strip("_")
    return f"eval_ind_{profile_id.lower()}_{safe_run_id}"


def profile_case_groups(matrix: list[dict[str, Any]]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for row in matrix:
        groups.setdefault(row["profile_id"], []).append(row["case_id"])
    return groups


def run_basic_scenarios(
    scenarios: list[dict[str, Any]],
    *,
    client,
    api_key: str,
    screen_case_fn=screen_case,
) -> dict[str, dict[str, Any]]:
    results = {}
    for scenario in scenarios:
        adapted = {
            **scenario,
            "case_id": scenario["scenario_id"],
            "archetype_id": "IND-BASIC",
        }
        measured = screen_case_fn(adapted, client, api_key)
        results[scenario["scenario_id"]] = {
            "scenario_id": scenario["scenario_id"],
            "status": measured["status"],
            "base_candidate_ids": measured["eligible_task_ids"],
            "base_ranking": measured["candidate_ranking"],
            "base_top1": measured["selected_task_id"],
            "filtered_task_ids": measured["filtered_task_ids"],
            "filter_reason_codes": measured["filter_reason_codes"],
            "matched_rule_ids": measured["matched_rule_ids"],
            "latency_ms": measured["latency_ms"],
            "model_call_counts": measured["model_call_counts"],
        }
    return results


def _utility(top1: str | None, preferred: str, avoided: str) -> int:
    if top1 == preferred:
        return 1
    if top1 == avoided:
        return -1
    return 0


def _prepare_profile_memories(
    profiles: list[dict[str, Any]],
    *,
    run_id: str,
    client,
    api_key: str,
    valid_task_ids: set[str],
) -> dict[str, dict[str, Any]]:
    states = {}
    now = datetime.now(UTC).isoformat()
    for row in profiles:
        eval_user = evaluation_user_id(row["profile_id"], run_id)
        profile = user_memory.UserProfile(
            eval_user, row["target_stage"], True, now, now
        )
        user_memory.upsert_user_profile(client, profile)
        role_memory_ids = {}
        all_memory_ids = []
        for payload in row["memories"]:
            candidate = build_memory_candidate(payload, eval_user, now)
            created = user_memory.create_memory(client, profile, candidate, valid_task_ids)
            if created["status"] != "created":
                raise RuntimeError(f"memory creation failed for {row['profile_id']}: {created}")
            memory_id = created["memory_id"]
            embedded = personal_memory_retrieval.embed_memory(
                client, eval_user, memory_id, api_key
            )
            if embedded["status"] != "embedded":
                raise RuntimeError(f"memory embedding failed for {row['profile_id']}")
            role_memory_ids[payload["preference_role"]] = memory_id
            all_memory_ids.append(memory_id)
        states[row["profile_id"]] = {
            "eval_user_id": eval_user,
            "profile": profile,
            "memory_ids": all_memory_ids,
            "role_memory_ids": role_memory_ids,
        }
    return states


def _execute_personal_case(
    case: dict[str, Any],
    scenario: dict[str, Any],
    baseline: dict[str, Any],
    profile_state: dict[str, Any],
    *,
    client,
    api_key: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    retrieved = personal_memory_retrieval.retrieve_personal_memories(
        client, profile_state["profile"], scenario["query"], api_key
    )
    retrieved_ids = [memory["memory_id"] for memory in retrieved]
    personal = personalize_frozen_candidates(baseline["base_ranking"], retrieved)
    base_order = [item["task_id"] for item in baseline["base_ranking"]]
    personal_order = [item["task_id"] for item in personal]
    if len(base_order) != len(personal_order) or set(base_order) != set(personal_order):
        raise RuntimeError("candidate set changed during personalization")
    base_ranks = {item["task_id"]: item["base_rank"] for item in baseline["base_ranking"]}
    personal_ranks = {item["task_id"]: item["personal_rank"] for item in personal}
    preferred = case["preferred_task_id"]
    avoided = case["avoided_task_id"]
    preferred_available = preferred in base_ranks
    avoided_available = avoided in base_ranks
    base_top1 = baseline["base_top1"]
    personal_top1 = personal_order[0] if personal_order else None
    basic_utility = _utility(base_top1, preferred, avoided)
    personal_utility = _utility(personal_top1, preferred, avoided)
    role_ids = profile_state["role_memory_ids"]
    return {
        "case_id": case["case_id"],
        "profile_id": case["profile_id"],
        "scenario_id": case["scenario_id"],
        "eval_user_id": profile_state["eval_user_id"],
        "preferred_task_id": preferred,
        "avoided_task_id": avoided,
        "base_candidate_ids": baseline["base_candidate_ids"],
        "base_ranking": baseline["base_ranking"],
        "base_top1": base_top1,
        "preferred_available": preferred_available,
        "avoided_available": avoided_available,
        "base_preferred_rank": base_ranks.get(preferred),
        "base_avoided_rank": base_ranks.get(avoided),
        "retrieved_memory_ids": retrieved_ids,
        "retrieved_memory_types": [memory["memory_type"] for memory in retrieved],
        "memory_retrieval_hit": bool(retrieved_ids),
        "any_memory_hit": bool(retrieved_ids),
        "preferred_memory_retrieval_hit": role_ids["preferred"] in retrieved_ids,
        "avoided_memory_retrieval_hit": role_ids["avoided"] in retrieved_ids,
        "personalization_delta_by_task": {
            item["task_id"]: item["personalization_delta"] for item in personal
        },
        "personal_ranking": personal,
        "personal_top1": personal_top1,
        "personal_preferred_rank": personal_ranks.get(preferred),
        "personal_avoided_rank": personal_ranks.get(avoided),
        "candidate_set_unchanged": set(base_order) == set(personal_order)
        and len(base_order) == len(personal_order),
        "ranking_unchanged": base_order == personal_order,
        "basic_preference_utility": basic_utility,
        "personal_preference_utility": personal_utility,
        "utility_delta": personal_utility - basic_utility,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "model_call_counts": dict.fromkeys(CALL_KEYS, 0),
    }


def _metric(
    name: str,
    numerator: float,
    denominator: int,
    value: Any,
    case_ids: list[str],
    run_id: str,
) -> dict[str, Any]:
    return {
        "metric_name": name,
        "numerator": numerator,
        "denominator": denominator,
        "value": value,
        "applicable_case_ids": case_ids,
        "run_id": run_id,
    }


def _rate(
    name: str, rows: list[dict[str, Any]], predicate, run_id: str
) -> dict[str, Any]:
    numerator = sum(bool(predicate(row)) for row in rows)
    return _metric(
        name,
        numerator,
        len(rows),
        numerator / len(rows) if rows else "not_measured",
        [row["case_id"] for row in rows],
        run_id,
    )


def _mean_metric(
    name: str, rows: list[dict[str, Any]], value_fn, run_id: str
) -> dict[str, Any]:
    values = [value_fn(row) for row in rows]
    return _metric(
        name,
        sum(values),
        len(values),
        statistics.mean(values) if values else "not_measured",
        [row["case_id"] for row in rows],
        run_id,
    )


def _cluster_bootstrap_ci(
    profile_rows: list[dict[str, Any]], seed: int = 20260816, resamples: int = 10000
) -> list[float] | str:
    if not profile_rows:
        return "not_measured"
    rng = random.Random(seed)
    improvements = [row["utility_improvement"] for row in profile_rows]
    samples = sorted(
        statistics.mean(rng.choices(improvements, k=len(improvements)))
        for _ in range(resamples)
    )
    return [samples[int(0.025 * (resamples - 1))], samples[int(0.975 * (resamples - 1))]]


def calculate_metrics(
    results: list[dict[str, Any]], run_id: str
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    all_rows = list(results)
    preferred_rows = [row for row in all_rows if row["preferred_available"]]
    avoided_rows = [row for row in all_rows if row["avoided_available"]]
    out_of_pool = [
        row
        for row in all_rows
        if not row["preferred_available"] and not row["avoided_available"]
    ]
    metrics = {
        "Mean Basic Preference Utility@1": _mean_metric(
            "Mean Basic Preference Utility@1",
            all_rows,
            lambda row: row["basic_preference_utility"],
            run_id,
        ),
        "Mean Personal Preference Utility@1": _mean_metric(
            "Mean Personal Preference Utility@1",
            all_rows,
            lambda row: row["personal_preference_utility"],
            run_id,
        ),
        "Mean Utility Improvement": _mean_metric(
            "Mean Utility Improvement", all_rows, lambda row: row["utility_delta"], run_id
        ),
    }
    comparisons = {
        "Personal Wins": lambda row: row["utility_delta"] > 0,
        "Ties": lambda row: row["utility_delta"] == 0,
        "Personal Losses": lambda row: row["utility_delta"] < 0,
    }
    for name, predicate in comparisons.items():
        count = sum(predicate(row) for row in all_rows)
        metrics[name] = _metric(name, count, len(all_rows), count, [row["case_id"] for row in all_rows], run_id)
    metrics["Win Rate"] = _rate("Win Rate", all_rows, comparisons["Personal Wins"], run_id)
    metrics["Loss Rate"] = _rate("Loss Rate", all_rows, comparisons["Personal Losses"], run_id)
    metrics["Preferred Task Availability Rate"] = _rate(
        "Preferred Task Availability Rate", all_rows, lambda row: row["preferred_available"], run_id
    )
    metrics["Basic Preferred Top1 Rate"] = _rate(
        "Basic Preferred Top1 Rate",
        preferred_rows,
        lambda row: row["base_top1"] == row["preferred_task_id"],
        run_id,
    )
    metrics["Personal Preferred Top1 Rate"] = _rate(
        "Personal Preferred Top1 Rate",
        preferred_rows,
        lambda row: row["personal_top1"] == row["preferred_task_id"],
        run_id,
    )
    metrics["Basic Avoided Top1 Rate"] = _rate(
        "Basic Avoided Top1 Rate",
        avoided_rows,
        lambda row: row["base_top1"] == row["avoided_task_id"],
        run_id,
    )
    metrics["Personal Avoided Top1 Rate"] = _rate(
        "Personal Avoided Top1 Rate",
        avoided_rows,
        lambda row: row["personal_top1"] == row["avoided_task_id"],
        run_id,
    )
    for name, rows, fn in (
        ("Mean Preferred Rank — Basic", preferred_rows, lambda row: row["base_preferred_rank"]),
        ("Mean Preferred Rank — Personal", preferred_rows, lambda row: row["personal_preferred_rank"]),
        (
            "Mean Preferred Rank Gain",
            preferred_rows,
            lambda row: row["base_preferred_rank"] - row["personal_preferred_rank"],
        ),
        ("Mean Avoided Rank — Basic", avoided_rows, lambda row: row["base_avoided_rank"]),
        ("Mean Avoided Rank — Personal", avoided_rows, lambda row: row["personal_avoided_rank"]),
        (
            "Mean Avoided Rank Demotion",
            avoided_rows,
            lambda row: row["personal_avoided_rank"] - row["base_avoided_rank"],
        ),
    ):
        metrics[name] = _mean_metric(name, rows, fn, run_id)
    metrics["Out-of-pool Memory No-op Rate"] = _rate(
        "Out-of-pool Memory No-op Rate", out_of_pool, lambda row: row["ranking_unchanged"], run_id
    )
    for name, field in (
        ("Candidate-set Invariance Rate", "candidate_set_unchanged"),
        ("Any Profile Memory Hit Rate", "any_memory_hit"),
        ("Preferred Memory Retrieval Hit Rate", "preferred_memory_retrieval_hit"),
        ("Avoided Memory Retrieval Hit Rate", "avoided_memory_retrieval_hit"),
    ):
        metrics[name] = _rate(name, all_rows, lambda row, key=field: row[key], run_id)

    profile_rows = []
    for profile_id in sorted({row["profile_id"] for row in all_rows}):
        rows = [row for row in all_rows if row["profile_id"] == profile_id]
        basic = statistics.mean(row["basic_preference_utility"] for row in rows)
        personal = statistics.mean(row["personal_preference_utility"] for row in rows)
        profile_rows.append(
            {
                "profile_id": profile_id,
                "basic_mean_utility": basic,
                "personal_mean_utility": personal,
                "utility_improvement": personal - basic,
                "wins": sum(row["utility_delta"] > 0 for row in rows),
                "ties": sum(row["utility_delta"] == 0 for row in rows),
                "losses": sum(row["utility_delta"] < 0 for row in rows),
                "run_id": run_id,
            }
        )
    metrics["Macro-average Profile Utility Improvement"] = _metric(
        "Macro-average Profile Utility Improvement",
        sum(row["utility_improvement"] for row in profile_rows),
        len(profile_rows),
        statistics.mean(row["utility_improvement"] for row in profile_rows),
        [row["profile_id"] for row in profile_rows],
        run_id,
    )
    ci = _cluster_bootstrap_ci(profile_rows)
    metrics["Mean Utility Improvement 95% CI"] = _metric(
        "Mean Utility Improvement 95% CI", 0, len(profile_rows), ci, [row["profile_id"] for row in profile_rows], run_id
    )
    return metrics, profile_rows


def _hash_files(paths: tuple[Path, ...]) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(path.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unavailable:not-a-git-worktree"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _metrics_csv_rows(metrics: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for metric in metrics.values():
        row = dict(metric)
        row["applicable_case_ids"] = "|".join(row["applicable_case_ids"])
        if isinstance(row["value"], list):
            row["value"] = json.dumps(row["value"])
        rows.append(row)
    return rows


def _paper_rows(metrics: dict[str, dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    mapping = (
        ("Mean Basic Preference Utility@1", "preference_utility_at_1", "Basic RAG"),
        ("Mean Personal Preference Utility@1", "preference_utility_at_1", "Personal RAG"),
        ("Basic Preferred Top1 Rate", "preferred_top1_rate", "Basic RAG"),
        ("Personal Preferred Top1 Rate", "preferred_top1_rate", "Personal RAG"),
        ("Basic Avoided Top1 Rate", "avoided_top1_rate", "Basic RAG"),
        ("Personal Avoided Top1 Rate", "avoided_top1_rate", "Personal RAG"),
        ("Mean Preferred Rank — Basic", "mean_preferred_rank", "Basic RAG"),
        ("Mean Preferred Rank — Personal", "mean_preferred_rank", "Personal RAG"),
        ("Mean Avoided Rank — Basic", "mean_avoided_rank", "Basic RAG"),
        ("Mean Avoided Rank — Personal", "mean_avoided_rank", "Personal RAG"),
        ("Candidate-set Invariance Rate", "candidate_set_invariance", "Personal RAG"),
    )
    return [
        {
            "experiment": "independent_personalization",
            "metric": metric_name,
            "method": method,
            "value": metrics[source]["value"],
            "n": metrics[source]["denominator"],
            "provenance_level": "A+C",
            "run_id": run_id,
        }
        for source, metric_name, method in mapping
    ]


def _claim_rows(
    metrics: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
    run_id: str,
) -> list[dict[str, Any]]:
    supported = (
        metrics["Mean Utility Improvement"]["value"]
        > manifest["claim_support_rule"]["mean_utility_improvement_gt"]
        and metrics["Personal Preferred Top1 Rate"]["value"]
        > metrics["Basic Preferred Top1 Rate"]["value"]
        and metrics["Personal Wins"]["value"] > metrics["Personal Losses"]["value"]
    )
    return [
        {
            "claim_id": "CR-PERS-IND-001",
            "claim": "On a preregistered synthetic-user benchmark whose user preferences and scenarios were frozen before observing Basic or Personal rankings, Personal RAG improves preference alignment relative to Basic RAG.",
            "status": (
                "SUPPORTED_IN_SYNTHETIC_BENCHMARK" if supported else "NOT_SUPPORTED"
            ),
            "run_id": run_id,
            "mean_basic_preference_utility_at_1": metrics[
                "Mean Basic Preference Utility@1"
            ]["value"],
            "mean_personal_preference_utility_at_1": metrics[
                "Mean Personal Preference Utility@1"
            ]["value"],
            "basic_preferred_top1_rate": metrics["Basic Preferred Top1 Rate"]["value"],
            "personal_preferred_top1_rate": metrics["Personal Preferred Top1 Rate"]["value"],
            "wins": metrics["Personal Wins"]["value"],
            "ties": metrics["Ties"]["value"],
            "losses": metrics["Personal Losses"]["value"],
            "profile_dataset_sha256": manifest["profile_dataset_sha256"],
            "scenario_dataset_sha256": manifest["scenario_dataset_sha256"],
            "benchmark_matrix_sha256": manifest["benchmark_matrix_sha256"],
        },
        {
            "claim_id": "CR-PERS-REAL-001",
            "claim": "Personal RAG improves real adolescents' health behavior or real-user satisfaction.",
            "status": "UNSUPPORTED",
            "run_id": run_id,
            "mean_basic_preference_utility_at_1": "not_measured",
            "mean_personal_preference_utility_at_1": "not_measured",
            "basic_preferred_top1_rate": "not_measured",
            "personal_preferred_top1_rate": "not_measured",
            "wins": "not_measured",
            "ties": "not_measured",
            "losses": "not_measured",
            "profile_dataset_sha256": manifest["profile_dataset_sha256"],
            "scenario_dataset_sha256": manifest["scenario_dataset_sha256"],
            "benchmark_matrix_sha256": manifest["benchmark_matrix_sha256"],
        },
    ]


def _cleanup(client, states: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failures = []
    for state in states.values():
        for memory_id in state["memory_ids"]:
            result = user_memory.forget_memory(client, state["eval_user_id"], memory_id)
            if result["status"] not in {"forgotten", "not_found"}:
                failures.append(result)
        try:
            client.delete(
                index=user_memory.USER_PROFILE_INDEX,
                id=state["eval_user_id"],
                refresh="wait_for",
            )
        except Exception as exc:  # noqa: BLE001 - results must survive cleanup failure
            failures.append({"eval_user_id": state["eval_user_id"], "error": str(exc)})
    return {"completed": not failures, "failures": failures}


def run_evaluation(
    *,
    client,
    api_key: str,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    scenario_path: Path = DEFAULT_SCENARIO_PATH,
    matrix_path: Path = DEFAULT_MATRIX_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    task_path: Path = DEFAULT_TASK_PATH,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    claim_path: Path = DEFAULT_CLAIM_PATH,
    run_id: str | None = None,
) -> Path:
    created_at = datetime.now(UTC)
    run_id = run_id or created_at.strftime("%Y%m%dT%H%M%SZ_personal_rag_independent_v1")
    valid_task_ids = {row["task_id"] for row in _read_jsonl(task_path)}
    profiles = load_profiles(profile_path, valid_task_ids)
    scenarios = load_scenarios(scenario_path)
    matrix = load_matrix(matrix_path, profiles, scenarios)
    manifest = load_manifest(
        manifest_path,
        profile_path=profile_path,
        scenario_path=scenario_path,
        matrix_path=matrix_path,
    )
    frozen_hashes = {
        profile_path: manifest["profile_dataset_sha256"],
        scenario_path: manifest["scenario_dataset_sha256"],
        matrix_path: manifest["benchmark_matrix_sha256"],
        manifest_path: file_sha256(manifest_path),
    }
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(manifest_path, run_dir / "preregistration_manifest.json")

    basic_started_at = datetime.now(UTC).isoformat()
    basic = run_basic_scenarios(scenarios, client=client, api_key=api_key)
    basic_rows = list(basic.values())
    task_calls = {
        "task_embedding": sum(
            row["model_call_counts"]["text_embedding_v4"] for row in basic_rows
        ),
        "task_reranker": sum(
            row["model_call_counts"]["qwen3_rerank"] for row in basic_rows
        ),
        "qwen_plus": sum(row["model_call_counts"]["qwen_plus"] for row in basic_rows),
    }

    results = []
    with MemoryModelCallCounter() as counter:
        states = _prepare_profile_memories(
            profiles,
            run_id=run_id,
            client=client,
            api_key=api_key,
            valid_task_ids=valid_task_ids,
        )
        scenario_map = {row["scenario_id"]: row for row in scenarios}
        for case in matrix:
            before = counter.snapshot()
            result = _execute_personal_case(
                case,
                scenario_map[case["scenario_id"]],
                basic[case["scenario_id"]],
                states[case["profile_id"]],
                client=client,
                api_key=api_key,
            )
            after = counter.snapshot()
            result["model_call_counts"] = {
                "task_embedding": 0,
                "task_reranker": 0,
                "memory_document_embedding": 0,
                "memory_query_embedding": after["memory_query_embedding"]
                - before["memory_query_embedding"],
                "memory_reranker": after["memory_reranker"] - before["memory_reranker"],
                "qwen_plus": 0,
            }
            results.append(result)
        memory_calls = counter.snapshot()

    for path, frozen_hash in frozen_hashes.items():
        assert_file_hash_unchanged(path, frozen_hash, path.as_posix())
    metrics, profile_metrics = calculate_metrics(results, run_id)
    model_calls = {
        **task_calls,
        "memory_document_embedding": memory_calls["memory_document_embedding"],
        "memory_query_embedding": memory_calls["memory_query_embedding"],
        "memory_reranker": memory_calls["memory_reranker"],
    }
    config = {
        "experiment": MANIFEST_VERSION,
        "profiles": 6,
        "scenarios": 8,
        "cases": 24,
        "profile_target_stage_adapter": "junior_high_fixed; not used by memory ranking",
        "cluster_bootstrap": {"seed": 20260816, "resamples": 10000},
        "qwen_plus": "off",
    }
    provenance = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "basic_run_started_at": basic_started_at,
        "profile_dataset_sha256": manifest["profile_dataset_sha256"],
        "scenario_dataset_sha256": manifest["scenario_dataset_sha256"],
        "benchmark_matrix_sha256": manifest["benchmark_matrix_sha256"],
        "preregistration_manifest_sha256": frozen_hashes[manifest_path],
        "source_tree_sha256": _hash_files(RELEVANT_PRODUCTION_SOURCES),
        "runner_sha256": file_sha256(Path(__file__)),
        "uv_lock_sha256": file_sha256(Path("uv.lock")),
        "git_commit": _git_commit(),
        "python_version": platform.python_version(),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dim": EMBEDDING_DIMENSION,
        "task_reranker_model": RERANK_MODEL,
        "memory_reranker_model": RERANK_MODEL,
        "personalization_weights": {"prefer_task": 3, "avoid_task": -3},
        "personalization_clamp": [-5, 5],
        "tie_break_contract": ["adjusted_rank ASC", "base_rank ASC", "task_id ASC"],
        "profiles_modified_after_basic_seen": False,
        "scenarios_modified_after_basic_seen": False,
        "gold_modified_after_basic_seen": False,
        "gold_modified_after_personal_seen": False,
        "model_call_counts": model_calls,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_jsonl(run_dir / "basic_scenario_results.jsonl", basic_rows)
    _write_jsonl(run_dir / "per_case_results.jsonl", results)
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    metric_fields = (
        "metric_name",
        "numerator",
        "denominator",
        "value",
        "applicable_case_ids",
        "run_id",
    )
    _write_csv(run_dir / "metrics.csv", _metrics_csv_rows(metrics), metric_fields)
    _write_csv(
        run_dir / "profile_metrics.csv",
        profile_metrics,
        (
            "profile_id",
            "basic_mean_utility",
            "personal_mean_utility",
            "utility_improvement",
            "wins",
            "ties",
            "losses",
            "run_id",
        ),
    )
    _write_csv(
        run_dir / "paper_metrics.csv",
        _paper_rows(metrics, run_id),
        ("experiment", "metric", "method", "value", "n", "provenance_level", "run_id"),
    )
    claim_fields = (
        "claim_id",
        "claim",
        "status",
        "run_id",
        "mean_basic_preference_utility_at_1",
        "mean_personal_preference_utility_at_1",
        "basic_preferred_top1_rate",
        "personal_preferred_top1_rate",
        "wins",
        "ties",
        "losses",
        "profile_dataset_sha256",
        "scenario_dataset_sha256",
        "benchmark_matrix_sha256",
    )
    _write_csv(claim_path, _claim_rows(metrics, manifest, run_id), claim_fields)

    cleanup = _cleanup(client, states)
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
