import json

import pytest

from weilv.basic_rag import BasicRagRequest
from weilv.user_memory import UserProfile


def _request(**changes):
    values = {
        "query": "连续写作业后只剩5分钟，快到睡觉时间，也不想活动",
        "target_stage": "junior_high",
        "current_context": "home",
        "activity_context": "writing",
        "available_minutes": 5,
    }
    values.update(changes)
    return BasicRagRequest(**values)


def _task(task_id="MT-SED-001", *, domain="sedentary", rank=1, minutes=3):
    return {
        "task_id": task_id,
        "title": f"任务 {task_id}",
        "instruction": "闭眼休息3分钟。",
        "trigger": "连续学习后",
        "domain": domain,
        "covered_domains": [domain],
        "context_tags": ["study_break"],
        "target_stage": ["primary_upper", "junior_high", "senior_high"],
        "execution_contexts": ["home", "school", "study_space"],
        "estimated_minutes": minutes,
        "review_status": "content_reviewed",
        "safety_capabilities": ["pause_reading_or_screen"],
        "evidence_chunk_ids": [f"KC-{task_id}"],
        "rerank_rank": rank,
    }


def _knowledge(chunk_id="KC-1"):
    return {
        "chunk_id": chunk_id,
        "document_id": "DOC-1",
        "title": "知识",
        "content": "连续学习后可以安排短暂休息。",
        "source_locator": "第1节",
        "source_url": "https://example.test/doc",
        "review_status": "content_reviewed",
        "proposed_use": ["rag_knowledge", "micro_task_evidence"],
    }


def _runtime(request=None):
    from weilv.agentic_rag import AgenticRagRuntime

    return AgenticRagRuntime(request or _request(), "user-1", object(), "key")


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [({"vision_abnormal": True}, "help_seeking"), ({"medical_request": True}, "blocked")],
)
def test_input_safety_terminates_before_every_agent_or_retrieval_call(
    monkeypatch, overrides, expected_status
):
    import weilv.agentic_rag as agentic

    def forbidden(*_args, **_kwargs):
        raise AssertionError("terminal safety must prevent downstream calls")

    for name in (
        "decompose_problem",
        "embed_texts",
        "bm25_search",
        "vector_search",
        "rerank_texts",
        "get_user_profile",
        "retrieve_personal_memories",
        "compose_agentic_explanation",
    ):
        monkeypatch.setattr(agentic, name, forbidden)

    result = agentic.run_agentic_rag(_request(**overrides), "user-1", object(), "key")

    assert result["status"] == expected_status
    assert result["selected_task"] is None
    assert result["diagnostics"]["model_calls"] == {
        "decomposition": 0,
        "knowledge_embedding": 0,
        "knowledge_rerank": 0,
        "task_embedding": 0,
        "task_rerank": 0,
        "memory_embedding": 0,
        "memory_rerank": 0,
        "explanation": 0,
    }


def test_valid_problem_decomposition_preserves_factor_order(monkeypatch):
    import weilv.agentic_rag as agentic

    payload = {
        "is_complex": True,
        "factors": [
            {
                "factor_id": "F1",
                "domain_hint": "study_break",
                "subquery": "连续学习后的休息需求",
                "evidence_need": "学习间歇证据",
            },
            {
                "factor_id": "F2",
                "domain_hint": "sleep",
                "subquery": "接近平时睡觉时间",
                "evidence_need": "睡眠安排证据",
            },
        ],
    }
    monkeypatch.setattr(agentic, "decompose_problem", lambda *_args, **_kwargs: json.dumps(payload))

    update = _runtime().analyze_problem({"diagnostics": agentic.initial_diagnostics()})

    assert [factor["factor_id"] for factor in update["factors"]] == ["F1", "F2"]
    assert [factor["domain_hint"] for factor in update["factors"]] == [
        "study_break",
        "sleep",
    ]
    assert update["analysis_fallback"] is False
    assert update["diagnostics"]["model_calls"]["decomposition"] == 1


