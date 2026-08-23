from dataclasses import replace

import pytest

KNOWLEDGE = {
    "chunk_id": "KC-SRC-007-003",
    "document_id": "SRC-007",
    "title": "学生常见病多病共防“十要义”",
    "content": "久坐1小时后起身活动10分钟，放松眼睛和身体。",
    "domain": "sedentary",
    "knowledge_role": "behavior_guidance",
    "source_locator": "source.md:L20-L20",
    "source_url": "https://example.test/source",
    "proposed_use": ["rag_knowledge", "micro_task_evidence"],
    "review_status": "content_reviewed",
}

TASK = {
    "task_id": "MT-SED-001",
    "title": "写作业久坐后的起身活动",
    "instruction": "如果写作业或自习已经连续坐了约1小时，起身活动约10分钟再继续。",
    "domain": "sedentary",
    "covered_domains": ["sedentary", "light_recovery"],
    "evidence_chunk_ids": ["KC-SRC-007-003"],
    "safety_evidence_chunk_ids": [],
    "target_stage": ["primary_upper", "junior_high", "senior_high"],
    "context_tags": ["homework", "self_study", "long_sitting"],
    "trigger": "连续久坐约1小时",
    "execution_contexts": ["home", "school", "study_space"],
    "estimated_minutes": 10,
    "review_status": "content_reviewed",
}


class RecordingClient:
    def __init__(self, knowledge=None, tasks=None):
        self.knowledge = list(knowledge or [])
        self.tasks = list(tasks or [])
        self.search_calls = []

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        sources = self.knowledge if kwargs["index"] == "health_knowledge_v1" else self.tasks
        return {
            "hits": {
                "hits": [
                    {"_score": 1.0 - position / 100, "_source": source}
                    for position, source in enumerate(sources)
                ]
            }
        }


def _request(**overrides):
    from weilv.basic_rag import BasicRagRequest

    request = BasicRagRequest(
        query="我写作业快一个小时了，现在有10分钟休息。",
        target_stage="junior_high",
        current_context="home",
        available_minutes=10,
    )
    return replace(request, **overrides)


def test_request_rejects_legacy_target_stage():
    from weilv.basic_rag import BasicRagRequest

    with pytest.raises(ValueError, match="target_stage"):
        BasicRagRequest("query", "middle_school", "home")


def test_input_risk_short_circuits_before_retrieval_and_models(monkeypatch):
    from weilv import basic_rag

    def forbidden(*args, **kwargs):
        raise AssertionError("risk short-circuit must not call retrieval or models")

    monkeypatch.setattr(basic_rag, "embed_texts", forbidden)
    monkeypatch.setattr(basic_rag, "bm25_search", forbidden)
    monkeypatch.setattr(basic_rag, "vector_search", forbidden)
    monkeypatch.setattr(basic_rag, "rerank_texts", forbidden)
    monkeypatch.setattr(basic_rag, "explain_selected_task", forbidden)

    result = basic_rag.run_basic_rag(
        _request(vision_abnormal=True), RecordingClient(), api_key="test-key"
    )

    assert result == {
        "status": "help_seeking",
        "selected_task": None,
        "explanation": None,
        "sources": [],
        "matched_rule_ids": ["SR-001"],
        "reason_codes": ["vision_abnormal_help_seeking"],
    }


def _unstable_rule_ids(**request_overrides):
    from weilv.basic_rag import _safety_context
    from weilv.safety_rules import filter_task_by_safety

    task = {**TASK, "execution_contexts": ["commute", "study_space"]}
    result = filter_task_by_safety(task, _safety_context(_request(**request_overrides)))
    return result["matched_rule_ids"]


def test_commute_unstable_screen_activity_triggers_sr010():
    assert _unstable_rule_ids(
        current_context="commute",
        unstable_environment=True,
        activity_context="screen",
    ) == ["SR-010"]


def test_commute_unstable_other_activity_does_not_trigger_sr010():
    assert _unstable_rule_ids(
        current_context="commute",
        unstable_environment=True,
        activity_context="other",
    ) == []


