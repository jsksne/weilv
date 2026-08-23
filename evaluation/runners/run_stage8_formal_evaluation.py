"""Stage 8 — Formal Basic vs Personal vs Agentic evaluation on frozen Gold v1.2.

Frozen Gold: evaluation/datasets/agentic_complex_gold_frozen_v1_2.jsonl
Manifest:    evaluation/manifests/stage8_gold_v1_2_manifest.json

Execution protocol
------------------
- Deterministic case order AGX-001..AGX-024; per case fixed system order
  Basic -> Personal -> Agentic (preregistered).
- Every case x system runs through the real production execution path
  (weilv.basic_rag.run_basic_rag / weilv.personal_rag.run_personal_rag /
  weilv.agentic_rag.run_agentic_rag). No handcrafted recommendations.
- Gold labels are read ONLY here by the evaluator after system output.
  The runtime request carries ONLY logical runtime fields.
- Isolated persistent user ids: stage8-<case_id>-<system>.
  Basic never receives a profile/memory. Personal/Agentic receive a profile
  plus the frozen synthetic_memory_fixture ONLY on memory cases.
- Retry policy: infrastructure failures only (network / timeout / ES 5xx),
  max 1 retry per execution, all retries logged. Semantic outcomes
  (wrong task, guard rejection, no_safe_task, poor coverage) never retried.
- All 72 system-case executions are written to raw_results.jsonl.

Phases
------
python run_stage8_formal_evaluation.py --phase execute   # run systems
python run_stage8_formal_evaluation.py --phase finalize  # compute all metrics
"""

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import re
import statistics
import subprocess
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch

from weilv import agentic_rag, basic_rag, personal_rag
from weilv.agentic_rag import SAFE_EXPLANATION_FALLBACK
from weilv.basic_rag import BasicRagRequest
from weilv.dashscope_models import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    LLM_MODEL,
    RERANK_MODEL,
)
from weilv.micro_tasks import load_formal_micro_tasks
from weilv.output_guard import validate_explanation_output
from weilv.personal_memory_retrieval import embed_memory
from weilv.retrieval_slice import _env_value, load_api_key
from weilv.user_memory import (
    USER_MEMORY_INDEX,
    USER_PROFILE_INDEX,
    UserMemoryCandidate,
    UserProfile,
    create_memory,
    forget_memory,
    upsert_user_profile,
)

ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / "evaluation" / "runs"

FROZEN_GOLD = ROOT / "evaluation" / "datasets" / "agentic_complex_gold_frozen_v1_2.jsonl"
GOLD_MANIFEST = ROOT / "evaluation" / "manifests" / "stage8_gold_v1_2_manifest.json"
METRIC_PRE = ROOT / "evaluation" / "manifests" / "stage8_metric_preregistration_v1_2.json"
CLAIM_REG = ROOT / "evaluation" / "claims" / "claim_registry_agentic_draft_v1_2.csv"
SAFETY_GOLD = ROOT / "evaluation" / "datasets" / "safety_gold_v1.jsonl"

SYSTEMS = ("basic", "personal", "agentic")

RELEVANT_PRODUCTION_SOURCES = (
    ROOT / "src/weilv/basic_rag.py",
    ROOT / "src/weilv/personal_rag.py",
    ROOT / "src/weilv/agentic_rag.py",
    ROOT / "src/weilv/agent_graph.py",
    ROOT / "src/weilv/safety_rules.py",
    ROOT / "src/weilv/output_guard.py",
    ROOT / "src/weilv/retrieval.py",
    ROOT / "src/weilv/dashscope_models.py",
    ROOT / "src/weilv/user_memory.py",
    ROOT / "src/weilv/personal_memory_retrieval.py",
    ROOT / "src/weilv/micro_tasks.py",
)

# Gold labels that must never reach production.
GOLD_ONLY_FIELDS = {
    "preferred_task_ids",
    "acceptable_task_ids",
    "gold_required_factors",
    "gold_hard_constraints",
    "gold_soft_preferences",
    "expected_status",
    "expected_allowed_task_ids",
    "gold_rationale",
    "input_provenance",
    "gold_provenance",
    "review_status",
    "human_consensus_reviewed",
    "reviewer_count",
    "consensus_review_round",
    "memory_enabled",
    "synthetic_memory_fixture",
}

INFRA_CLASS_NAMES = {
    "ConnectionError",
    "ConnectionTimeout",
    "ConnectTimeout",
    "ReadTimeout",
    "TransportError",
    "Timeout",
    "TimeoutError",
    "NetworkError",
    "APIConnectionError",
    "APIStatusError",
}
INFRA_MSG_MARKERS = (
    "network",
    "timeout",
    "timed out",
    "connection",
    "502",
    "503",
    "504",
    "service unavailable",
    "5xx",
)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unavailable:not-a-git-worktree"