def test_invalid_problem_decomposition_uses_one_deterministic_factor(monkeypatch):
    import weilv.agentic_rag as agentic

    monkeypatch.setattr(agentic, "decompose_problem", lambda *_args, **_kwargs: "not-json")

    update = _runtime().analyze_problem({"diagnostics": agentic.initial_diagnostics()})

    assert update["analysis_fallback"] is True
    assert update["factors"] == [
        {
            "factor_id": "F1",
            "domain_hint": None,
            "subquery": _request().query,
            "evidence_need": "general",
        }
    ]
    assert update["diagnostics"]["model_calls"]["decomposition"] == 1


def test_public_rag_marks_decomposition_fallback_without_exposing_template_factor(monkeypatch):
    import weilv.agentic_rag as agentic

    task = _task()
    evidence = [_knowledge(task["evidence_chunk_ids"][0])]
    knowledge = _knowledge("KC-PUBLIC-1")
    monkeypatch.setattr(
        agentic,
        "validate_explanation_output",
        lambda *_args, **_kwargs: {"passed": True, "reason_codes": []},
    )
    monkeypatch.setattr(agentic, "load_formal_task_identities", lambda *_args, **_kwargs: [task])
    state = {
        "selected_task": task,
        "task_evidence": evidence,
        "response_text": "基于证据的回答 [E1]",
        "safety_status": "allowed",
        "safety_reason_codes": [],
        "safety_matched_rule_ids": [],
        "analysis_fallback": True,
        "factors": [
            {
                "factor_id": "F1",
                "domain_hint": None,
                "subquery": "原问题",
                "evidence_need": "general",
            }
        ],
        "knowledge_by_factor": {"F1": [knowledge]},
        "knowledge_contexts": [knowledge],
        "diagnostics": agentic.initial_diagnostics(),
    }

    public = _runtime().output_guard(state)["result"]["public_rag"]

    assert public["analysis_fallback"] is True
    assert public["factors"] == []
    assert public["knowledge_chunks"][0]["chunk_id"] == "KC-PUBLIC-1"


def test_each_factor_runs_frozen_knowledge_retrieval_and_global_contexts_dedupe(monkeypatch):
    import weilv.agentic_rag as agentic

    calls = {"embed": [], "bm25": [], "vector": [], "rerank": []}
    monkeypatch.setattr(
        agentic,
        "embed_texts",
        lambda texts, *_args, **_kwargs: calls["embed"].append(texts[0]) or [[0.0] * 1024],
    )

    def bm25(_client, query, *_args, **_kwargs):
        calls["bm25"].append(query)
        return [_knowledge("KC-SHARED"), _knowledge(f"KC-B-{len(calls['bm25'])}")]

    def vector(_client, vector_value, *_args, **_kwargs):
        calls["vector"].append(len(vector_value))
        return [_knowledge("KC-SHARED"), _knowledge(f"KC-V-{len(calls['vector'])}")]

    def rerank(query, documents, _api_key):
        calls["rerank"].append((query, len(documents)))
        return [{"index": index, "relevance_score": 1 - index / 10} for index in range(len(documents))]

    monkeypatch.setattr(agentic, "bm25_search", bm25)
    monkeypatch.setattr(agentic, "vector_search", vector)
    monkeypatch.setattr(agentic, "rerank_texts", rerank)
    factors = [
        {"factor_id": "F1", "domain_hint": "study_break", "subquery": "因素一", "evidence_need": "a"},
        {"factor_id": "F2", "domain_hint": "sleep", "subquery": "因素二", "evidence_need": "b"},
    ]

    update = _runtime().retrieve_factor_knowledge(
        {"factors": factors, "diagnostics": agentic.initial_diagnostics()}
    )

    assert calls == {
        "embed": ["因素一", "因素二"],
        "bm25": ["因素一", "因素二"],
        "vector": [1024, 1024],
        "rerank": [("因素一", 3), ("因素二", 3)],
    }
    assert list(update["knowledge_by_factor"]) == ["F1", "F2"]
    assert [item["chunk_id"] for item in update["knowledge_contexts"]].count("KC-SHARED") == 1
    assert update["diagnostics"]["knowledge_chunk_ids_by_factor"]["F1"] == [
        "KC-SHARED",
        "KC-B-1",
        "KC-V-1",
    ]