def test_study_space_unstable_reading_activity_triggers_sr010():
    assert _unstable_rule_ids(
        current_context="study_space",
        unstable_environment=True,
        activity_context="reading",
    ) == ["SR-010"]


def test_stable_screen_activity_does_not_trigger_sr010():
    assert _unstable_rule_ids(
        current_context="commute",
        unstable_environment=False,
        activity_context="screen",
    ) == []


def test_unknown_context_does_not_become_a_safety_context_mismatch(monkeypatch):
    from weilv import basic_rag

    seen = []

    def capture(context, rules):
        seen.append(context)
        return {
            "status": "help_seeking",
            "matched_rule_ids": ["SR-X"],
            "reason_codes": ["captured"],
        }

    monkeypatch.setattr(basic_rag, "evaluate_input_risk", capture)

    basic_rag.run_basic_rag(
        _request(current_context="unknown"), RecordingClient(), api_key="test-key"
    )

    assert seen[0]["current_context"] is None


def test_allowed_flow_uses_frozen_filters_reuses_embedding_and_copies_es_task(
    monkeypatch,
):
    from weilv import basic_rag

    events = []
    embed_calls = []
    rerank_calls = []
    explanation_inputs = []

    def embed(texts, api_key, text_type):
        embed_calls.append((texts, api_key, text_type))
        return [[0.1] * 1024]

    def rerank(query, documents, api_key):
        rerank_calls.append((query, documents, api_key))
        events.append("knowledge_rerank" if len(rerank_calls) == 1 else "task_rerank")
        return [
            {"index": index, "relevance_score": 1.0 - index / 10}
            for index in range(len(documents))
        ]

    original_select = basic_rag.select_safe_tasks

    def select(tasks, context, rules):
        events.append("task_safety")
        return original_select(tasks, context, rules)

    def explain(query, selected_task, knowledge, api_key):
        explanation_inputs.append((query, selected_task, knowledge, api_key))
        return "这个任务与当前久坐后的短暂休息时间相符。"

    monkeypatch.setattr(basic_rag, "embed_texts", embed)
    monkeypatch.setattr(basic_rag, "rerank_texts", rerank)
    monkeypatch.setattr(basic_rag, "select_safe_tasks", select)
    monkeypatch.setattr(basic_rag, "explain_selected_task", explain)
    client = RecordingClient(knowledge=[KNOWLEDGE], tasks=[TASK])

    result = basic_rag.run_basic_rag(_request(), client, api_key="test-key")

    assert embed_calls == [
        (["我写作业快一个小时了，现在有10分钟休息。"], "test-key", "query")
    ]
    assert events == ["knowledge_rerank", "task_safety", "task_rerank"]
    assert result["status"] == "allowed"
    assert result["selected_task"] == {
        "task_id": "MT-SED-001",
        "title": "写作业久坐后的起身活动",
        "instruction": "如果写作业或自习已经连续坐了约1小时，起身活动约10分钟再继续。",
        "evidence_chunk_ids": ["KC-SRC-007-003"],
        "covered_domains": ["sedentary", "light_recovery"],
        "estimated_minutes": 10,
    }
    assert result["sources"] == [
        {
            "chunk_id": "KC-SRC-007-003",
            "document_id": "SRC-007",
            "source_locator": "source.md:L20-L20",
            "source_url": "https://example.test/source",
        }
    ]
    assert explanation_inputs[0][1]["task_id"] == "MT-SED-001"
    assert explanation_inputs[0][2][0]["content"] == KNOWLEDGE["content"]

    knowledge_filters = client.search_calls[0]["query"]["bool"]["filter"]
    assert knowledge_filters == [
        {"term": {"review_status": "content_reviewed"}},
        {"term": {"proposed_use": "rag_knowledge"}},
        {"bool": {"must_not": [{"term": {"proposed_use": "exclude_from_normal_recommendation"}}]}},
    ]
    task_filters = client.search_calls[2]["query"]["bool"]["filter"]
    assert task_filters == [
        {"term": {"review_status": "content_reviewed"}},
        {"term": {"target_stage": "junior_high"}},
        {"term": {"execution_contexts": "home"}},
        {"range": {"estimated_minutes": {"lte": 10}}},
    ]
    assert client.search_calls[1]["knn"]["filter"] == knowledge_filters
    assert client.search_calls[3]["knn"]["filter"] == task_filters


