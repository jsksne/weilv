"""Stage 4 Personal RAG v0.1 over safety-approved task candidates."""

from collections.abc import Callable
from typing import Any

from weilv.basic_rag import (
    BasicRagRequest,
    _basic_result_from_pipeline,
    _finalize_selected_task,
    _run_basic_pipeline,
    _selected_task,
    _surfaced_tasks,
)
from weilv.collaborative_ranking import apply_cf_to_ranking
from weilv.personal_memory_retrieval import retrieve_personal_memories
from weilv.user_memory import get_user_profile


def _memory_adjustment(memory: dict[str, Any]) -> tuple[int, list[str]]:
    value = memory.get("memory_value", {})
    if memory.get("memory_type") == "task_preference":
        preference = value.get("preference") or memory.get("memory_key")
        if preference == "prefer_task":
            return 3, ["preferred_task"]
        if preference == "avoid_task":
            return -3, ["avoided_task"]
        return 0, []
    if memory.get("memory_type") != "task_feedback":
        return 0, []

    delta = 0
    reasons = []
    helpfulness = value.get("helpfulness")
    if isinstance(helpfulness, int) and helpfulness >= 4:
        delta += 2
        reasons.append("helpful_task")
    elif isinstance(helpfulness, int) and helpfulness <= 2:
        delta -= 2
        reasons.append("unhelpful_task")
    if value.get("completion_status") == "completed":
        delta += 1
        reasons.append("completed_task")
    elif value.get("completion_status") == "skipped":
        delta -= 1
        reasons.append("skipped_task")
    if value.get("burden") == "easy":
        delta += 1
        reasons.append("easy_task")
    elif value.get("burden") == "hard":
        delta -= 1
        reasons.append("hard_task")
    return delta, reasons


def personalize_task_candidates(
    tasks: list[dict[str, Any]], memories: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    personalized = []
    for position, task in enumerate(tasks, start=1):
        base_rank = task.get("rerank_rank", position)
        delta = 0
        memory_ids = []
        reasons = []
        for memory in memories:
            if memory.get("task_id") != task["task_id"]:
                continue
            adjustment, memory_reasons = _memory_adjustment(memory)
            if not memory_reasons:
                continue
            delta += adjustment
            memory_ids.append(memory["memory_id"])
            reasons.extend(memory_reasons)
        delta = max(-5, min(5, delta))
        adjusted_rank = base_rank - delta
        personalized.append(
            {
                **task,
                "personalization": {
                    "memory_used": bool(memory_ids),
                    "memory_ids": memory_ids,
                    "base_task_rank": base_rank,
                    "personalization_delta": delta,
                    "adjusted_rank": adjusted_rank,
                    "reason_codes": reasons,
                },
            }
        )
    return sorted(
        personalized,
        key=lambda task: (
            task["personalization"]["adjusted_rank"],
            task["personalization"]["base_task_rank"],
            task["task_id"],
        ),
    )


def run_personal_rag(
    request: BasicRagRequest,
    user_id: str,
    client,
    api_key: str,
    knowledge_index: str = "health_knowledge_v1",
    task_index: str = "micro_tasks_v1",
    cf_provider: Callable[[list[str]], dict[str, dict[str, Any]]] | None = None,
) -> dict:
    """Personal RAG with the optional Stage 9B CF exact-tie break.

    ``cf_provider`` defaults to None: the production behavior is a strict no-op
    (neutral).  When provided, CF runs only after personalization (which itself
    only runs on safety-allowed states) and only reorders exact adjusted_rank
    ties; any failure returns the pre-CF order.
    """
    pipeline = _run_basic_pipeline(
        request,
        client,
        api_key,
        knowledge_index=knowledge_index,
        task_index=task_index,
    )
    if pipeline["result"] is not None:
        return pipeline["result"]

    profile = get_user_profile(client, user_id)
    if profile is None or not profile.memory_enabled:
        return _basic_result_from_pipeline(
            request, pipeline, client, api_key, knowledge_index, task_index
        )

    memories = retrieve_personal_memories(
        client,
        profile,
        request.query,
        api_key,
        query_embedding=pipeline["query_embedding"],
    )
    personalized = personalize_task_candidates(pipeline["reranked_tasks"], memories)
    personalized, cf_diagnostics = apply_cf_to_ranking(personalized, cf_provider)
    if getattr(request, "prefer_easy_start", False):
        from weilv.basic_rag import apply_easy_start_ordering

        personalized = apply_easy_start_ordering(personalized)
    selected_task = _selected_task(personalized[0])
    result = _finalize_selected_task(
        request,
        selected_task,
        pipeline,
        client,
        api_key,
        knowledge_index,
        task_index,
    )
    if result["status"] == "allowed":
        result["personalization"] = personalized[0]["personalization"]
        if cf_diagnostics is not None:
            result["cf"] = cf_diagnostics
        result["tasks"] = _surfaced_tasks(personalized, result, client, knowledge_index)
    return result
