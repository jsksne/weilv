"""B3: public agentic observable trace.

Single-execution observability for the Agentic pipeline.

The compiled LangGraph is run once via ``astream_events``; node *start*
events are translated into coarse, sanitized public trace events.  Nothing
internal (prompts, reasoning, raw retrieval candidates, scores, embeddings,
diagnostics, secrets) ever leaves the backend. Reviewed knowledge excerpts may
leave only through the explicit ``public_rag`` allowlist. The final response is
allowlist-sanitized before being attached to the completed event.
"""

from collections.abc import AsyncIterator, Mapping
from typing import Any

from weilv.agent_graph import build_agent_graph
from weilv.agentic_rag import AgenticRagRuntime, _public_rag_trace, initial_diagnostics
from weilv.basic_rag import BasicRagRequest

# Real LangGraph node name -> coarse public stage (fixed pipeline order).
NODE_STAGE: Mapping[str, str] = {
    "input_safety": "safety",
    "analyze_problem": "analysis",
    "retrieve_factor_knowledge": "retrieval",
    "retrieve_agentic_tasks": "ranking",
    "apply_personalization": "personalization",
    "select_and_ground": "grounding",
    "compose_explanation": "generation",
}

# Terminal nodes that only complete a path and add no user-facing stage.
# (terminal_response = safety-blocked completion; output_guard = final check.)
_TERMINAL_NODES = frozenset({"terminal_response", "output_guard"})

STAGE_LABELS: Mapping[str, str] = {
    "accepted": "正在理解你的需求",
    "safety": "正在进行安全检查",
    "analysis": "正在理解你的需求",
    "retrieval": "正在检索相关健康知识",
    "ranking": "正在匹配适合的信息",
    "memory": "正在结合你的历史情况",
    "personalization": "正在匹配适合的信息",
    "grounding": "正在核对信息",
    "generation": "正在整理建议",
    "completed": "处理完成",
    "error": "暂时无法完成，请稍后重试",
}

# Allowlist for the final response attached to the completed event.  Internal
# fields (diagnostics, ranking traces, model call counts, candidate ids)
# must never cross this boundary.
RESULT_ALLOWLIST = (
    "status",
    "selected_task",
    "explanation",
    "sources",
    "context_sources",
    "public_rag",
    "matched_rule_ids",
    "reason_codes",
    "explanation_guard",
    "personalization",
    "agentic",
)


PUBLIC_RAG_FACTOR_FIELDS = frozenset({"factor_id", "subquery", "evidence_need", "domain_hint"})
PUBLIC_RAG_CHUNK_FIELDS = frozenset({"factor_id", "chunk_id", "source_locator", "source_url", "excerpt"})


def _project_mapping(value: Any, fields: frozenset[str]) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return {key: value[key] for key in fields if key in value}


def _sanitize_public_rag(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"analysis_fallback": False, "factors": [], "knowledge_chunks": []}
    factors = [
        projected
        for item in value.get("factors", [])
        if (projected := _project_mapping(item, PUBLIC_RAG_FACTOR_FIELDS)) is not None
    ]
    chunks = [
        projected
        for item in value.get("knowledge_chunks", [])
        if (projected := _project_mapping(item, PUBLIC_RAG_CHUNK_FIELDS)) is not None
    ]
    return {
        "analysis_fallback": bool(value.get("analysis_fallback", False)),
        "factors": factors,
        "knowledge_chunks": chunks,
    }


def sanitize_final_response(result: Mapping[str, Any]) -> dict[str, Any]:
    """Allowlist-filter the final agentic result for public transport."""
    public = {key: value for key, value in result.items() if key in RESULT_ALLOWLIST}
    if "public_rag" in public:
        public["public_rag"] = _sanitize_public_rag(public["public_rag"])
    return public


def translate_graph_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Map one ``astream_events`` event to a public trace event, or ``None``.

    Only node *start* events for non-terminal nodes are exposed.  Terminal
    nodes and root events are skipped here; the caller derives the final
    result from the root ``on_chain_end`` event.
    """
    node = (event.get("metadata") or {}).get("langgraph_node")
    if not node or node in _TERMINAL_NODES or event.get("event") != "on_chain_start":
        return None
    stage = NODE_STAGE.get(node)
    if stage is None:
        return None
    return {"stage": stage, "status": "active", "label": STAGE_LABELS[stage]}


def public_stage_result(stage: str, state: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return only the reviewed public content produced by a completed stage."""
    public = _public_rag_trace(state)
    if stage == "analysis":
        return {
            "analysis": {
                "analysis_fallback": public["analysis_fallback"],
                "factors": public["factors"],
            }
        }
    if stage == "retrieval":
        return {"retrieval": {"knowledge_chunks": public["knowledge_chunks"]}}
    return None


async def iter_agentic_graph_events(
    request: BasicRagRequest,
    user_id: str,
    client,
    api_key: str,
    knowledge_index: str = "health_knowledge_v1",
    task_index: str = "micro_tasks_v1",
    cf_provider=None,
) -> AsyncIterator[dict[str, Any]]:
    """Run the compiled Agentic graph exactly once and yield raw graph events.

    This is the same graph and the same semantics as ``run_agentic_rag``;
    only the execution surface changes (``astream_events`` vs ``invoke``).
    """
    runtime = AgenticRagRuntime(
        request,
        user_id,
        client,
        api_key,
        knowledge_index=knowledge_index,
        task_index=task_index,
        cf_provider=cf_provider,
    )
    graph = build_agent_graph(runtime)
    async for event in graph.astream_events(
        {"request": request, "user_id": user_id, "diagnostics": initial_diagnostics()},
        version="v2",
    ):
        yield event