def test_ten_minute_task_cannot_survive_two_minute_request(monkeypatch):
    from weilv import basic_rag

    rerank_documents = []

    monkeypatch.setattr(
        basic_rag, "embed_texts", lambda *args, **kwargs: [[0.1] * 1024]
    )
    monkeypatch.setattr(
        basic_rag,
        "rerank_texts",
        lambda query, documents, api_key: (
            rerank_documents.append(documents)
            or [
                {"index": index, "relevance_score": 1.0}
                for index in range(len(documents))
            ]
        ),
    )
    monkeypatch.setattr(
        basic_rag,
        "explain_selected_task",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("no_safe_task must not call qwen-plus")
        ),
    )

    result = basic_rag.run_basic_rag(
        _request(available_minutes=2),
        RecordingClient(knowledge=[KNOWLEDGE], tasks=[TASK]),
        api_key="test-key",
    )

    assert result["status"] == "no_safe_task"
    assert result["selected_task"] is None
    assert len(rerank_documents) == 1
    assert result["matched_rule_ids"] == ["SR-012"]


def test_commute_unstable_context_cannot_return_home_only_task(monkeypatch):
    from weilv import basic_rag

    monkeypatch.setattr(
        basic_rag, "embed_texts", lambda *args, **kwargs: [[0.1] * 1024]
    )
    monkeypatch.setattr(
        basic_rag,
        "rerank_texts",
        lambda query, documents, api_key: [
            {"index": index, "relevance_score": 1.0}
            for index in range(len(documents))
        ],
    )
    monkeypatch.setattr(
        basic_rag,
        "explain_selected_task",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("no_safe_task must not call qwen-plus")
        ),
    )
    home_only = {**TASK, "execution_contexts": ["home"]}

    result = basic_rag.run_basic_rag(
        _request(current_context="commute", unstable_environment=True),
        RecordingClient(knowledge=[KNOWLEDGE], tasks=[home_only]),
        api_key="test-key",
    )

    assert result["status"] == "no_safe_task"
    assert result["selected_task"] is None
    assert result["matched_rule_ids"] == ["SR-012"]


def test_explanation_model_only_explains_the_program_selected_task(monkeypatch):
    from types import SimpleNamespace

    from weilv import dashscope_models

    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="这个任务符合当前可用的休息时间。")
                    )
                ]
            ),
        )

    monkeypatch.setattr(dashscope_models.Generation, "call", generate)

    explanation = dashscope_models.explain_selected_task(
        "我写作业快一个小时了，现在有10分钟休息。",
        {
            "task_id": "MT-SED-001",
            "title": "写作业久坐后的起身活动",
            "instruction": "起身活动约10分钟再继续。",
            "estimated_minutes": 10,
        },
        [KNOWLEDGE],
        api_key="test-key",
    )

    assert explanation == "这个任务符合当前可用的休息时间。"
    assert calls[0]["model"] == "qwen-plus"
    system_prompt = calls[0]["messages"][0]["content"]
    user_prompt = calls[0]["messages"][1]["content"]
    assert "只输出解释文本" in system_prompt
    assert "不得新增任务" in system_prompt
    assert "不得修改任务指令、时长" in system_prompt
    assert "起身活动约10分钟再继续。" in user_prompt
    assert KNOWLEDGE["content"] in user_prompt


def test_exact_task_evidence_is_complete_ordered_and_separate_from_context():
    from weilv.basic_rag import load_task_evidence

    class Client:
        def search(self, **kwargs):
            assert kwargs["query"] == {
                "bool": {
                    "filter": [
                        {"terms": {"chunk_id": ["KC-A", "KC-B"]}},
                        {"term": {"review_status": "content_reviewed"}},
                        {"term": {"proposed_use": "micro_task_evidence"}},
                    ]
                }
            }
            return {
                "hits": {
                    "hits": [
                        {"_source": {**KNOWLEDGE, "chunk_id": "KC-B", "content": "B"}},
                        {"_source": {**KNOWLEDGE, "chunk_id": "KC-A", "content": "A"}},
                        {"_source": {**KNOWLEDGE, "chunk_id": "KC-C", "content": "C"}},
                    ]
                }
            }

    evidence = load_task_evidence(
        Client(), {**TASK, "evidence_chunk_ids": ["KC-A", "KC-B"]}, "health_knowledge_v1"
    )

    assert [item["chunk_id"] for item in evidence] == ["KC-A", "KC-B"]


