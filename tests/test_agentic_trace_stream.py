"""B3: public agentic observable trace — streaming endpoint tests."""

import json

from fastapi.testclient import TestClient

from weilv.api.agentic_trace import NODE_STAGE, STAGE_LABELS


def _payload():
    return {
        "user_id": "agentic-trace-user-001",
        "query": "连续写作业后只剩5分钟，快到睡觉时间，也不想活动",
        "target_stage": "junior_high",
        "current_context": "home",
        "activity_context": "writing",
        "available_minutes": 5,
        "vision_abnormal": False,
        "physical_discomfort": False,
        "medical_request": False,
        "cannot_move": False,
        "unstable_environment": False,
        "sleep_being_crowded": True,
    }


def _allowed_result():
    return {
        "status": "allowed",
        "selected_task": {"task_id": "MT-SED-001", "instruction": "正式指令"},
        "explanation": "解释文本",
        "sources": [{"chunk_id": "KC-1"}],
        "context_sources": [{"chunk_id": "KC-2"}],
        "public_rag": {
            "analysis_fallback": False,
            "factors": [
                {
                    "factor_id": "F1",
                    "subquery": "连续学习后的短休息",
                    "evidence_need": "学习间歇证据",
                    "domain_hint": "study_break",
                    "reasoning": "must-not-leak",
                }
            ],
            "knowledge_chunks": [
                {
                    "factor_id": "F1",
                    "chunk_id": "KC-2",
                    "source_locator": "审核知识库 · 第1节",
                    "source_url": "https://example.test/knowledge",
                    "excerpt": "公开知识片段：连续学习后可以安排短暂休息。",
                    "score": 0.99,
                    "embedding": [0.1, 0.2],
                }
            ],
        },
        "matched_rule_ids": [],
        "reason_codes": [],
        "explanation_guard": {"passed": True, "fallback_used": False, "reason_codes": []},
        "personalization": None,
        "agentic": True,
        "diagnostics": {
            "factor_count": 1,
            "factor_domains": ["sleep"],
            "analysis_fallback": False,
            "knowledge_chunk_ids_by_factor": {"F1": ["KC-1"]},
            "knowledge_trace_by_factor": {"F1": {"candidate_ids": ["KC-1"], "reranked_ids": ["KC-1"], "selected_ids": ["KC-1"]}},
            "task_candidate_ids": ["MT-SED-001"],
            "base_task_ranking": ["MT-SED-001"],
            "personal_task_ranking": ["MT-SED-001"],
            "memory_hit_count": 0,
            "selected_task_id": "MT-SED-001",
            "safety_reason_codes": [],
            "model_calls": {
                "decomposition": 1,
                "knowledge_embedding": 1,
                "knowledge_rerank": 1,
                "task_embedding": 1,
                "task_rerank": 1,
                "memory_embedding": 0,
                "memory_rerank": 0,
                "explanation": 1,
            },
        },
    }


def _graph_events(result):
    """Real node-start events followed by the root completion event."""
    for node in NODE_STAGE:
        yield {"event": "on_chain_start", "metadata": {"langgraph_node": node}}
    yield {"event": "on_chain_start", "metadata": {"langgraph_node": "retrieve_user_memory"}}
    yield {"event": "on_chain_end", "metadata": {}, "data": {"output": {"result": result}}}


def _setup(monkeypatch, events=None, result=None, raise_error=False, log_calls=None):
    from weilv.api import app as api

    calls = []
    expected_result = result if result is not None else _allowed_result()

    async def fake_events(*args, **kwargs):
        calls.append((args, kwargs))
        if raise_error:
            raise RuntimeError("secret-stack-trace: boom ES error")
        if events is None:
            for event in _graph_events(expected_result):
                yield event
        else:
            for event in events:
                yield event

    monkeypatch.setattr(api, "iter_agentic_graph_events", fake_events)
    if log_calls is None:
        log_calls = []
    monkeypatch.setattr(api, "create_recommendation_log", lambda *a, **k: log_calls.append((a, k)))
    api.app.state.es_client = object()
    api.app.state.api_key = "server-key"
    return api, calls, log_calls


