"""Stage 3 Basic RAG orchestration over reviewed knowledge and micro-tasks."""

from dataclasses import asdict, dataclass
from typing import Literal

from weilv.dashscope_models import embed_texts, explain_selected_task, rerank_texts
from weilv.output_guard import validate_explanation_output
from weilv.retrieval import apply_rerank, bm25_search, merge_candidates, vector_search
from weilv.safety_rules import evaluate_input_risk, load_safety_rules, select_safe_tasks

TargetStage = Literal["primary_upper", "junior_high", "senior_high"]
CurrentContext = Literal[
    "home", "school", "study_space", "commute", "bedroom", "outdoor", "unknown"
]
ActivityContext = Literal["reading", "writing", "screen", "other", "unknown"]


@dataclass(frozen=True)
class BasicRagRequest:
    query: str
    target_stage: TargetStage
    current_context: CurrentContext
    available_minutes: int | None = None
    activity_context: ActivityContext = "unknown"
    vision_abnormal: bool = False
    physical_discomfort: bool = False
    medical_request: bool = False
    cannot_move: bool = False
    unstable_environment: bool = False
    sleep_being_crowded: bool = False
    """F1：最近会话轮次（仅 Agentic 理解环节消费，非 Memory）。"""
    conversation_history: list[dict[str, str]] | None = None
    """日程结构化事实（仅 kind/busy_level，名称绝不进入）。"""
    schedule_events: list[dict[str, str]] | None = None
    """易启动：用户表达“不想动/轻一点”后，在安全候选内优先短任务。"""
    prefer_easy_start: bool = False

    def __post_init__(self) -> None:
        if self.target_stage not in {"primary_upper", "junior_high", "senior_high"}:
            raise ValueError("unsupported target_stage")


def _safety_context(request: BasicRagRequest) -> dict:
    context = asdict(request)
    if request.current_context == "unknown":
        context["current_context"] = None
    context["unstable_reading_or_screen"] = (
        request.unstable_environment
        and request.activity_context in {"reading", "writing", "screen"}
    )
    context["sleep_displaced_by_study"] = request.sleep_being_crowded
    return context


def _empty_result(status_result: dict) -> dict:
    return {
        "status": status_result["status"],
        "selected_task": None,
        "explanation": None,
        "sources": [],
        "matched_rule_ids": status_result["matched_rule_ids"],
        "reason_codes": status_result["reason_codes"],
    }


def _rerank(query: str, candidates: list[dict], documents: list[str], api_key: str) -> list[dict]:
    if not candidates:
        return []
    return apply_rerank(candidates, rerank_texts(query, documents, api_key))


def _knowledge_filters() -> list[dict]:
    return [
        {"term": {"review_status": "content_reviewed"}},
        {"term": {"proposed_use": "rag_knowledge"}},
        {
            "bool": {
                "must_not": [
                    {"term": {"proposed_use": "exclude_from_normal_recommendation"}}
                ]
            }
        },
    ]


def _task_filters(request: BasicRagRequest) -> list[dict]:
    filters = [
        {"term": {"review_status": "content_reviewed"}},
        {"term": {"target_stage": request.target_stage}},
    ]
    if request.current_context != "unknown":
        filters.append({"term": {"execution_contexts": request.current_context}})
    if request.available_minutes is not None:
        filters.append({"range": {"estimated_minutes": {"lte": request.available_minutes}}})
    return filters


def _matches_task_metadata(task: dict, request: BasicRagRequest) -> bool:
    return (
        task.get("review_status") == "content_reviewed"
        and request.target_stage in task.get("target_stage", [])
        and (
            request.current_context == "unknown"
            or request.current_context in task.get("execution_contexts", [])
        )
        and (
            request.available_minutes is None
            or task.get("estimated_minutes", request.available_minutes + 1)
            <= request.available_minutes
        )
    )


def _task_document(task: dict) -> str:
    values = [
        task.get("title", ""),
        task.get("instruction", ""),
        task.get("trigger", ""),
        task.get("domain", ""),
        *task.get("covered_domains", []),
        *task.get("context_tags", []),
    ]
    return "\n".join(value for value in values if value)