def test_agentic_task_union_dedupes_and_safety_filter_cannot_resurrect(monkeypatch):
    import weilv.agentic_rag as agentic

    safe = _task()
    blocked = _task("MT-ACT-001", domain="physical_activity")
    monkeypatch.setattr(
        agentic, "load_formal_micro_tasks", lambda: [safe, blocked]
    )
    monkeypatch.setattr(agentic, "embed_texts", lambda *_args, **_kwargs: [[0.0] * 1024])
    monkeypatch.setattr(agentic, "bm25_search", lambda *_args, **_kwargs: [safe, blocked])
    monkeypatch.setattr(agentic, "vector_search", lambda *_args, **_kwargs: [safe])
    seen_documents = []

    def rerank(_query, documents, _api_key):
        seen_documents.extend(documents)
        return [{"index": index, "relevance_score": 1.0} for index in range(len(documents))]

    monkeypatch.setattr(agentic, "rerank_texts", rerank)
    runtime = _runtime(_request(cannot_move=True))
    factors = [
        {"factor_id": "F1", "domain_hint": None, "subquery": "因素一", "evidence_need": "general"}
    ]

    update = runtime.retrieve_agentic_tasks(
        {"factors": factors, "diagnostics": agentic.initial_diagnostics()}
    )

    assert [task["task_id"] for task in update["base_task_ranking"]] == [safe["task_id"]]
    assert len(seen_documents) == 1
    assert update["diagnostics"]["task_candidate_ids"] == [safe["task_id"]]
    assert update["diagnostics"]["model_calls"]["task_embedding"] == 2
    assert update["diagnostics"]["model_calls"]["task_rerank"] == 1


def test_memory_disabled_makes_no_memory_retrieval_call(monkeypatch):
    import weilv.agentic_rag as agentic

    profile = UserProfile("user-1", "junior_high", False, "now", "now")
    monkeypatch.setattr(agentic, "get_user_profile", lambda *_args: profile)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("memory retrieval must stay off")

    monkeypatch.setattr(agentic, "retrieve_personal_memories", forbidden)

    update = _runtime().retrieve_user_memory(
        {
            "safety_status": "allowed",
            "diagnostics": agentic.initial_diagnostics(),
            "original_query_embedding": [0.0] * 1024,
        }
    )

    assert update["retrieved_memories"] == []
    assert update["retrieved_memory_ids"] == []
    assert update["diagnostics"]["memory_hit_count"] == 0
    assert update["diagnostics"]["model_calls"]["memory_rerank"] == 0


def test_personalization_preserves_candidate_set_and_frozen_scoring(monkeypatch):
    import weilv.agentic_rag as agentic

    tasks = [_task("MT-SED-001", rank=1), _task("MT-EYE-001", domain="eye_health", rank=2)]
    memories = [
        {
            "memory_id": "UM-1",
            "memory_type": "task_preference",
            "task_id": "MT-EYE-001",
            "memory_key": "prefer_task",
            "memory_value": {"preference": "prefer_task"},
        }
    ]

    update = _runtime().apply_personalization(
        {"base_task_ranking": tasks, "retrieved_memories": memories, "diagnostics": agentic.initial_diagnostics()}
    )

    assert {item["task_id"] for item in update["personal_task_ranking"]} == {
        "MT-SED-001",
        "MT-EYE-001",
    }
    assert update["personal_task_ranking"][0]["task_id"] == "MT-EYE-001"
    assert update["personal_task_ranking"][0]["personalization"]["personalization_delta"] == 3
    assert update["diagnostics"]["personalization_delta_by_task"] == {
        "MT-SED-001": 0,
        "MT-EYE-001": 3,
    }