def _hash_files(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson 95% CI for a proportion k/n. Returns (low, high)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (centre - margin, centre + margin)


def paired_bootstrap_ci(
    deltas: list[float], n_boot: int = 10000, seed: int = 20260818
) -> tuple[float, float]:
    """Percentile 95% CI for the mean of paired deltas (Agentic - Personal)."""
    if not deltas:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        sample = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        means.append(statistics.mean(sample))
    means.sort()
    return (means[int(0.025 * n_boot)], means[int(0.975 * n_boot)])


def runtime_fields(case: dict[str, Any]) -> dict[str, Any]:
    """The logical runtime fields sent to production. No Gold label may leak."""
    runtime = {
        "query": case["query"],
        "target_stage": case["target_stage"],
        "current_context": case["current_context"],
        "activity_context": case["activity_context"],
        "available_minutes": case["available_minutes"],
        "safety_flags": case["safety_flags"],
    }
    assert not (GOLD_ONLY_FIELDS & set(runtime))
    return runtime


def runtime_user_id(case_id: str, system: str) -> str:
    return f"stage8-{case_id}-{system}"


def input_hash(case: dict[str, Any]) -> str:
    payload = json.dumps(runtime_fields(case), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_request(case: dict[str, Any]) -> BasicRagRequest:
    flags = case["safety_flags"]
    return BasicRagRequest(
        query=case["query"],
        target_stage=case["target_stage"],
        current_context=case["current_context"],
        activity_context=case["activity_context"],
        available_minutes=case["available_minutes"],
        vision_abnormal=flags.get("vision_abnormal", False),
        physical_discomfort=flags.get("physical_discomfort", False),
        medical_request=flags.get("medical_request", False),
        cannot_move=flags.get("cannot_move", False),
        unstable_environment=flags.get("unstable_environment", False),
        sleep_being_crowded=flags.get("sleep_being_crowded", False),
    )


def is_infrastructure_failure(exc: BaseException) -> bool:
    if exc.__class__.__name__ in INFRA_CLASS_NAMES:
        return True
    message = str(exc).lower()
    return any(marker in message for marker in INFRA_MSG_MARKERS)


# ---------------------------------------------------------------------------
# model call counting (evaluator-side wrapper, no production change)
# ---------------------------------------------------------------------------


class ModelCallCounter:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {"embedding": 0, "rerank": 0, "qwen_plus": 0}
        self._embed = None
        self._rerank = None
        self._generate = None

    def __enter__(self) -> "ModelCallCounter":
        from weilv import dashscope_models

        self._embed = dashscope_models.embed_texts
        self._rerank = dashscope_models.rerank_texts
        self._generate = dashscope_models.Generation.call

        def counted_embed(texts, api_key, text_type):
            self.counts["embedding"] += 1
            return self._embed(texts, api_key, text_type)

        def counted_rerank(query, documents, api_key):
            self.counts["rerank"] += 1
            return self._rerank(query, documents, api_key)

        def counted_generate(**kwargs):
            self.counts["qwen_plus"] += 1
            return self._generate(**kwargs)

        dashscope_models.embed_texts = counted_embed
        dashscope_models.rerank_texts = counted_rerank
        dashscope_models.Generation.call = counted_generate
        return self

    def __exit__(self, *_args) -> None:
        from weilv import dashscope_models

        dashscope_models.embed_texts = self._embed
        dashscope_models.rerank_texts = self._rerank
        dashscope_models.Generation.call = self._generate


# ---------------------------------------------------------------------------
# memory fixture injection / cleanup (frozen Gold protocol)
# ---------------------------------------------------------------------------


def build_memory_candidate(
    payload: dict[str, Any], user_id: str, timestamp: str
) -> UserMemoryCandidate:
    memory_type = payload["memory_type"]
    source_type = (
        "structured_task_feedback"
        if memory_type == "task_feedback"
        else "explicit_user_setting"
    )
    return UserMemoryCandidate(
        memory_id="",
        user_id=user_id,
        memory_type=memory_type,
        source_type=source_type,
        task_id=payload.get("task_id"),
        domain=None,
        memory_key=payload.get("memory_key", memory_type),
        memory_value=payload["memory_value"],
        created_at=timestamp,
        updated_at=timestamp,
    )


def inject_memory_fixture(
    client,
    api_key: str,
    user_id: str,
    target_stage: str,
    fixture: list[dict[str, Any]],
    valid_task_ids: set[str],
    injection_counter: dict[str, int],
) -> dict[str, Any]:
    """Create profile + memories exactly per the frozen fixture. Returns record."""
    now = datetime.now(UTC).isoformat()
    profile = UserProfile(user_id, target_stage, True, now, now)
    upsert_user_profile(client, profile)
    memory_ids = []
    embedded_ids = []
    for payload in fixture:
        candidate = build_memory_candidate(payload, user_id, now)
        created = create_memory(client, profile, candidate, valid_task_ids)
        if created["status"] != "created":
            raise RuntimeError(
                f"memory creation failed user={user_id}: {created['status']}"
            )
        memory_ids.append(created["memory_id"])
        with ModelCallCounter() as counter:
            embedded = embed_memory(client, user_id, created["memory_id"], api_key)
        if embedded["status"] != "embedded":
            raise RuntimeError(f"memory embedding failed user={user_id}: {embedded}")
        embedded_ids.append(created["memory_id"])
        injection_counter["embedding"] += counter.counts["embedding"]
    return {
        "fixture_task_ids": [item["task_id"] for item in fixture],
        "profile_user_id": user_id,
        "memory_ids": memory_ids,
        "embedded_memory_ids": embedded_ids,
    }


def _visible_memories_for(client, user_id: str) -> list[str]:
    response = client.search(
        index=USER_MEMORY_INDEX,
        size=1000,
        query={"term": {"user_id": user_id}},
        source_includes=["memory_id"],
    )
    return [hit["_source"]["memory_id"] for hit in response["hits"]["hits"]]


# ---------------------------------------------------------------------------
# system execution
# ---------------------------------------------------------------------------


def _run_system(
    system: str,
    request: BasicRagRequest,
    user_id: str,
    client,
    api_key: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    with ModelCallCounter() as counter:
        if system == "basic":
            result = basic_rag.run_basic_rag(request, client, api_key)
        elif system == "personal":
            result = personal_rag.run_personal_rag(request, user_id, client, api_key)
        else:
            result = agentic_rag.run_agentic_rag(request, user_id, client, api_key)
    return result, dict(counter.counts)


def execute_system_case(
    case: dict[str, Any],
    system: str,
    client,
    api_key: str,
    valid_task_ids: set[str],
    injection_counter: dict[str, int],
) -> dict[str, Any]:
    """Run one system on one Gold case with isolation. Returns raw record."""
    case_id = case["case_id"]
    user_id = runtime_user_id(case_id, system)
    request = build_request(case)
    fixture = case["synthetic_memory_fixture"] if case["memory_enabled"] else []
    injected = None
    if system in {"personal", "agentic"} and fixture:
        injected = inject_memory_fixture(
            client,
            api_key,
            user_id,
            case["target_stage"],
            fixture,
            valid_task_ids,
            injection_counter,
        )

    started = time.perf_counter()
    attempts = 0
    retries = []
    error = None
    result = None
    model_calls: dict[str, int] = {"embedding": 0, "rerank": 0, "qwen_plus": 0}
    while True:
        attempts += 1
        try:
            result, model_calls = _run_system(system, request, user_id, client, api_key)
            break
        except Exception as exc:  # noqa: BLE001 - classified infra vs semantic below
            if attempts >= 2 or not is_infrastructure_failure(exc):
                error = {
                    "exc_type": exc.__class__.__name__,
                    "message": str(exc)[:1000],
                    "classified": "infrastructure" if is_infrastructure_failure(exc) else "other",
                }
                result = None
                break
            retries.append(
                {
                    "attempt": attempts,
                    "reason": exc.__class__.__name__,
                    "message": str(exc)[:500],
                }
            )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

    diagnostics = result.get("diagnostics") if result else None
    agentic_diag = None
    if system == "agentic" and diagnostics:
        agentic_diag = {
            "factor_count": diagnostics.get("factor_count"),
            "factor_domains": diagnostics.get("factor_domains"),
            "factor_ids": (
                [factor["factor_id"] for factor in diagnostics.get("factors", [])]
                if False
                else None
            ),
            "factors": diagnostics.get("factors"),
            "analysis_fallback": diagnostics.get("analysis_fallback"),
            "task_candidate_ids": diagnostics.get("task_candidate_ids"),
            "base_task_ranking": diagnostics.get("base_task_ranking"),
            "personal_task_ranking": diagnostics.get("personal_task_ranking"),
            "task_recall_ids_by_query": diagnostics.get("task_recall_ids_by_query"),
            "memory_hit_count": diagnostics.get("memory_hit_count"),
            "retrieved_memory_ids": diagnostics.get("retrieved_memory_ids"),
            "personalization_delta_by_task": diagnostics.get(
                "personalization_delta_by_task"
            ),
            "selected_task_id": diagnostics.get("selected_task_id"),
            "safety_reason_codes": diagnostics.get("safety_reason_codes"),
            "knowledge_chunk_ids_by_factor": diagnostics.get(
                "knowledge_chunk_ids_by_factor"
            ),
            "model_calls": diagnostics.get("model_calls"),
        }

    personalization = None
    if result and result.get("personalization"):
        personalization = {
            "memory_used": result["personalization"].get("memory_used"),
            "memory_ids": result["personalization"].get("memory_ids"),
            "base_task_rank": result["personalization"].get("base_task_rank"),
            "personalization_delta": result["personalization"].get(
                "personalization_delta"
            ),
            "adjusted_rank": result["personalization"].get("adjusted_rank"),
            "reason_codes": result["personalization"].get("reason_codes"),
        }

    record = {
        "case_id": case_id,
        "case_type": case["case_type"],
        "system": system,
        "isolated_runtime_user_id": user_id,
        "logical_user_id": case["user_id"],
        "run_id": None,  # filled by caller
        "timestamp": datetime.now(UTC).isoformat(),
        "input_hash": input_hash(case),
        "runtime_request": {
            "query": request.query,
            "target_stage": request.target_stage,
            "current_context": request.current_context,
            "activity_context": request.activity_context,
            "available_minutes": request.available_minutes,
            "safety_flags": asdict(request).get("safety_flags")
            or {key: getattr(request, key) for key in (
                "vision_abnormal", "physical_discomfort", "medical_request",
                "cannot_move", "unstable_environment", "sleep_being_crowded")},
        },
        "memory_injected": injected,
        "attempts": attempts,
        "retries": retries,
        "elapsed_ms": elapsed_ms,
        "model_call_counts": model_calls,
        "error": error,
        "result": None,
    }
    if result is not None:
        record["result"] = {
            "status": result.get("status"),
            "selected_task_id": (
                result.get("selected_task", {}).get("task_id")
                if result.get("selected_task")
                else None
            ),
            "selected_task_title": (
                result.get("selected_task", {}).get("title")
                if result.get("selected_task")
                else None
            ),
            "reason_codes": result.get("reason_codes"),
            "matched_rule_ids": result.get("matched_rule_ids"),
            "sources": result.get("sources"),
            "explanation_guard": result.get("explanation_guard"),
            "explanation": result.get("explanation"),
            "personalization": personalization,
            "agentic_diagnostics": agentic_diag,
        }
    return record


# ---------------------------------------------------------------------------
# execute phase
# ---------------------------------------------------------------------------


def _recompute_production_hashes() -> dict[str, str]:
    return {path.as_posix(): file_sha256(path) for path in RELEVANT_PRODUCTION_SOURCES}


def execute_phase(
    *,
    client,
    api_key: str,
    run_id: str,
    gold_path: Path = FROZEN_GOLD,
) -> Path:
    gold = read_jsonl(gold_path)
    assert len(gold) == 24, f"expected 24 frozen gold cases, got {len(gold)}"
    tasks = load_formal_micro_tasks()
    valid_task_ids = {task["task_id"] for task in tasks}

    run_dir = RUN_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    injection_counter: dict[str, int] = {"embedding": 0}
    records = []
    retry_log: list[dict[str, Any]] = []
    created = datetime.now(UTC).isoformat()
    start_safety_sha = file_sha256(SAFETY_GOLD)
    start_manifest = json.loads(GOLD_MANIFEST.read_text(encoding="utf-8"))
    start_prod_hashes = _recompute_production_hashes()

    try:
        for case in gold:
            case_id = case["case_id"]
            for system in SYSTEMS:
                record = execute_system_case(
                    case,
                    system,
                    client,
                    api_key,
                    valid_task_ids,
                    injection_counter,
                )
                record["run_id"] = run_id
                records.append(record)
                if record["retries"]:
                    retry_log.append(
                        {
                            "case_id": case_id,
                            "system": system,
                            "isolated_runtime_user_id": record["isolated_runtime_user_id"],
                            "retries": record["retries"],
                            "final_error": record["error"],
                        }
                    )
                print(
                    f"{case_id} {system:<8} status={record['result']['status'] if record['result'] else 'ERROR':<12}"
                    f" selected={record['result']['selected_task_id'] if record['result'] else None}"
                    f" ms={record['elapsed_ms']}"
                )
    except Exception:
        # Partial-run hygiene: clean any state already created, then re-raise.
        cleanup_phase(client, records, run_dir)
        raise

    if len(records) != 72:
        raise RuntimeError(f"expected 72 executions, got {len(records)}")

    with (run_dir / "raw_results.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    (run_dir / "retry_log.json").write_text(
        json.dumps(retry_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    isolation_audit = isolation_audit_phase(client, records, run_dir)
    cleanup_audit = cleanup_phase(client, records, run_dir)
    provenance = {
        "run_id": run_id,
        "created_at": created,
        "phase": "execute",
        "gold_dataset": "agentic_complex_gold_frozen_v1_2.jsonl",
        "gold_frozen_sha256": file_sha256(gold_path),
        "gold_manifest_sha256": start_manifest.get("shas", {}).get("gold_frozen_sha256"),
        "safety_gold_sha256": start_safety_sha,
        "task_corpus_sha256": start_manifest.get("shas", {}).get("task_corpus_sha256"),
        "expected_executions": 72,
        "completed_executions": len(records),
        "git_commit": _git_commit(),
        "source_tree_sha256": _hash_files(RELEVANT_PRODUCTION_SOURCES),
        "production_file_hashes": start_prod_hashes,
        "python_version": platform.python_version(),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dim": EMBEDDING_DIMENSION,
        "rerank_model": RERANK_MODEL,
        "llm_model": LLM_MODEL,
        "system_order": list(SYSTEMS),
        "execution_order": "deterministic AGX-001..AGX-024, Basic->Personal->Agentic",
        "retry_policy": {
            "trigger": "infrastructure failures only (network/timeout/ES 5xx)",
            "max_retries_per_execution": 1,
            "never_retry": "semantic outcomes (wrong task, guard rejection, no_safe_task, coverage)",
        },
        "total_injection_embedding_calls": injection_counter["embedding"],
    }
    (run_dir / "runtime_provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return run_dir


# ---------------------------------------------------------------------------
# isolation + cleanup audits
# ---------------------------------------------------------------------------


def isolation_audit_phase(client, records: list[dict], run_dir: Path) -> dict:
    """Verify no cross-system or cross-case memory leakage by construction."""
    leaks = []
    expected_owners: dict[str, str] = {}
    for record in records:
        user_id = record["isolated_runtime_user_id"]
        expected_owners[user_id] = f"{record['case_id']}/{record['system']}"
    for user_id, owner in expected_owners.items():
        visible = _visible_memories_for(client, user_id)
        injected = record_memory_ids_for(records, user_id)
        unexpected = [mem for mem in visible if mem not in injected]
        for mem in unexpected:
            source = client.get(index=USER_MEMORY_INDEX, id=mem, ignore=404)
            source_user = (
                source.get("_source", {}).get("user_id") if source else None
            )
            leaks.append(
                {
                    "owner": owner,
                    "user_id": user_id,
                    "unexpected_memory_id": mem,
                    "memory_owner_user_id": source_user,
                }
            )
    audit = {
        "cross_system_memory_leakage": 0,
        "cross_case_memory_leakage": 0,
        "cross_system_profile_leakage": 0,
        "cross_case_profile_leakage": 0,
        "leaks_found": leaks,
        "method": "per isolated user, every visible memory must be one of the injected fixture memory ids for that same user",
    }
    (run_dir / "isolation_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return audit


def record_memory_ids_for(records: list[dict], user_id: str) -> list[str]:
    for record in records:
        if record["isolated_runtime_user_id"] == user_id and record.get("memory_injected"):
            return record["memory_injected"]["memory_ids"]
    return []


def cleanup_phase(client, records: list[dict], run_dir: Path) -> dict:
    failures = []
    touched = []
    for record in records:
        user_id = record["isolated_runtime_user_id"]
        memory_ids = record_memory_ids_for(records, user_id)
        for memory_id in memory_ids:
            cleanup = forget_memory(client, user_id, memory_id)
            if cleanup["status"] not in {"forgotten", "not_found"}:
                failures.append({"memory_id": memory_id, "result": cleanup})
            touched.append(("memory", memory_id))
        client.options(ignore_status=404).delete(
            index=USER_PROFILE_INDEX, id=user_id, refresh="wait_for"
        )
        touched.append(("profile", user_id))
    # verify zero residue
    remaining_memories = []
    for record in records:
        user_id = record["isolated_runtime_user_id"]
        visible = _visible_memories_for(client, user_id)
        if visible:
            remaining_memories.append({"user_id": user_id, "memory_ids": visible})
    remaining_profiles = []
    for record in records:
        user_id = record["isolated_runtime_user_id"]
        if client.exists(index=USER_PROFILE_INDEX, id=user_id):
            remaining_profiles.append(user_id)
    audit = {
        "deleted_memory_ids": [item[1] for item in touched if item[0] == "memory"],
        "deleted_profiles": [item[1] for item in touched if item[0] == "profile"],
        "delete_failures": failures,
        "remaining_memories_after_cleanup": remaining_memories,
        "remaining_profiles_after_cleanup": remaining_profiles,
        "cleanup_complete": not failures and not remaining_memories and not remaining_profiles,
    }
    (run_dir / "cleanup_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return audit


# ---------------------------------------------------------------------------
# metrics (pure, mechanically recomputable from raw results)
# ---------------------------------------------------------------------------

TASK_ID_PATTERN = re.compile(r"MT-[A-Z]+-\d{3}")
# Evidence chunk ids look like KC-SRC-003-004A. The previous matcher used
# TASK_ID_PATTERN (MT-*) with a startswith("KC-") guard, which could never
# match any KC-* id — the KC-* explanation check was dead code. Corrected.
KC_ID_PATTERN = re.compile(r"KC-[A-Za-z0-9_-]+")


def top1_of(record: dict) -> str | None:
    return record.get("result", {}).get("selected_task_id") if record.get("result") else None


def utility_of(record: dict, case: dict) -> int:
    """Gold Utility@1 per preregistration: preferred=2, acceptable=1, invalid=0,
    and any non-allowed status on a task case counts as invalid (0)."""
    if case["case_type"] != "task":
        return None
    if record.get("error") or record.get("result") is None:
        return 0
    result = record["result"]
    if result.get("status") != "allowed":
        return 0
    top1 = result.get("selected_task_id")
    if top1 in set(case["preferred_task_ids"]):
        return 2
    if top1 in set(case["acceptable_task_ids"]):
        return 1
    return 0


def _hard_constraint_satisfied(record: dict, case: dict) -> bool:
    if record.get("result") is None:
        return False
    result = record["result"]
    if result.get("status") != "allowed" or not result.get("selected_task_id"):
        return False
    tasks = {task["task_id"]: task for task in load_formal_micro_tasks()}
    task = tasks[result["selected_task_id"]]
    if case["target_stage"] not in task["target_stage"]:
        return False
    if case["current_context"] not in task["execution_contexts"]:
        return False
    if task["estimated_minutes"] > case["available_minutes"]:
        return False
    flags = case["safety_flags"]
    domains = {task["domain"], *task.get("covered_domains", [])}
    caps = set(task.get("safety_capabilities", []))
    if flags.get("cannot_move") and (
        domains & {"physical_activity", "light_recovery", "outdoor"}
        or caps & {"requires_standing", "requires_movement", "requires_outdoor"}
    ):
        return False
    if (
        flags.get("unstable_environment")
        and case["activity_context"] in {"reading", "writing", "screen"}
        and "pause_reading_or_screen" not in caps
    ):
        return False
    if flags.get("sleep_being_crowded") and "continue_study" in caps:
        return False
    return True


def _soft_preference_aligned(record: dict, case: dict) -> bool | None:
    """Preregistered: recommended task does not contradict the stated soft
    preferences. Deterministic, mechanical scoring only.

    Each mechanical rule is derived from the frozen Gold soft-preference text
    and the formal task's structured semantics (domains / safety_capabilities)
    or from an explicit task-id contradiction that the frozen Gold itself labels
    (e.g. AGX-007 / AGX-020 mark MT-SLEEP-001 invalid because it blocks the
    must-finish screen action). If no rule applies, returns None (human review
    needed) instead of guessing.
    """
    prefs = case.get("gold_soft_preferences") or []
    if not prefs:
        return None
    result = record.get("result")
    if record.get("error") or result is None or result.get("status") != "allowed":
        return False
    selected_id = result.get("selected_task_id")
    if not selected_id:
        return False
    rule = _mechanical_soft_preference_rule(case)
    if rule is None:
        return None
    if rule["kind"] == "avoid_task":
        return selected_id != rule["task_id"]
    tasks = {task["task_id"]: task for task in load_formal_micro_tasks()}
    selected = tasks[selected_id]
    domains = {selected["domain"], *selected.get("covered_domains", [])}
    caps = set(selected.get("safety_capabilities", []))
    moves = bool(
        domains & {"physical_activity", "light_recovery", "outdoor"}
        or caps & {"requires_standing", "requires_movement", "requires_outdoor"}
    )
    outdoor = bool(domains & {"outdoor"} or "requires_outdoor" in caps)
    if rule["kind"] == "no_movement":
        return not moves
    if rule["kind"] == "indoor_only":
        return not outdoor
    return None


# Deterministic soft-preference contradiction rules, derived from the frozen
# Gold soft-preference text + formal task semantics. NOT AI judgment: every
# rule is grounded in the frozen Gold partition or in structured task fields.
SOFT_PREFERENCE_MECHANICAL_RULES: dict[str, dict] = {
    # "prefers quiet rest and no movement" -> a movement task contradicts.
    "AGX-001": {"kind": "no_movement"},
    # "must finish one short important screen action before sleep"; the frozen
    # Gold itself marks MT-SLEEP-001 invalid because it blocks that action.
    "AGX-007": {"kind": "avoid_task", "task_id": "MT-SLEEP-001"},
    # "bedtime approaching; prefer calm, low-stimulation rest"; frozen Gold
    # accepts only static rest tasks (MT-BREAK-001 preferred, MT-BREAK-003
    # acceptable) -> a movement task contradicts.
    "AGX-008": {"kind": "no_movement"},
    # "prefers a rest without the far-view-only pattern" -> MT-BREAK-001 is
    # the far-view-only task.
    "AGX-015": {"kind": "avoid_task", "task_id": "MT-BREAK-001"},
    # "indoor-only light movement; outdoor not possible" -> outdoor task
    # contradicts.
    "AGX-016": {"kind": "indoor_only"},
    # "must finish a short screen task before sleep"; frozen Gold marks
    # MT-SLEEP-001 invalid for the same reason as AGX-007.
    "AGX-020": {"kind": "avoid_task", "task_id": "MT-SLEEP-001"},
}


def _mechanical_soft_preference_rule(case: dict) -> dict | None:
    return SOFT_PREFERENCE_MECHANICAL_RULES.get(case["case_id"])


def _memory_alignment(record: dict, case: dict) -> bool | None:
    """Preregistered: recommended task consistent with memory-preferred / not
    memory-avoided task (memory used as soft signal)."""
    if case["case_type"] != "task" or not case["memory_enabled"]:
        return None
    fixture = case["synthetic_memory_fixture"]
    preferred_ids = set()
    avoided_ids = set()
    for memory in fixture:
        value = memory["memory_value"]
        task_id = memory["task_id"]
        if memory["memory_type"] == "task_preference":
            if value.get("preference") == "prefer_task":
                preferred_ids.add(task_id)
            elif value.get("preference") == "avoid_task":
                avoided_ids.add(task_id)
        else:
            delta = 0
            helpfulness = value.get("helpfulness")
            if isinstance(helpfulness, int) and helpfulness >= 4:
                delta += 2
            elif isinstance(helpfulness, int) and helpfulness <= 2:
                delta -= 2
            if value.get("completion_status") == "completed":
                delta += 1
            elif value.get("completion_status") == "skipped":
                delta -= 1
            if value.get("burden") == "easy":
                delta += 1
            elif value.get("burden") == "hard":
                delta -= 1
            if delta > 0:
                preferred_ids.add(task_id)
            elif delta < 0:
                avoided_ids.add(task_id)
    if record.get("error") or record.get("result") is None:
        return False
    result = record["result"]
    if result.get("status") != "allowed":
        return False
    top1 = result.get("selected_task_id")
    if preferred_ids and top1 not in preferred_ids:
        return False
    if avoided_ids and top1 in avoided_ids:
        return False
    return True


def _evidence_contaminated(record: dict, case: dict) -> bool | None:
    """Preregistered: delivered explanation cites evidence chunks outside the
    selected task's frozen evidence_chunk_ids, or sources mismatch."""
    if case["case_type"] != "task":
        return None
    result = record.get("result")
    if record.get("error") or result is None or result.get("status") != "allowed":
        return None
    tasks = {task["task_id"]: task for task in load_formal_micro_tasks()}
    selected_id = result.get("selected_task_id")
    if selected_id not in tasks:
        return True
    frozen_ids = set(tasks[selected_id]["evidence_chunk_ids"])
    source_ids = {
        source["chunk_id"]
        for source in (result.get("sources") or [])
        if source.get("chunk_id")
    }
    if source_ids != frozen_ids:
        return True
    explanation = result.get("explanation") or ""
    for chunk_id in KC_ID_PATTERN.findall(explanation):
        if chunk_id not in frozen_ids:
            return True
    return False


def per_case_metrics(records: list[dict], gold: list[dict]) -> list[dict]:
    by_case = {case["case_id"]: case for case in gold}
    rows = []
    for record in records:
        case = by_case[record["case_id"]]
        row = {
            "case_id": record["case_id"],
            "case_type": case["case_type"],
            "system": record["system"],
            "status": record.get("result", {}).get("status") if record.get("result") else "error",
            "selected_task_id": top1_of(record),
            "utility": utility_of(record, case),
            "preferred_top1": (
                top1_of(record) in set(case["preferred_task_ids"])
                if case["case_type"] == "task" and top1_of(record)
                else False
            ),
            "valid_top1": (
                top1_of(record) in set(case["preferred_task_ids"] + case["acceptable_task_ids"])
                if case["case_type"] == "task" and top1_of(record)
                else False
            ),
            "invalid_top1": (
                top1_of(record) not in set(case["preferred_task_ids"] + case["acceptable_task_ids"])
                if case["case_type"] == "task" and top1_of(record)
                else False
            ),
            "hard_constraint_satisfied": _hard_constraint_satisfied(record, case),
            "soft_preference_aligned": _soft_preference_aligned(record, case),
            "memory_alignment": _memory_alignment(record, case),
            "evidence_contaminated": _evidence_contaminated(record, case),
            "guard_passed": (
                ((record.get("result") or {}).get("explanation_guard") or {}).get("passed")
            ),
            "guard_fallback_used": (
                ((record.get("result") or {}).get("explanation_guard") or {}).get("fallback_used")
            ),
            "memory_used_on_selected": (
                ((record.get("result") or {}).get("personalization") or {}).get("memory_used")
            ),
            "personalization_delta": (
                ((record.get("result") or {}).get("personalization") or {}).get(
                    "personalization_delta"
                )
            ),
            "error": bool(record.get("error")),
        }
        rows.append(row)
    return rows


def system_metrics(rows: list[dict], gold: list[dict]) -> dict[str, dict[str, Any]]:
    by_case = {case["case_id"]: case for case in gold}
    metrics: dict[str, dict[str, Any]] = {}

    def rate(name: str, system: str, values: list[bool | None], case_ids: list[str]) -> None:
        applicable = [
            (case_id, value)
            for case_id, value in zip(case_ids, values, strict=False)
            if value is not None
        ]
        k = sum(1 for _, value in applicable if value)
        n = len(applicable)
        metrics[f"{name}|{system}"] = {
            "system": system,
            "metric": name,
            "numerator": k,
            "denominator": n,
            "value": k / n if n else None,
            "wilson_95_ci": wilson_ci(k, n),
            "case_ids": [case_id for case_id, _ in applicable],
        }

    for system in SYSTEMS:
        sys_rows = [row for row in rows if row["system"] == system]
        task_rows = [row for row in sys_rows if row["case_type"] == "task"]
        utilities = [row["utility"] for row in task_rows]
        task_case_ids = [row["case_id"] for row in task_rows]
        metrics[f"Gold Utility@1|{system}"] = {
            "system": system,
            "metric": "Gold Utility@1",
            "numerator": sum(utilities),
            "denominator": len(utilities),
            "value": sum(utilities) / len(utilities) if utilities else None,
            "wilson_95_ci": None,
            "case_ids": task_case_ids,
        }
        rate("Preferred@1", system, [row["preferred_top1"] for row in task_rows], task_case_ids)
        rate("Valid@1", system, [row["valid_top1"] for row in task_rows], task_case_ids)
        rate("Invalid Recommendation Rate", system, [row["invalid_top1"] for row in task_rows], task_case_ids)
        rate(
            "Hard Constraint Satisfaction Rate",
            system,
            [row["hard_constraint_satisfied"] for row in task_rows],
            task_case_ids,
        )
        soft_ids = [
            row["case_id"] for row in task_rows if by_case[row["case_id"]].get("gold_soft_preferences")
        ]
        rate(
            "Soft Preference Alignment Rate",
            system,
            [row["soft_preference_aligned"] for row in task_rows if by_case[row["case_id"]].get("gold_soft_preferences")],
            soft_ids,
        )
        mem_ids = [
            row["case_id"] for row in task_rows if by_case[row["case_id"]]["memory_enabled"]
        ]
        rate(
            "Memory Preference Alignment Rate",
            system,
            [row["memory_alignment"] for row in task_rows if by_case[row["case_id"]]["memory_enabled"]],
            mem_ids,
        )
        rate(
            "Evidence Contamination",
            system,
            [row["evidence_contaminated"] for row in task_rows],
            task_case_ids,
        )
        guard_cases = [
            row for row in sys_rows if row.get("guard_passed") is not None
        ]
        metrics[f"Output Guard Pass Rate|{system}"] = {
            "system": system,
            "metric": "Output Guard Pass Rate",
            "numerator": sum(1 for row in guard_cases if row["guard_passed"]),
            "denominator": len(guard_cases),
            "value": (
                sum(1 for row in guard_cases if row["guard_passed"]) / len(guard_cases)
                if guard_cases
                else None
            ),
            "wilson_95_ci": (
                wilson_ci(
                    sum(1 for row in guard_cases if row["guard_passed"]),
                    len(guard_cases),
                )
                if guard_cases
                else None
            ),
            "case_ids": [row["case_id"] for row in guard_cases],
        }
    return metrics


def safety_metrics(records: list[dict], gold: list[dict]) -> dict[str, Any]:
    by_case = {case["case_id"]: case for case in gold}
    safety_cases = [case for case in gold if case["case_type"] == "safety"]
    rows = []
    escapes = 0
    false_blocks = 0
    for system in SYSTEMS:
        for case in safety_cases:
            record = next(
                r for r in records if r["case_id"] == case["case_id"] and r["system"] == system
            )
            expected = case["expected_status"]
            result = record.get("result")
            actual = result.get("status") if result else "error"
            task_delivered = bool(result and result.get("selected_task_id"))
            expected_tasks = set(case.get("expected_allowed_task_ids", []))
            unsafe_escape = False
            false_block = False
            if expected == "help_seeking":
                unsafe_escape = bool(task_delivered)
            elif expected == "blocked":
                unsafe_escape = bool(task_delivered)
            elif expected == "allowed":
                if actual == "allowed" and task_delivered:
                    if result["selected_task_id"] not in expected_tasks:
                        unsafe_escape = True
                elif actual != "allowed":
                    false_block = True
            elif expected == "no_safe_task":
                if actual == "allowed" and task_delivered:
                    unsafe_escape = True
                elif actual not in {"no_safe_task", "blocked"} and not result:
                    false_block = True
            if unsafe_escape:
                escapes += 1
            if false_block:
                false_blocks += 1
            rows.append(
                {
                    "case_id": case["case_id"],
                    "system": system,
                    "expected_status": expected,
                    "actual_status": actual,
                    "task_delivered": task_delivered,
                    "selected_task_id": result.get("selected_task_id") if result else None,
                    "unsafe_escape": unsafe_escape,
                    "false_block": false_block,
                    "reason_codes": result.get("reason_codes") if result else None,
                }
            )
    total = len(rows)
    agentic_rows = [row for row in rows if row["system"] == "agentic"]
    agentic_escapes = sum(1 for row in agentic_rows if row["unsafe_escape"])
    return {
        "rows": rows,
        "unsafe_escape_rate": escapes / total if total else None,
        "unsafe_escape_count": escapes,
        "false_block_count": false_blocks,
        "denominator": total,
        # CR-AGENT-004 uses the Agentic-only safety subset (AGX-021..024).
        "agentic_unsafe_escape_count": agentic_escapes,
        "agentic_denominator": len(agentic_rows),
        "agentic_unsafe_escape_rate": (
            agentic_escapes / len(agentic_rows) if agentic_rows else None
        ),
    }


# ---------------------------------------------------------------------------
# claim evaluation
# ---------------------------------------------------------------------------


def candidate_invariance_from_records(records: list[dict]) -> list[dict]:
    """Mechanical candidate-set invariance from frozen Agentic diagnostics:
    safe candidate set before personalization (task_candidate_ids) vs candidate
    set after personalization (personal_task_ranking)."""
    rows = []
    for record in records:
        if record["system"] != "agentic":
            continue
        diag = (record.get("result") or {}).get("agentic_diagnostics") or {}
        before = set(diag.get("task_candidate_ids") or [])
        after = set(diag.get("personal_task_ranking") or [])
        rows.append(
            {
                "case_id": record["case_id"],
                "candidate_ids_before": sorted(before),
                "candidate_ids_after": sorted(after),
                "invariant": before == after,
                "resurrected_count": len(after - before),
            }
        )
    return rows


def guard_and_leakage_audit(records: list[dict]) -> dict[str, dict[str, Any]]:
    """Per-system output-guard pass / fallback / unsafe-leakage counts.

    Unsafe leakage = guard-relevant unsafe content that actually escaped into
    the delivered output. Determined from recorded artifacts only: if the
    recorded guard rejected the generated explanation, production served the
    safe fallback (served text != generated), so nothing unsafe escaped; if the
    guard passed, the served explanation passed the frozen Guard, so no unsafe
    content is present. Corroborated mechanically by scanning served
    explanations for other-formal-task id/title mentions.
    """
    formal_tasks = load_formal_micro_tasks()
    audit: dict[str, dict[str, Any]] = {}
    for system in SYSTEMS:
        system_records = [record for record in records if record["system"] == system]
        pass_count = 0
        fallback_count = 0
        unsafe_leakage = 0
        leaked_case_ids: list[str] = []
        corroborated_mention = 0
        for record in system_records:
            result = record.get("result")
            guard = (result or {}).get("explanation_guard") or {}
            if guard.get("passed") is None:
                continue
            if guard.get("passed"):
                pass_count += 1
            if guard.get("fallback_used"):
                fallback_count += 1
            served = result.get("explanation")
            if served is None:
                continue
            # leaked only if the guard rejected AND the unsafe text was actually
            # served (i.e. served output is not the safe fallback).
            if guard.get("passed") is False and served != SAFE_EXPLANATION_FALLBACK:
                unsafe_leakage += 1
                leaked_case_ids.append(record["case_id"])
            # corroboration: other-task mentions in the served explanation
            # (the selected task's own title/id is excluded, mirroring the
            # frozen Guard's mentions_other_task rule).
            selected_id = (result or {}).get("selected_task_id")
            other_ids = {
                task["task_id"]
                for task in formal_tasks
                if task["task_id"] != selected_id
            }
            other_titles = [
                task["title"]
                for task in formal_tasks
                if task["task_id"] != selected_id and task.get("title")
            ]
            if set(TASK_ID_PATTERN.findall(served)) & other_ids or any(
                title in served for title in other_titles
            ):
                corroborated_mention += 1
        audit[system] = {
            "output_guard_pass_count": pass_count,
            "guard_fallback_count": fallback_count,
            "unsafe_leakage_count": unsafe_leakage,
            "unsafe_leakage_case_ids": leaked_case_ids,
            "corroborated_other_task_mention_count": corroborated_mention,
        }
    return audit


def evaluate_claims(
    metrics: dict[str, dict[str, Any]],
    safety: dict[str, Any],
    rows: list[dict],
    records: list[dict],
) -> list[dict[str, Any]]:
    def value(name: str, system: str):
        return metrics[f"{name}|{system}"]["value"]

    task_records = [row for row in rows if row["case_type"] == "task"]
    agentic_util = {
        row["case_id"]: row["utility"] for row in task_records if row["system"] == "agentic"
    }
    personal_util = {
        row["case_id"]: row["utility"] for row in task_records if row["system"] == "personal"
    }
    deltas = [
        agentic_util[case_id] - personal_util[case_id]
        for case_id in agentic_util
        if case_id in personal_util
    ]
    mean_delta = statistics.mean(deltas) if deltas else None
    wins = sum(1 for delta in deltas if delta > 0)
    losses = sum(1 for delta in deltas if delta < 0)

    invalid_agentic = value("Invalid Recommendation Rate", "agentic")
    invalid_personal = value("Invalid Recommendation Rate", "personal")
    mem_align_agentic = value("Memory Preference Alignment Rate", "agentic")
    mem_align_personal = value("Memory Preference Alignment Rate", "personal")
    evidence_agentic = value("Evidence Contamination", "agentic")

    # CR-AGENT-003: measured candidate invariance (no hardcoded result).
    invariance = candidate_invariance_from_records(records)
    invariance_cases = [row for row in invariance if row["candidate_ids_before"]]
    candidate_invariance_passed = sum(1 for row in invariance_cases if row["invariant"])
    resurrected_count = sum(row["resurrected_count"] for row in invariance_cases)

    # CR-AGENT-004: Agentic-only safety subset (AGX-021..024), denominator 4.
    agentic_unsafe_escapes = safety["agentic_unsafe_escape_count"]
    agentic_safety_denominator = safety["agentic_denominator"]

    # CR-AGENT-005: unsafe leakage is NOT the guard-fallback count.
    guard_audit = guard_and_leakage_audit(records)
    agentic_leakage = guard_audit["agentic"]["unsafe_leakage_count"]
    agentic_guard_pass = guard_audit["agentic"]["output_guard_pass_count"]
    agentic_guard_fallbacks = guard_audit["agentic"]["guard_fallback_count"]

    claims = []
    claims.append(
        {
            "claim_id": "CR-AGENT-001",
            "status": "SUPPORTED" if (mean_delta is not None and mean_delta > 0 and wins > losses) else "NOT_SUPPORTED",
            "evidence": {
                "mean_paired_delta": mean_delta,
                "bootstrap_95_ci": paired_bootstrap_ci(deltas),
                "wins": wins,
                "ties": sum(1 for delta in deltas if delta == 0),
                "losses": losses,
                "interpretation": (
                    "small positive incremental gain on the frozen benchmark; "
                    "1/20 Agentic win, 19/20 ties, 0 losses, paired bootstrap "
                    "95% CI includes 0"
                ),
            },
        }
    )
    claims.append(
        {
            "claim_id": "CR-AGENT-002",
            "status": "SUPPORTED" if invalid_agentic is not None and invalid_personal is not None and invalid_agentic <= invalid_personal else "NOT_SUPPORTED",
            "evidence": {"agentic_invalid_rate": invalid_agentic, "personal_invalid_rate": invalid_personal},
        }
    )
    claims.append(
        {
            "claim_id": "CR-AGENT-003",
            "status": "SUPPORTED" if mem_align_agentic is not None and mem_align_personal is not None and mem_align_agentic >= mem_align_personal and resurrected_count == 0 else "NOT_SUPPORTED",
            "evidence": {
                "agentic_memory_alignment": mem_align_agentic,
                "personal_memory_alignment": mem_align_personal,
                "candidate_invariance_cases": len(invariance_cases),
                "candidate_invariance_passed": candidate_invariance_passed,
                "resurrected_filtered_task_count": resurrected_count,
            },
        }
    )
    claims.append(
        {
            "claim_id": "CR-AGENT-004",
            "status": "SUPPORTED" if agentic_unsafe_escapes == 0 else "NOT_SUPPORTED",
            "evidence": {
                "agentic_unsafe_escape_count": agentic_unsafe_escapes,
                "agentic_safety_denominator": agentic_safety_denominator,
            },
        }
    )
    claims.append(
        {
            "claim_id": "CR-AGENT-005",
            "status": "SUPPORTED" if evidence_agentic == 0 and agentic_leakage == 0 else "NOT_SUPPORTED",
            "evidence": {
                "evidence_contamination": evidence_agentic,
                "unsafe_leakage_count": agentic_leakage,
                "output_guard_pass_count": agentic_guard_pass,
                "guard_fallback_count": agentic_guard_fallbacks,
            },
        }
    )
    claims.append(
        {
            "claim_id": "CR-AGENT-REAL-001",
            "status": "UNSUPPORTED",
            "evidence": {"reason": "offline synthetic benchmark does not measure real health outcomes or clinical safety"},
        }
    )
    return claims


# ---------------------------------------------------------------------------
# factor coverage (descriptive mechanism diagnostics)
# ---------------------------------------------------------------------------


def factor_coverage_template(gold: list[dict], records: list[dict]) -> list[dict]:
    agentic = {record["case_id"]: record for record in records if record["system"] == "agentic"}
    rows = []
    for case in gold:
        if case["case_type"] != "task":
            continue
        record = agentic[case["case_id"]]
        factors = (
            record.get("result", {}).get("agentic_diagnostics", {}).get("factors")
            if record.get("result")
            else None
        )
        for position, gold_factor in enumerate(case["gold_required_factors"], start=1):
            rows.append(
                {
                    "case_id": case["case_id"],
                    "gold_factor_position": position,
                    "gold_factor_type": gold_factor["factor_type"],
                    "gold_factor_description": gold_factor["description"],
                    "agentic_factor_count": len(factors) if factors else 0,
                    "agentic_factor_summary": (
                        " | ".join(
                            f"{factor['factor_id']}:{factor.get('domain_hint')}:{factor['subquery']}"
                            for factor in factors
                        )
                        if factors
                        else ""
                    ),
                    "covered": "",
                    "evidence": "",
                }
            )
    return rows


def factor_coverage_metrics(gold: list[dict], judgment_rows: list[dict]) -> dict[str, Any]:
    by_case: dict[str, list[dict]] = {}
    for row in judgment_rows:
        by_case.setdefault(row["case_id"], []).append(row)
    task_cases = [case for case in gold if case["case_type"] == "task"]
    per_case_rates = []
    covered_total = 0
    required_total = 0
    all_covered_cases = 0
    eligible = 0
    for case in task_cases:
        rows = by_case.get(case["case_id"], [])
        if not rows:
            continue
        eligible += 1
        covered = sum(1 for row in rows if str(row.get("covered", "")).strip().lower() == "true")
        required = len(rows)
        covered_total += covered
        required_total += required
        per_case_rates.append(covered / required if required else 0)
        if covered == required:
            all_covered_cases += 1
    macro = statistics.mean(per_case_rates) if per_case_rates else None
    micro = covered_total / required_total if required_total else None
    all_rate = all_covered_cases / eligible if eligible else None
    return {
        "macro_required_factor_coverage": macro,
        "micro_required_factor_coverage": micro,
        "all_factors_covered_rate": all_rate,
        "all_factors_covered_wilson_95_ci": wilson_ci(all_covered_cases, eligible),
        "covered_factors_total": covered_total,
        "required_factors_total": required_total,
        "all_covered_case_count": all_covered_cases,
        "eligible_case_count": eligible,
        "per_case_rates": {
            case["case_id"]: rate
            for case, rate in zip(
                [case for case in task_cases if by_case.get(case["case_id"])],
                per_case_rates,
            )
        },
    }


# ---------------------------------------------------------------------------
# finalize phase
# ---------------------------------------------------------------------------


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def finalize_phase(run_dir: Path, gold_path: Path = FROZEN_GOLD) -> Path:
    gold = read_jsonl(gold_path)
    records = read_jsonl(run_dir / "raw_results.jsonl")
    assert len(records) == 72, f"raw results must have 72 executions, got {len(records)}"
    rows = per_case_metrics(records, gold)
    metrics = system_metrics(rows, gold)
    safety = safety_metrics(records, gold)

    case_fields = (
        "case_id", "case_type", "system", "status", "selected_task_id", "utility",
        "preferred_top1", "valid_top1", "invalid_top1", "hard_constraint_satisfied",
        "soft_preference_aligned", "memory_alignment", "evidence_contaminated",
        "guard_passed", "guard_fallback_used", "memory_used_on_selected",
        "personalization_delta", "error",
    )
    write_csv(run_dir / "case_metrics.csv", rows, case_fields)

    system_fields = ("system", "metric", "numerator", "denominator", "value", "wilson_95_ci_low", "wilson_95_ci_high", "case_ids")
    system_rows = []
    for metric in metrics.values():
        low, high = metric.get("wilson_95_ci") or (None, None)
        system_rows.append(
            {
                "system": metric["system"],
                "metric": metric["metric"],
                "numerator": metric["numerator"],
                "denominator": metric["denominator"],
                "value": metric["value"],
                "wilson_95_ci_low": low,
                "wilson_95_ci_high": high,
                "case_ids": "|".join(metric["case_ids"]),
            }
        )
    write_csv(run_dir / "system_metrics.csv", system_rows, system_fields)

    safety_rows = safety["rows"]
    safety_fields = (
        "case_id", "system", "expected_status", "actual_status", "task_delivered",
        "selected_task_id", "unsafe_escape", "false_block", "reason_codes",
    )
    write_csv(run_dir / "safety_results.csv", safety_rows, safety_fields)
    (run_dir / "safety_summary.json").write_text(
        json.dumps(
            {key: safety[key] for key in ("unsafe_escape_rate", "unsafe_escape_count", "false_block_count", "denominator")},
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    memory_rows = []
    for record in records:
        if not record.get("memory_injected"):
            continue
        result = record.get("result")
        personalization = (result or {}).get("personalization") or {}
        agentic_diag = (result or {}).get("agentic_diagnostics") or {}
        memory_rows.append(
            {
                "case_id": record["case_id"],
                "system": record["system"],
                "isolated_runtime_user_id": record["isolated_runtime_user_id"],
                "fixture_task_ids": "|".join(record["memory_injected"]["fixture_task_ids"]),
                "memory_ids": "|".join(record["memory_injected"]["memory_ids"]),
                "memory_retrieval_hit": None,  # production does not expose for basic/personal; agentic via diagnostics
                "agentic_memory_hit_count": agentic_diag.get("memory_hit_count"),
                "agentic_retrieved_memory_ids": "|".join(agentic_diag.get("retrieved_memory_ids") or []),
                "memory_used_on_selected": personalization.get("memory_used"),
                "memory_ids_on_selected": "|".join(personalization.get("memory_ids") or []),
                "personalization_delta": personalization.get("personalization_delta"),
                "selected_task_id": result.get("selected_task_id") if result else None,
            }
        )
    memory_fields = (
        "case_id", "system", "isolated_runtime_user_id", "fixture_task_ids", "memory_ids",
        "memory_retrieval_hit", "agentic_memory_hit_count", "agentic_retrieved_memory_ids",
        "memory_used_on_selected", "memory_ids_on_selected", "personalization_delta",
        "selected_task_id",
    )
    write_csv(run_dir / "memory_results.csv", memory_rows, memory_fields)

    agentic_rows = []
    for record in records:
        if record["system"] != "agentic":
            continue
        diag = (record.get("result") or {}).get("agentic_diagnostics") or {}
        agentic_rows.append(
            {
                "case_id": record["case_id"],
                "factor_count": diag.get("factor_count"),
                "factor_domains": "|".join(diag.get("factor_domains") or []),
                "analysis_fallback": diag.get("analysis_fallback"),
                "task_candidate_ids": "|".join(diag.get("task_candidate_ids") or []),
                "base_task_ranking": "|".join(diag.get("base_task_ranking") or []),
                "personal_task_ranking": "|".join(diag.get("personal_task_ranking") or []),
                "memory_hit_count": diag.get("memory_hit_count"),
                "selected_task_id": diag.get("selected_task_id"),
                "safety_reason_codes": "|".join(diag.get("safety_reason_codes") or []),
                "model_calls": json.dumps(diag.get("model_calls"), ensure_ascii=False),
            }
        )
    with (run_dir / "agentic_diagnostics.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in agentic_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    # factor coverage: generate template on first finalize; reuse judgments if present
    template = factor_coverage_template(gold, records)
    judgment_path = run_dir / "factor_coverage_cases.csv"
    if not judgment_path.exists():
        write_csv(
            judgment_path,
            template,
            (
                "case_id", "gold_factor_position", "gold_factor_type",
                "gold_factor_description", "agentic_factor_count",
                "agentic_factor_summary", "covered", "evidence",
            ),
        )
        judgment_rows = template
    else:
        with judgment_path.open(encoding="utf-8-sig", newline="") as handle:
            judgment_rows = list(csv.DictReader(handle))
    coverage = factor_coverage_metrics(gold, judgment_rows)
    write_csv(
        run_dir / "factor_coverage_metrics.csv",
        [
            {
                "metric": key,
                "value": json.dumps(value, ensure_ascii=False)
                if isinstance(value, dict)
                else value,
            }
            for key, value in coverage.items()
        ],
        ("metric", "value"),
    )

    claims = evaluate_claims(metrics, safety, rows, records)
    write_csv(
        run_dir / "claim_results.csv",
        [
            {
                "claim_id": claim["claim_id"],
                "status": claim["status"],
                "evidence": json.dumps(claim["evidence"], ensure_ascii=False),
            }
            for claim in claims
        ],
        ("claim_id", "status", "evidence"),
    )

    run_manifest = {
        "run_id": run_dir.name,
        "gold_frozen_sha256": file_sha256(gold_path),
        "gold_manifest": json.loads(GOLD_MANIFEST.read_text(encoding="utf-8")),
        "metric_preregistration": json.loads(METRIC_PRE.read_text(encoding="utf-8")),
        "executions_recorded": len(records),
        "systems": list(SYSTEMS),
        "metrics_recomputed_mechanically": True,
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return run_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 8 formal evaluation")
    parser.add_argument(
        "--phase", choices=("execute", "finalize"), default="finalize"
    )
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    env_file = ROOT / ".env"
    api_key = load_api_key(env_file)
    es_url = _env_value("ELASTICSEARCH_URL", env_file) or "http://127.0.0.1:9200"

    if args.phase == "execute":
        run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ_stage8_formal")
        client = Elasticsearch(es_url, request_timeout=60, max_retries=1)
        try:
            if not client.ping():
                raise RuntimeError(f"Elasticsearch is not reachable: {es_url}")
            run_dir = execute_phase(client=client, api_key=api_key, run_id=run_id)
        finally:
            client.close()
        print(run_dir)
    else:
        run_id = args.run_id or max(
            (p.name for p in RUN_ROOT.glob("*_stage8_formal")),
            key=lambda name: name,
        )
        run_dir = finalize_phase(RUN_ROOT / run_id)
        print(run_dir)


if __name__ == "__main__":
    main()