def _selected_task(task: dict) -> dict:
    fields = (
        "task_id",
        "title",
        "instruction",
        "evidence_chunk_ids",
        "covered_domains",
        "estimated_minutes",
    )
    return {field: task[field] for field in fields}


def _surfaced_task_view(task: dict, sources: list[dict]) -> dict:
    """Minimal display fields for one surfaced task; never exposes ranking
    internals such as reranker scores, embeddings or raw query text."""
    return {
        "task_id": task["task_id"],
        "title": task["title"],
        "instruction": task["instruction"],
        "estimated_minutes": task["estimated_minutes"],
        "covered_domains": list(task.get("covered_domains") or []),
        "sources": sources,
    }


def _surfaced_tasks(
    ordered_tasks: list[dict],
    primary_result: dict,
    client,
    knowledge_index: str,
    max_tasks: int = 3,
) -> list[dict]:
    """Expose up to ``max_tasks`` tasks from the same run, in the same order.

    The primary task keeps its exact existing evidence/guard treatment. Ranks
    2+ reuse the same evidence grounding gate (``load_task_evidence`` + exact
    evidence match) and are skipped when they fail; the walk never re-ranks.
    """
    tasks = [
        _surfaced_task_view(primary_result["selected_task"], primary_result.get("sources", []))
    ]
    for task in ordered_tasks[1:]:
        if len(tasks) >= max_tasks:
            break
        candidate = _selected_task(task)
        evidence = load_task_evidence(client, candidate, knowledge_index)
        if [item["chunk_id"] for item in evidence] != candidate["evidence_chunk_ids"]:
            continue
        tasks.append(_surfaced_task_view(candidate, _sources(evidence)))
    return tasks


def _sources(knowledge: list[dict]) -> list[dict]:
    fields = ("chunk_id", "document_id", "source_locator", "source_url")
    return [{field: item[field] for field in fields} for item in knowledge]


def load_task_evidence(client, selected_task: dict, knowledge_index: str) -> list[dict]:
    evidence_ids = selected_task["evidence_chunk_ids"]
    response = client.search(
        index=knowledge_index,
        size=len(evidence_ids),
        query={
            "bool": {
                "filter": [
                    {"terms": {"chunk_id": evidence_ids}},
                    {"term": {"review_status": "content_reviewed"}},
                    {"term": {"proposed_use": "micro_task_evidence"}},
                ]
            }
        },
        source_excludes=["embedding"],
    )
    found = {
        hit["_source"]["chunk_id"]: hit["_source"]
        for hit in response["hits"]["hits"]
        if hit["_source"].get("chunk_id") in evidence_ids
        and hit["_source"].get("review_status") == "content_reviewed"
        and "micro_task_evidence" in hit["_source"].get("proposed_use", [])
    }
    return [found[chunk_id] for chunk_id in evidence_ids if chunk_id in found]


def load_formal_task_identities(client, task_index: str) -> list[dict]:
    response = client.search(
        index=task_index,
        size=100,
        query={"term": {"review_status": "content_reviewed"}},
        source_includes=["task_id", "title"],
    )
    return [hit["_source"] for hit in response["hits"]["hits"]]


def _run_basic_pipeline(
    request: BasicRagRequest,
    client,
    api_key: str,
    knowledge_index: str = "health_knowledge_v1",
    task_index: str = "micro_tasks_v1",
) -> dict:
    rules = load_safety_rules()
    safety_context = _safety_context(request)
    input_result = evaluate_input_risk(safety_context, rules)
    if input_result["status"] in {"blocked", "help_seeking"}:
        return {"result": _empty_result(input_result)}

    query_vector = embed_texts([request.query], api_key=api_key, text_type="query")[0]

    knowledge_bm25 = bm25_search(
        client,
        request.query,
        knowledge_index,
        raw_filters=_knowledge_filters(),
    )
    knowledge_vector = vector_search(
        client,
        query_vector,
        knowledge_index,
        raw_filters=_knowledge_filters(),
    )
    knowledge_candidates = merge_candidates(knowledge_bm25, knowledge_vector)
    knowledge = _rerank(
        request.query,
        knowledge_candidates,
        [candidate["content"] for candidate in knowledge_candidates],
        api_key,
    )[:5]

    task_filters = _task_filters(request)
    task_bm25 = bm25_search(
        client,
        request.query,
        task_index,
        raw_filters=task_filters,
        search_fields=["title^2", "instruction", "trigger", "domain", "context_tags"],
    )
    task_vector = vector_search(
        client,
        query_vector,
        task_index,
        raw_filters=task_filters,
    )
    task_candidates = merge_candidates(task_bm25, task_vector, identity_field="task_id")
    metadata_tasks = [
        task for task in task_candidates if _matches_task_metadata(task, request)
    ]
    safe_result = select_safe_tasks(metadata_tasks, safety_context, rules)
    if safe_result["status"] != "allowed":
        return {"result": _empty_result(safe_result)}

    reranked_tasks = _rerank(
        request.query,
        safe_result["tasks"],
        [_task_document(task) for task in safe_result["tasks"]],
        api_key,
    )
    if not reranked_tasks:
        return {
            "result": _empty_result(
                {
                    "status": "no_safe_task",
                    "matched_rule_ids": ["SR-012"],
                    "reason_codes": ["no_safe_whitelist_task"],
                }
            )
        }

    return {
        "result": None,
        "query_embedding": query_vector,
        "knowledge": knowledge,
        "safe_result": safe_result,
        "reranked_tasks": reranked_tasks,
    }