def _post(api, url="/api/v1/recommend/agentic/stream"):
    return TestClient(api.app).post(url, json=_payload())


def _lines(response):
    return [json.loads(line) for line in response.text.strip().splitlines()]


def test_stream_status_200_and_ndjson_content_type(monkeypatch):
    api, _, _ = _setup(monkeypatch)
    response = _post(api)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")


def test_stream_stage_order_matches_real_pipeline(monkeypatch):
    api, _, _ = _setup(monkeypatch)
    lines = _lines(_post(api))
    stages = [line["stage"] for line in lines if "result" not in line]
    assert stages == ["accepted", "safety", "analysis", "retrieval", "ranking", "personalization", "grounding", "generation"]
    assert "memory" not in stages
    assert "正在结合你的历史情况" not in response_text(lines)
    assert all(line["status"] == "active" for line in lines if "result" not in line)
    # terminal nodes must never surface as public stages
    assert "terminal_response" not in json.dumps(stages)
    assert "output_guard" not in json.dumps(stages)


def test_completed_appears_exactly_once(monkeypatch):
    api, _, _ = _setup(monkeypatch)
    lines = _lines(_post(api))
    completed = [line for line in lines if line["stage"] == "completed"]
    assert len(completed) == 1
    assert completed[0]["status"] == "complete"
    assert completed[0]["label"] == "处理完成"


def test_final_answer_matches_single_execution_result(monkeypatch):
    api, _, _ = _setup(monkeypatch)
    lines = _lines(_post(api))
    completed = next(line for line in lines if line["stage"] == "completed")
    result = completed["result"]
    assert result["status"] == "allowed"
    assert result["explanation"] == "解释文本"
    assert result["selected_task"]["task_id"] == "MT-SED-001"
    assert result["sources"] == [{"chunk_id": "KC-1"}]
    assert result["public_rag"]["factors"][0]["subquery"] == "连续学习后的短休息"
    assert result["public_rag"]["analysis_fallback"] is False
    assert result["public_rag"]["knowledge_chunks"][0]["excerpt"].startswith("公开知识片段")
    assert "score" not in json.dumps(result["public_rag"], ensure_ascii=False)
    assert "embedding" not in json.dumps(result["public_rag"], ensure_ascii=False)
    assert result["recommendation_id"]
    assert result["feedback_available"] is True


def test_single_agentic_execution_call_count(monkeypatch):
    api, calls, _ = _setup(monkeypatch)
    _post(api)
    assert len(calls) == 1


def test_no_duplicate_retrieval_or_generation_stages(monkeypatch):
    api, _, _ = _setup(monkeypatch)
    lines = _lines(_post(api))
    counts = {line["stage"] for line in lines}
    assert "retrieval" in counts
    assert "generation" in counts
    from collections import Counter

    stage_counts = Counter(line["stage"] for line in lines if "result" not in line)
    assert stage_counts["retrieval"] == 1
    assert stage_counts["ranking"] == 1
    assert stage_counts["generation"] == 1


def test_duplicated_node_start_events_are_deduped(monkeypatch):
    # astream_events 会对同一节点重复发 on_chain_start；trace 每阶段只出现一次。
    events = [
        {"event": "on_chain_start", "metadata": {"langgraph_node": "input_safety"}},
        {"event": "on_chain_start", "metadata": {"langgraph_node": "input_safety"}},
        {"event": "on_chain_start", "metadata": {"langgraph_node": "analyze_problem"}},
        {"event": "on_chain_start", "metadata": {"langgraph_node": "analyze_problem"}},
        {"event": "on_chain_end", "metadata": {}, "data": {"output": {"result": _allowed_result()}}},
    ]
    api, _, _ = _setup(monkeypatch, events=events)
    lines = _lines(_post(api))
    stages = [line["stage"] for line in lines if "result" not in line]
    assert stages == ["accepted", "safety", "analysis"]


