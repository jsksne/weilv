"""Fixed, loop-free Stage 7A Agentic RAG nodes over the frozen production core."""

import json
from copy import deepcopy
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from weilv.basic_rag import (
    BasicRagRequest,
    _empty_result,
    _knowledge_filters,
    _matches_task_metadata,
    _safety_context,
    _selected_task,
    _sources,
    _task_document,
    load_formal_task_identities,
    load_task_evidence,
)
from weilv.collaborative_ranking import apply_cf_to_ranking
from weilv.dashscope_models import (
    compose_agentic_explanation,
    decompose_problem,
    embed_texts,
    rerank_texts,
)
from weilv.micro_tasks import load_formal_micro_tasks
from weilv.output_guard import validate_explanation_output
from weilv.personal_memory_retrieval import retrieve_personal_memories
from weilv.personal_rag import personalize_task_candidates
from weilv.retrieval import apply_rerank, bm25_search, merge_candidates, vector_search
from weilv.safety_rules import evaluate_input_risk, load_safety_rules, select_safe_tasks
from weilv.user_memory import get_user_profile

DomainHint = Literal[
    "sedentary",
    "eye_health",
    "outdoor",
    "physical_activity",
    "sleep",
    "study_break",
    "light_recovery",
]

SAFE_EXPLANATION_FALLBACK = (
    "该任务来自已审核的健康知识，并已通过当前学段、场景和安全条件筛选。"
    "请按任务卡中的原始指令执行。"
)


class Factor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factor_id: str = Field(pattern=r"^F[1-4]$")
    domain_hint: DomainHint | None
    subquery: str = Field(min_length=1)
    evidence_need: str = Field(min_length=1)


class ProblemAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_complex: bool
    factors: list[Factor] = Field(min_length=1, max_length=4)


class AgenticState(TypedDict, total=False):
    request: BasicRagRequest
    user_id: str
    safety_status: str
    safety_matched_rule_ids: list[str]
    safety_reason_codes: list[str]
    analysis_status: str
    analysis_fallback: bool
    factors: list[dict[str, Any]]
    knowledge_by_factor: dict[str, list[dict]]
    knowledge_contexts: list[dict]
    task_candidate_ids: list[str]
    base_task_ranking: list[dict]
    original_query_embedding: list[float]
    retrieved_memories: list[dict]
    retrieved_memory_ids: list[str]
    personalization_delta_by_task: dict[str, int]
    personal_task_ranking: list[dict]
    selected_task: dict | None
    task_evidence: list[dict]
    response_text: str | None
    guard_status: str | None
    diagnostics: dict[str, Any]
    result: dict[str, Any]


def initial_diagnostics() -> dict[str, Any]:
    return {
        "agentic": True,
        "factor_count": 0,
        "factor_domains": [],
        "analysis_fallback": False,
        "knowledge_chunk_ids_by_factor": {},
        "knowledge_trace_by_factor": {},
        "task_candidate_ids": [],
        "base_task_ranking": [],
        "personal_task_ranking": [],
        "memory_hit_count": 0,
        "selected_task_id": None,
        "safety_reason_codes": [],
        "model_calls": {
            "decomposition": 0,
            "knowledge_embedding": 0,
            "knowledge_rerank": 0,
            "task_embedding": 0,
            "task_rerank": 0,
            "memory_embedding": 0,
            "memory_rerank": 0,
            "explanation": 0,
        },
    }


def _diagnostics(state: AgenticState) -> dict[str, Any]:
    return deepcopy(state.get("diagnostics") or initial_diagnostics())


def _fallback_factor(query: str) -> list[dict[str, Any]]:
    return [
        {
            "factor_id": "F1",
            "domain_hint": None,
            "subquery": query,
            "evidence_need": "general",
        }
    ]


PUBLIC_RAG_EXCERPT_CHARS = 420
PUBLIC_RAG_CHUNKS_PER_FACTOR = 2