def _finalize_selected_task(
    request: BasicRagRequest,
    selected_task: dict,
    pipeline: dict,
    client,
    api_key: str,
    knowledge_index: str,
    task_index: str,
) -> dict:
    task_evidence = load_task_evidence(client, selected_task, knowledge_index)
    if [item["chunk_id"] for item in task_evidence] != selected_task["evidence_chunk_ids"]:
        return _empty_result(
            {
                "status": "no_safe_task",
                "matched_rule_ids": [],
                "reason_codes": ["selected_task_evidence_invalid"],
            }
        )

    explanation = explain_selected_task(request.query, selected_task, task_evidence, api_key=api_key)
    guard = validate_explanation_output(
        explanation,
        selected_task,
        task_evidence,
        load_formal_task_identities(client, task_index),
    )
    fallback_used = not guard["passed"]
    if fallback_used:
        explanation = (
            "该任务来自已审核的健康知识，并已通过当前学段、场景和安全条件筛选。"
            "请按任务卡中的原始指令执行。"
        )
    return {
        "status": "allowed",
        "selected_task": selected_task,
        "explanation": explanation,
        "sources": _sources(task_evidence),
        "context_sources": _sources(pipeline["knowledge"]),
        "matched_rule_ids": pipeline["safe_result"]["matched_rule_ids"],
        "reason_codes": pipeline["safe_result"]["reason_codes"],
        "explanation_guard": {
            "passed": guard["passed"],
            "fallback_used": fallback_used,
            "reason_codes": guard["reason_codes"],
        },
    }


def apply_easy_start_ordering(tasks: list[dict]) -> list[dict]:
    """易启动排序：安全候选不变，仅在候选内把短任务排前（稳定排序）。

    只调整优先级，不做二次筛选、不改写任务内容；关闭时是严格 no-op。
    """
    return sorted(tasks, key=lambda task: task.get("estimated_minutes") or 0)


def _basic_result_from_pipeline(
    request: BasicRagRequest,
    pipeline: dict,
    client,
    api_key: str,
    knowledge_index: str,
    task_index: str,
) -> dict:
    ranking = pipeline["reranked_tasks"]
    if request.prefer_easy_start:
        ranking = apply_easy_start_ordering(ranking)
    result = _finalize_selected_task(
        request,
        _selected_task(ranking[0]),
        pipeline,
        client,
        api_key,
        knowledge_index,
        task_index,
    )
    if result["status"] == "allowed":
        result["tasks"] = _surfaced_tasks(ranking, result, client, knowledge_index)
    return result


def run_basic_rag(
    request: BasicRagRequest,
    client,
    api_key: str,
    knowledge_index: str = "health_knowledge_v1",
    task_index: str = "micro_tasks_v1",
) -> dict:
    pipeline = _run_basic_pipeline(
        request,
        client,
        api_key,
        knowledge_index=knowledge_index,
        task_index=task_index,
    )
    if pipeline["result"] is not None:
        return pipeline["result"]
    return _basic_result_from_pipeline(
        request, pipeline, client, api_key, knowledge_index, task_index
    )