def test_evidence_mismatch_fails_closed_before_explanation(monkeypatch):
    import weilv.agentic_rag as agentic

    monkeypatch.setattr(agentic, "load_task_evidence", lambda *_args, **_kwargs: [])
    task = _task()
    state = {
        "personal_task_ranking": [task],
        "diagnostics": agentic.initial_diagnostics(),
    }

    grounded = _runtime().select_and_ground(state)
    composed = _runtime().compose_explanation({**state, **grounded})

    assert grounded["safety_status"] == "no_safe_task"
    assert grounded["safety_reason_codes"] == ["selected_task_evidence_invalid"]
    assert composed == {}
    assert grounded["diagnostics"]["model_calls"]["explanation"] == 0


def test_output_guard_rejection_uses_existing_safe_fallback(monkeypatch):
    import weilv.agentic_rag as agentic

    task = _task()
    evidence = [_knowledge(task["evidence_chunk_ids"][0])]
    monkeypatch.setattr(
        agentic,
        "load_formal_task_identities",
        lambda *_args, **_kwargs: [task, {"task_id": "MT-OTHER-001", "title": "另一个任务"}],
    )
    state = {
        "selected_task": task,
        "task_evidence": evidence,
        "response_text": "请执行另一个任务。",
        "safety_status": "allowed",
        "safety_reason_codes": [],
        "safety_matched_rule_ids": [],
        "knowledge_contexts": [],
        "diagnostics": agentic.initial_diagnostics(),
    }

    update = _runtime().output_guard(state)

    assert update["guard_status"] == "rejected"
    assert update["result"]["explanation_guard"]["fallback_used"] is True
    assert update["result"]["explanation"] == agentic.SAFE_EXPLANATION_FALLBACK


def test_public_rag_projection_exposes_reviewed_excerpts_without_internal_ranking(monkeypatch):
    import weilv.agentic_rag as agentic

    task = _task()
    evidence = [_knowledge(task["evidence_chunk_ids"][0])]
    knowledge = {
        **_knowledge("KC-PUBLIC-1"),
        "rerank_rank": 1,
        "rerank_score": 0.999,
        "embedding": [0.1, 0.2],
    }
    monkeypatch.setattr(
        agentic,
        "validate_explanation_output",
        lambda *_args, **_kwargs: {"passed": True, "reason_codes": []},
    )
    monkeypatch.setattr(agentic, "load_formal_task_identities", lambda *_args, **_kwargs: [task])
    state = {
        "selected_task": task,
        "task_evidence": evidence,
        "response_text": "基于证据的回答 [E1]",
        "safety_status": "allowed",
        "safety_reason_codes": [],
        "safety_matched_rule_ids": [],
        "factors": [
            {
                "factor_id": "F1",
                "domain_hint": "study_break",
                "subquery": "连续学习后的短休息",
                "evidence_need": "学习间歇证据",
            }
        ],
        "knowledge_by_factor": {"F1": [knowledge]},
        "knowledge_contexts": [knowledge],
        "diagnostics": agentic.initial_diagnostics(),
    }

    result = _runtime().output_guard(state)["result"]
    public = result["public_rag"]
    assert public["factors"] == [
        {
            "factor_id": "F1",
            "subquery": "连续学习后的短休息",
            "evidence_need": "学习间歇证据",
            "domain_hint": "study_break",
        }
    ]
    assert public["knowledge_chunks"][0] == {
        "factor_id": "F1",
        "chunk_id": "KC-PUBLIC-1",
        "source_locator": "第1节",
        "source_url": "https://example.test/doc",
        "excerpt": "连续学习后可以安排短暂休息。",
    }
    serialized = json.dumps(public, ensure_ascii=False)
    assert "rerank" not in serialized
    assert "score" not in serialized
    assert "embedding" not in serialized


def test_langgraph_is_real_compiled_fixed_graph():
    from weilv.agent_graph import build_agent_graph

    graph = build_agent_graph(_runtime())

    assert set(graph.get_graph().nodes) == {
        "__start__",
        "input_safety",
        "terminal_response",
        "analyze_problem",
        "retrieve_factor_knowledge",
        "retrieve_agentic_tasks",
        "retrieve_user_memory",
        "apply_personalization",
        "select_and_ground",
        "compose_explanation",
        "output_guard",
        "__end__",
    }