def test_rag_knowledge_without_micro_task_evidence_is_not_task_evidence():
    from weilv.basic_rag import load_task_evidence

    class Client:
        def search(self, **_kwargs):
            return {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                **KNOWLEDGE,
                                "chunk_id": "KC-A",
                                "proposed_use": ["rag_knowledge"],
                            }
                        }
                    ]
                }
            }

    assert load_task_evidence(
        Client(), {**TASK, "evidence_chunk_ids": ["KC-A"]}, "health_knowledge_v1"
    ) == []


def test_invalid_exact_evidence_fails_closed_before_llm(monkeypatch):
    from weilv import basic_rag

    state = {
        "result": None,
        "knowledge": [{**KNOWLEDGE, "chunk_id": "KC-C"}],
        "safe_result": {"matched_rule_ids": [], "reason_codes": []},
        "reranked_tasks": [{**TASK, "evidence_chunk_ids": ["KC-MISSING"]}],
    }
    monkeypatch.setattr(basic_rag, "_run_basic_pipeline", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(basic_rag, "load_task_evidence", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        basic_rag,
        "explain_selected_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("invalid evidence")),
    )

    result = basic_rag.run_basic_rag(_request(), object(), "key")

    assert result["status"] == "no_safe_task"
    assert result["selected_task"] is None
    assert result["reason_codes"] == ["selected_task_evidence_invalid"]


def test_final_sources_use_exact_evidence_context_sources_stay_query_grounded(monkeypatch):
    from weilv import basic_rag

    context = [{**KNOWLEDGE, "chunk_id": "KC-C"}]
    evidence = [{**KNOWLEDGE, "chunk_id": "KC-SRC-007-003"}]
    state = {
        "result": None,
        "knowledge": context,
        "safe_result": {"matched_rule_ids": [], "reason_codes": []},
        "reranked_tasks": [TASK],
    }
    explanation_inputs = []
    monkeypatch.setattr(basic_rag, "_run_basic_pipeline", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(basic_rag, "load_task_evidence", lambda *_args, **_kwargs: evidence)
    monkeypatch.setattr(basic_rag, "load_formal_task_identities", lambda *_args: [TASK])
    monkeypatch.setattr(
        basic_rag,
        "explain_selected_task",
        lambda query, task, knowledge, api_key: explanation_inputs.append(knowledge) or "安全解释",
    )

    result = basic_rag.run_basic_rag(_request(), object(), "key")

    assert [item["chunk_id"] for item in result["sources"]] == ["KC-SRC-007-003"]
    assert [item["chunk_id"] for item in result["context_sources"]] == ["KC-C"]
    assert explanation_inputs == [evidence]


def test_guard_rejection_uses_fallback_without_changing_task(monkeypatch):
    from weilv import basic_rag

    state = {
        "result": None,
        "knowledge": [],
        "safe_result": {"matched_rule_ids": [], "reason_codes": []},
        "reranked_tasks": [TASK],
    }
    monkeypatch.setattr(basic_rag, "_run_basic_pipeline", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(basic_rag, "load_task_evidence", lambda *_args, **_kwargs: [KNOWLEDGE])
    monkeypatch.setattr(basic_rag, "load_formal_task_identities", lambda *_args: [TASK])
    monkeypatch.setattr(basic_rag, "explain_selected_task", lambda *_args, **_kwargs: "做30分钟深蹲")

    result = basic_rag.run_basic_rag(_request(), object(), "key")

    assert result["selected_task"]["task_id"] == TASK["task_id"]
    assert "深蹲" not in result["explanation"]
    assert result["explanation_guard"] == {
        "passed": False,
        "fallback_used": True,
        "reason_codes": ["adds_unsupported_action", "adds_unsupported_quantity"],
    }