def test_safety_blocked_path_never_shows_generation(monkeypatch):
    blocked = {
        "status": "blocked",
        "selected_task": None,
        "explanation": "该请求不适合继续推荐",
        "sources": [],
        "context_sources": [],
        "matched_rule_ids": ["SR-001"],
        "reason_codes": ["medical_emergency"],
        "agentic": True,
        "diagnostics": {"factor_count": 0, "memory_hit_count": 0, "model_calls": {}},
    }
    events = [
        {"event": "on_chain_start", "metadata": {"langgraph_node": "input_safety"}},
        {"event": "on_chain_start", "metadata": {"langgraph_node": "terminal_response"}},
        {"event": "on_chain_end", "metadata": {}, "data": {"output": {"result": blocked}}},
    ]
    api, _, log_calls = _setup(monkeypatch, events=events, result=blocked)
    lines = _lines(_post(api))
    stages = [line["stage"] for line in lines]
    assert stages == ["accepted", "safety", "completed"]
    assert "generation" not in stages
    assert "analysis" not in stages
    assert "retrieval" not in stages
    assert stages[-1] == "completed"
    completed = next(line for line in lines if line["stage"] == "completed")
    assert completed["result"]["status"] == "blocked"
    assert completed["label"] == "处理完成"
    # blocked path never logs an interaction session with a selected task
    assert log_calls == []


def test_error_is_sanitized(monkeypatch):
    api, _, _ = _setup(monkeypatch, raise_error=True)
    lines = _lines(_post(api))
    assert lines[-1]["stage"] == "error"
    assert lines[-1]["status"] == "error"
    assert lines[-1]["label"] == STAGE_LABELS["error"]
    assert "boom" not in response_text(lines)


def response_text(lines):
    return "\n".join(json.dumps(line, ensure_ascii=False) for line in lines)


def test_error_when_no_result_emitted(monkeypatch):
    events = [
        {"event": "on_chain_start", "metadata": {"langgraph_node": "input_safety"}},
        # no root end -> no result
    ]
    api, _, _ = _setup(monkeypatch, events=events)
    lines = _lines(_post(api))
    assert lines[-1]["stage"] == "error"


def test_public_event_payload_secret_boundary(monkeypatch):
    api, _, _ = _setup(monkeypatch)
    text = response_text(_lines(_post(api)))
    for forbidden in (
        "prompt",
        "messages",
        "retrieval_text",
        "raw_query",
        "embedding",
        "score",
        "memory_content",
        "system",
        "reasoning",
        "api_key",
        "diagnostics",
        "model_calls",
        "task_candidate_ids",
        "knowledge_trace_by_factor",
    ):
        assert forbidden not in text, f"forbidden token leaked: {forbidden}"
    # 解释与 allowlist 审核知识 excerpt 可展示；分数/诊断/内部字段不可展示。
    assert "解释文本" in text
    assert "公开知识片段" in text
    assert "must-not-leak" not in text


def test_old_agentic_endpoint_remains_compatible(monkeypatch):
    from weilv.api import app as api

    result = _allowed_result()
    core_calls = []
    monkeypatch.setattr(
        api,
        "run_agentic_rag",
        lambda *args, **kwargs: core_calls.append(args) or result,
        raising=False,
    )
    monkeypatch.setattr(api, "create_recommendation_log", lambda *a, **k: None)
    api.app.state.es_client = object()
    api.app.state.api_key = "server-key"

    response = TestClient(api.app).post("/api/v1/recommend/agentic", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["agentic"] is True
    # 旧接口保持完整返回（含 diagnostics），兼容既有客户端
    assert body["diagnostics"]["model_calls"]["decomposition"] == 1
    assert body["recommendation_id"]
    assert body["feedback_available"] is True
    assert len(core_calls) == 1


def test_stream_uses_same_agentic_semantics_no_extra_side_effects(monkeypatch):
    api, _, log_calls = _setup(monkeypatch)
    _post(api)
    assert len(log_calls) == 1
    session = log_calls[0][0][1]
    assert session["agentic"] is True
    assert session["selected_task_id"] == "MT-SED-001"
    assert session["factor_count"] == 1
    # trace 不引入额外 Memory / Feedback 副作用
    assert session["memory_persisted"] is False
    assert session["feedback"] is None