def _public_excerpt(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= PUBLIC_RAG_EXCERPT_CHARS:
        return text
    return text[: PUBLIC_RAG_EXCERPT_CHARS - 1].rstrip() + "…"


def _public_rag_trace(state: AgenticState) -> dict[str, Any]:
    # Display-only projection. Never expose scores/ranks/embeddings/prompts/Memory.
    analysis_fallback = bool(state.get("analysis_fallback"))
    factors: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    knowledge_by_factor = state.get("knowledge_by_factor") or {}

    for factor in state.get("factors") or []:
        factor_id = str(factor.get("factor_id") or "")
        if not factor_id:
            continue
        if not analysis_fallback:
            factors.append(
                {
                    "factor_id": factor_id,
                    "subquery": str(factor.get("subquery") or ""),
                    "evidence_need": str(factor.get("evidence_need") or ""),
                    "domain_hint": factor.get("domain_hint"),
                }
            )
        visible_count = 0
        for item in knowledge_by_factor.get(factor_id, []):
            if visible_count >= PUBLIC_RAG_CHUNKS_PER_FACTOR:
                break
            if item.get("review_status") != "content_reviewed":
                continue
            excerpt = _public_excerpt(item.get("content"))
            chunk_id = str(item.get("chunk_id") or "")
            if not chunk_id or not excerpt:
                continue
            chunks.append(
                {
                    "factor_id": factor_id,
                    "chunk_id": chunk_id,
                    "source_locator": str(item.get("source_locator") or "审核知识库"),
                    "source_url": item.get("source_url") or None,
                    "excerpt": excerpt,
                }
            )
            visible_count += 1

    return {
        "analysis_fallback": analysis_fallback,
        "factors": factors,
        "knowledge_chunks": chunks,
    }


class AgenticRagRuntime:
    def __init__(
        self,
        request: BasicRagRequest,
        user_id: str,
        client,
        api_key: str,
        knowledge_index: str = "health_knowledge_v1",
        task_index: str = "micro_tasks_v1",
        cf_provider=None,
    ) -> None:
        self.request = request
        self.user_id = user_id
        self.client = client
        self.api_key = api_key
        self.knowledge_index = knowledge_index
        self.task_index = task_index
        self.rules = load_safety_rules()
        # Stage 9B CF exact-tie provider; None (production default) is a strict
        # no-op.  HeartSteps scores must never be passed here.
        self.cf_provider = cf_provider

    def input_safety(self, state: AgenticState) -> dict[str, Any]:
        result = evaluate_input_risk(_safety_context(self.request), self.rules)
        diagnostics = _diagnostics(state)
        diagnostics["safety_reason_codes"] = result["reason_codes"]
        return {
            "safety_status": result["status"],
            "safety_matched_rule_ids": result["matched_rule_ids"],
            "safety_reason_codes": result["reason_codes"],
            "diagnostics": diagnostics,
        }

    def terminal_response(self, state: AgenticState) -> dict[str, Any]:
        result = _empty_result(
            {
                "status": state["safety_status"],
                "matched_rule_ids": state["safety_matched_rule_ids"],
                "reason_codes": state["safety_reason_codes"],
            }
        )
        result["diagnostics"] = state["diagnostics"]
        result["agentic"] = True
        return {"result": result}

    def analyze_problem(self, state: AgenticState) -> dict[str, Any]:
        diagnostics = _diagnostics(state)
        diagnostics["model_calls"]["decomposition"] += 1
        fallback = False
        try:
            raw = decompose_problem(self.request.query, self.api_key)
            analysis = ProblemAnalysis.model_validate(json.loads(raw))
            factor_ids = [factor.factor_id for factor in analysis.factors]
            if factor_ids != [f"F{position}" for position in range(1, len(factor_ids) + 1)]:
                raise ValueError("factor IDs must be ordered and contiguous")
            factors = [factor.model_dump() for factor in analysis.factors]
        except (json.JSONDecodeError, TypeError, ValueError, ValidationError):
            factors = _fallback_factor(self.request.query)
            fallback = True
        diagnostics.update(
            factor_count=len(factors),
            factor_domains=[factor["domain_hint"] for factor in factors],
            analysis_fallback=fallback,
        )
        return {
            "analysis_status": "fallback" if fallback else "parsed",
            "analysis_fallback": fallback,
            "factors": factors,
            "diagnostics": diagnostics,
        }

    def retrieve_factor_knowledge(self, state: AgenticState) -> dict[str, Any]:
        diagnostics = _diagnostics(state)
        knowledge_by_factor: dict[str, list[dict]] = {}
        deduped: dict[str, dict] = {}
        for factor in state["factors"]:
            query = factor["subquery"]
            query_vector = embed_texts([query], self.api_key, "query")[0]
            diagnostics["model_calls"]["knowledge_embedding"] += 1
            bm25 = bm25_search(
                self.client,
                query,
                self.knowledge_index,
                raw_filters=_knowledge_filters(),
            )
            vector = vector_search(
                self.client,
                query_vector,
                self.knowledge_index,
                raw_filters=_knowledge_filters(),
            )
            candidates = merge_candidates(bm25, vector)
            reranked = (
                apply_rerank(
                    candidates,
                    rerank_texts(
                        query,
                        [candidate["content"] for candidate in candidates],
                        self.api_key,
                    ),
                )
                if candidates
                else []
            )
            if candidates:
                diagnostics["model_calls"]["knowledge_rerank"] += 1
            selected = reranked[:5]
            factor_id = factor["factor_id"]
            knowledge_by_factor[factor_id] = selected
            diagnostics["knowledge_chunk_ids_by_factor"][factor_id] = [
                item["chunk_id"] for item in selected
            ]
            diagnostics["knowledge_trace_by_factor"][factor_id] = {
                "candidate_ids": [item["chunk_id"] for item in candidates],
                "reranked_ids": [item["chunk_id"] for item in reranked],
                "selected_ids": [item["chunk_id"] for item in selected],
            }
            for item in selected:
                deduped.setdefault(item["chunk_id"], item)
        return {
            "knowledge_by_factor": knowledge_by_factor,
            "knowledge_contexts": list(deduped.values()),
            "diagnostics": diagnostics,
        }

    def retrieve_agentic_tasks(self, state: AgenticState) -> dict[str, Any]:
        diagnostics = _diagnostics(state)
        queries = [self.request.query, *[factor["subquery"] for factor in state["factors"]]]
        formal_ids = {task["task_id"] for task in load_formal_micro_tasks()}
        union: dict[str, dict] = {}
        original_embedding: list[float] = []
        recall_trace = []
        task_filters = [{"term": {"review_status": "content_reviewed"}}]
        for position, query in enumerate(queries):
            query_vector = embed_texts([query], self.api_key, "query")[0]
            diagnostics["model_calls"]["task_embedding"] += 1
            if position == 0:
                original_embedding = query_vector
            bm25 = bm25_search(
                self.client,
                query,
                self.task_index,
                raw_filters=task_filters,
                search_fields=["title^2", "instruction", "trigger", "domain", "context_tags"],
            )
            vector = vector_search(
                self.client,
                query_vector,
                self.task_index,
                raw_filters=task_filters,
            )
            recalled = merge_candidates(bm25, vector, identity_field="task_id")
            recall_trace.append([task["task_id"] for task in recalled if task["task_id"] in formal_ids])
            for task in recalled:
                if task["task_id"] in formal_ids:
                    union.setdefault(task["task_id"], task)

        metadata_tasks = [
            task for task in union.values() if _matches_task_metadata(task, self.request)
        ]
        safe_result = select_safe_tasks(metadata_tasks, _safety_context(self.request), self.rules)
        diagnostics["task_recall_ids_by_query"] = recall_trace
        if safe_result["status"] != "allowed":
            diagnostics["safety_reason_codes"] = safe_result["reason_codes"]
            return {
                "safety_status": safe_result["status"],
                "safety_matched_rule_ids": safe_result["matched_rule_ids"],
                "safety_reason_codes": safe_result["reason_codes"],
                "task_candidate_ids": [],
                "base_task_ranking": [],
                "original_query_embedding": original_embedding,
                "diagnostics": diagnostics,
            }

        eligible = safe_result["tasks"]
        composite_query = self.request.query + "\n\n关键因素：\n" + "\n".join(
            factor["subquery"] for factor in state["factors"]
        )
        reranked = apply_rerank(
            eligible,
            rerank_texts(
                composite_query,
                [_task_document(task) for task in eligible],
                self.api_key,
            ),
        )
        diagnostics["model_calls"]["task_rerank"] += 1
        candidate_ids = [task["task_id"] for task in eligible]
        diagnostics["task_candidate_ids"] = candidate_ids
        diagnostics["base_task_ranking"] = [task["task_id"] for task in reranked]
        diagnostics["safety_reason_codes"] = safe_result["reason_codes"]
        return {
            "safety_status": "allowed",
            "safety_matched_rule_ids": safe_result["matched_rule_ids"],
            "safety_reason_codes": safe_result["reason_codes"],
            "task_candidate_ids": candidate_ids,
            "base_task_ranking": reranked,
            "original_query_embedding": original_embedding,
            "diagnostics": diagnostics,
        }

    def retrieve_user_memory(self, state: AgenticState) -> dict[str, Any]:
        if state.get("safety_status") != "allowed":
            return {}
        diagnostics = _diagnostics(state)
        profile = get_user_profile(self.client, self.user_id)
        if profile is None or not profile.memory_enabled:
            diagnostics["memory_hit_count"] = 0
            return {
                "retrieved_memories": [],
                "retrieved_memory_ids": [],
                "diagnostics": diagnostics,
            }
        memories = retrieve_personal_memories(
            self.client,
            profile,
            self.request.query,
            self.api_key,
            query_embedding=state["original_query_embedding"],
        )
        if memories:
            diagnostics["model_calls"]["memory_rerank"] += 1
        diagnostics["memory_hit_count"] = len(memories)
        return {
            "retrieved_memories": memories,
            "retrieved_memory_ids": [memory["memory_id"] for memory in memories],
            "diagnostics": diagnostics,
        }

    def apply_personalization(self, state: AgenticState) -> dict[str, Any]:
        if state.get("safety_status") not in {None, "allowed"}:
            return {}
        base = state.get("base_task_ranking", [])
        if not base:
            return {}
        diagnostics = _diagnostics(state)
        personalized = personalize_task_candidates(base, state.get("retrieved_memories", []))
        before = {task["task_id"] for task in base}
        after = {task["task_id"] for task in personalized}
        if before != after:
            diagnostics["safety_reason_codes"] = ["personalization_candidate_invariance_failed"]
            return {
                "safety_status": "no_safe_task",
                "safety_matched_rule_ids": [],
                "safety_reason_codes": ["personalization_candidate_invariance_failed"],
                "personal_task_ranking": [],
                "diagnostics": diagnostics,
            }
        # Stage 9B CF exact-tie break: after personalization, before selection.
        # Only safety-allowed states reach this point (see the guard above), and
        # the adapter fails closed to the pre-CF order on any anomaly.
        personalized, cf_diagnostics = apply_cf_to_ranking(personalized, self.cf_provider)
        if cf_diagnostics is not None:
            diagnostics["cf"] = cf_diagnostics
        deltas = {
            task["task_id"]: task["personalization"]["personalization_delta"]
            for task in personalized
        }
        diagnostics["personal_task_ranking"] = [task["task_id"] for task in personalized]
        diagnostics["personalization_delta_by_task"] = deltas
        return {
            "personalization_delta_by_task": deltas,
            "personal_task_ranking": personalized,
            "diagnostics": diagnostics,
        }

    def select_and_ground(self, state: AgenticState) -> dict[str, Any]:
        if state.get("safety_status") not in {None, "allowed"}:
            return {}
        ranking = state.get("personal_task_ranking") or state.get("base_task_ranking", [])
        diagnostics = _diagnostics(state)
        if not ranking:
            diagnostics["safety_reason_codes"] = ["no_safe_whitelist_task"]
            return {
                "safety_status": "no_safe_task",
                "safety_matched_rule_ids": ["SR-012"],
                "safety_reason_codes": ["no_safe_whitelist_task"],
                "diagnostics": diagnostics,
            }
        selected_task = _selected_task(ranking[0])
        evidence = load_task_evidence(self.client, selected_task, self.knowledge_index)
        if [item["chunk_id"] for item in evidence] != selected_task["evidence_chunk_ids"]:
            diagnostics["safety_reason_codes"] = ["selected_task_evidence_invalid"]
            return {
                "safety_status": "no_safe_task",
                "safety_matched_rule_ids": [],
                "safety_reason_codes": ["selected_task_evidence_invalid"],
                "selected_task": None,
                "task_evidence": [],
                "diagnostics": diagnostics,
            }
        diagnostics["selected_task_id"] = selected_task["task_id"]
        return {
            "selected_task": selected_task,
            "task_evidence": evidence,
            "diagnostics": diagnostics,
        }

    def compose_explanation(self, state: AgenticState) -> dict[str, Any]:
        if state.get("safety_status") != "allowed" or not state.get("selected_task"):
            return {}
        diagnostics = _diagnostics(state)
        top = (state.get("personal_task_ranking") or [{}])[0]
        personalization = top.get("personalization")
        if not personalization or personalization["personalization_delta"] == 0:
            personalization = None
        explanation = compose_agentic_explanation(
            self.request.query,
            state["factors"],
            state["selected_task"],
            state["task_evidence"],
            state.get("knowledge_contexts", []),
            personalization,
            self.api_key,
        )
        diagnostics["model_calls"]["explanation"] += 1
        return {"response_text": explanation, "diagnostics": diagnostics}

    def output_guard(self, state: AgenticState) -> dict[str, Any]:
        if state.get("safety_status") != "allowed" or not state.get("selected_task"):
            result = _empty_result(
                {
                    "status": state.get("safety_status", "no_safe_task"),
                    "matched_rule_ids": state.get("safety_matched_rule_ids", []),
                    "reason_codes": state.get("safety_reason_codes", []),
                }
            )
            result.update(agentic=True, diagnostics=state["diagnostics"])
            return {"guard_status": None, "result": result}

        guard = validate_explanation_output(
            state["response_text"],
            state["selected_task"],
            state["task_evidence"],
            load_formal_task_identities(self.client, self.task_index),
        )
        fallback_used = not guard["passed"]
        explanation = SAFE_EXPLANATION_FALLBACK if fallback_used else state["response_text"]
        result = {
            "status": "allowed",
            "selected_task": state["selected_task"],
            "explanation": explanation,
            "sources": _sources(state["task_evidence"]),
            "context_sources": _sources(state.get("knowledge_contexts", [])),
            "public_rag": _public_rag_trace(state),
            "matched_rule_ids": state.get("safety_matched_rule_ids", []),
            "reason_codes": state.get("safety_reason_codes", []),
            "explanation_guard": {
                "passed": guard["passed"],
                "fallback_used": fallback_used,
                "reason_codes": guard["reason_codes"],
            },
            "agentic": True,
            "diagnostics": state["diagnostics"],
        }
        top = (state.get("personal_task_ranking") or [{}])[0]
        if top.get("personalization"):
            result["personalization"] = top["personalization"]
        return {
            "guard_status": "accepted" if guard["passed"] else "rejected",
            "result": result,
        }


def run_agentic_rag(
    request: BasicRagRequest,
    user_id: str,
    client,
    api_key: str,
    knowledge_index: str = "health_knowledge_v1",
    task_index: str = "micro_tasks_v1",
    cf_provider=None,
) -> dict[str, Any]:
    from weilv.agent_graph import build_agent_graph

    runtime = AgenticRagRuntime(
        request,
        user_id,
        client,
        api_key,
        knowledge_index=knowledge_index,
        task_index=task_index,
        cf_provider=cf_provider,
    )
    state = build_agent_graph(runtime).invoke(
        {"request": request, "user_id": user_id, "diagnostics": initial_diagnostics()}
    )
    return state["result"]
