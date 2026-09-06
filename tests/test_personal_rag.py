from dataclasses import replace

from conftest import NullElasticClient


def _task(task_id, base_rank):
    return {
        "task_id": task_id,
        "title": task_id,
        "instruction": f"instruction-{task_id}",
        "evidence_chunk_ids": ["KC-1"],
        "covered_domains": ["sedentary"],
        "estimated_minutes": 5,
        "rerank_rank": base_rank,
        "rerank_score": 1 - base_rank / 10,
    }


def _memory(memory_id, task_id, memory_type="task_feedback", **value):
    return {
        "memory_id": memory_id,
        "memory_type": memory_type,
        "task_id": task_id,
        "memory_key": value.get("preference", memory_type),
        "memory_value": value,
    }


def test_no_memory_preserves_base_order_and_has_empty_audit():
    from weilv.personal_rag import personalize_task_candidates

    result = personalize_task_candidates([_task("A", 1), _task("B", 2)], [])

    assert [item["task_id"] for item in result] == ["A", "B"]
    assert result[0]["personalization"] == {
        "memory_used": False,
        "memory_ids": [],
        "base_task_rank": 1,
        "personalization_delta": 0,
        "adjusted_rank": 1,
        "reason_codes": [],
    }


def test_prefer_and_avoid_are_soft_rank_adjustments():
    from weilv.personal_rag import personalize_task_candidates

    tasks = [_task("A", 1), _task("B", 2)]
    memories = [
        _memory("prefer-B", "B", "task_preference", preference="prefer_task"),
        _memory("avoid-A", "A", "task_preference", preference="avoid_task"),
    ]

    result = personalize_task_candidates(tasks, memories)

    assert [item["task_id"] for item in result] == ["B", "A"]
    assert result[0]["personalization"]["personalization_delta"] == 3
    assert result[0]["personalization"]["reason_codes"] == ["preferred_task"]
    assert result[1]["personalization"]["personalization_delta"] == -3
    assert result[1]["personalization"]["reason_codes"] == ["avoided_task"]


def test_positive_and_negative_feedback_apply_frozen_rules():
    from weilv.personal_rag import personalize_task_candidates

    memories = [
        _memory(
            "positive",
            "B",
            helpfulness=5,
            completion_status="completed",
            burden="easy",
        ),
        _memory(
            "negative",
            "A",
            helpfulness=1,
            completion_status="skipped",
            burden="hard",
        ),
    ]

    result = personalize_task_candidates([_task("A", 1), _task("B", 2)], memories)

    assert [item["task_id"] for item in result] == ["B", "A"]
    assert result[0]["personalization"]["personalization_delta"] == 4
    assert result[0]["personalization"]["reason_codes"] == [
        "helpful_task",
        "completed_task",
        "easy_task",
    ]
    assert result[1]["personalization"]["personalization_delta"] == -4


def test_unrelated_and_unsupported_memory_types_do_not_change_order():
    from weilv.personal_rag import personalize_task_candidates

    tasks = [_task("A", 1), _task("B", 2)]
    memories = [
        _memory("other", "C", helpfulness=5),
        _memory("context", "B", "context_preference", preference="home"),
        _memory("constraint", "B", "user_constraint", max_minutes=5),
    ]

    result = personalize_task_candidates(tasks, memories)

    assert [item["task_id"] for item in result] == ["A", "B"]
    assert all(item["personalization"]["memory_used"] is False for item in result)


def test_delta_is_clamped_to_five_in_both_directions():
    from weilv.personal_rag import personalize_task_candidates

    positive = [
        _memory(f"p-{number}", "A", helpfulness=5, completion_status="completed", burden="easy")
        for number in range(3)
    ]
    negative = [
        _memory(f"n-{number}", "B", helpfulness=1, completion_status="skipped", burden="hard")
        for number in range(3)
    ]

    result = personalize_task_candidates([_task("A", 1), _task("B", 2)], positive + negative)
    audits = {item["task_id"]: item["personalization"] for item in result}

    assert audits["A"]["personalization_delta"] == 5
    assert audits["B"]["personalization_delta"] == -5


def test_ties_use_base_rank_then_task_id_deterministically():
    from weilv.personal_rag import personalize_task_candidates

    tasks = [_task("B", 1), _task("A", 1), _task("C", 2)]

    assert [item["task_id"] for item in personalize_task_candidates(tasks, [])] == [
        "A",
        "B",
        "C",
    ]


def test_small_delta_does_not_overturn_a_large_base_rank_gap():
    from weilv.personal_rag import personalize_task_candidates

    tasks = [_task("A", 1), _task("B", 10)]
    memories = [_memory("completed-B", "B", completion_status="completed")]

    result = personalize_task_candidates(tasks, memories)

    assert [item["task_id"] for item in result] == ["A", "B"]
    assert result[1]["personalization"]["adjusted_rank"] == 9


def test_strong_delta_can_overturn_a_nearby_base_rank_gap():
    from weilv.personal_rag import personalize_task_candidates

    tasks = [_task("A", 3), _task("B", 5)]
    memories = [_memory("prefer-B", "B", "task_preference", preference="prefer_task")]

    result = personalize_task_candidates(tasks, memories)

    assert [item["task_id"] for item in result] == ["B", "A"]
    assert result[0]["personalization"] == {
        "memory_used": True,
        "memory_ids": ["prefer-B"],
        "base_task_rank": 5,
        "personalization_delta": 3,
        "adjusted_rank": 2,
        "reason_codes": ["preferred_task"],
    }


def _request():
    from weilv.basic_rag import BasicRagRequest

    return BasicRagRequest("query", "junior_high", "home", 10)


def _pipeline_state(tasks=None):
    return {
        "result": None,
        "query_embedding": [0.1] * 1024,
        "knowledge": [],
        "safe_result": {"matched_rule_ids": [], "reason_codes": []},
        "reranked_tasks": tasks or [_task("A", 1), _task("B", 2)],
    }


def test_missing_or_disabled_profile_degrades_to_basic_result(monkeypatch):
    from weilv import personal_rag
    from weilv.user_memory import UserProfile

    state = _pipeline_state(tasks=[_task("A", 1)])
    monkeypatch.setattr(personal_rag, "_run_basic_pipeline", lambda *_args, **_kwargs: state)
    basic = {"status": "allowed", "selected_task": {"task_id": "A"}, "explanation": "basic"}
    monkeypatch.setattr(
        personal_rag, "_basic_result_from_pipeline", lambda *_args, **_kwargs: basic
    )
    monkeypatch.setattr(personal_rag, "get_user_profile", lambda *_args: None)
    missing = personal_rag.run_personal_rag(_request(), "user", NullElasticClient(), "key")

    disabled = replace(
        UserProfile("user", "junior_high", True, "created", "updated"),
        memory_enabled=False,
    )
    monkeypatch.setattr(personal_rag, "get_user_profile", lambda *_args: disabled)
    disabled_result = personal_rag.run_personal_rag(_request(), "user", NullElasticClient(), "key")

    assert missing == disabled_result
    assert missing["selected_task"]["task_id"] == "A"
    assert "personalization" not in missing


def test_personal_rag_reuses_query_embedding_and_llm_cannot_change_selection(monkeypatch):
    from weilv import personal_rag
    from weilv.user_memory import UserProfile

    state = _pipeline_state()
    profile = UserProfile("user", "junior_high", True, "created", "updated")
    retrieval_calls = []
    finalize_calls = []
    monkeypatch.setattr(personal_rag, "get_user_profile", lambda *_args: profile)
    monkeypatch.setattr(personal_rag, "_run_basic_pipeline", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(
        personal_rag,
        "retrieve_personal_memories",
        lambda *args, **kwargs: retrieval_calls.append((args, kwargs))
        or [_memory("prefer-B", "B", "task_preference", preference="prefer_task")],
    )
    monkeypatch.setattr(
        personal_rag,
        "_finalize_selected_task",
        lambda *args, **kwargs: finalize_calls.append((args, kwargs))
        or {
            "status": "allowed",
            "selected_task": args[1],
            "explanation": "choose A instead",
        },
    )
    monkeypatch.setattr(personal_rag, "_surfaced_tasks", lambda *_args, **_kwargs: [])

    result = personal_rag.run_personal_rag(_request(), "user", NullElasticClient(), "key")

    assert retrieval_calls[0][1]["query_embedding"] is state["query_embedding"]
    assert result["selected_task"]["task_id"] == "B"
    assert result["explanation"] == "choose A instead"
    assert finalize_calls[0][0][1]["task_id"] == "B"


def test_personalization_cannot_restore_task_absent_from_safe_candidates(monkeypatch):
    from weilv import personal_rag
    from weilv.user_memory import UserProfile

    state = _pipeline_state(tasks=[_task("SAFE", 1)])
    profile = UserProfile("user", "junior_high", True, "created", "updated")
    monkeypatch.setattr(personal_rag, "get_user_profile", lambda *_args: profile)
    monkeypatch.setattr(personal_rag, "_run_basic_pipeline", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(
        personal_rag,
        "retrieve_personal_memories",
        lambda *_args, **_kwargs: [
            _memory("unsafe", "FILTERED", "task_preference", preference="prefer_task"),
            _memory("feedback", "FILTERED", helpfulness=5, completion_status="completed", burden="easy"),
        ],
    )
    monkeypatch.setattr(
        personal_rag,
        "_finalize_selected_task",
        lambda _request, task, *_args, **_kwargs: {
            "status": "allowed",
            "selected_task": task,
            "explanation": "safe",
        },
    )

    result = personal_rag.run_personal_rag(_request(), "user", NullElasticClient(), "key")

    assert result["selected_task"]["task_id"] == "SAFE"
    assert result["personalization"]["memory_used"] is False


def test_pipeline_result_short_circuits_before_profile_or_memory(monkeypatch):
    from weilv import personal_rag

    blocked = {"status": "help_seeking", "selected_task": None}
    monkeypatch.setattr(
        personal_rag,
        "_run_basic_pipeline",
        lambda *_args, **_kwargs: {"result": blocked},
    )
    monkeypatch.setattr(
        personal_rag,
        "get_user_profile",
        lambda *_args: (_ for _ in ()).throw(AssertionError("profile after safety only")),
    )

    assert personal_rag.run_personal_rag(_request(), "user", NullElasticClient(), "key") == blocked


def test_one_query_embedding_is_shared_by_knowledge_task_and_memory(monkeypatch):
    from weilv import basic_rag, personal_rag
    from weilv.user_memory import UserProfile

    knowledge = {
        "chunk_id": "KC-1",
        "document_id": "SRC-1",
        "content": "knowledge",
        "source_locator": "source:L1",
        "source_url": "https://example.test",
    }
    task = {
        **_task("A", 1),
        "domain": "sedentary",
        "safety_evidence_chunk_ids": [],
        "target_stage": ["junior_high"],
        "context_tags": ["homework"],
        "trigger": "study",
        "execution_contexts": ["home"],
        "review_status": "content_reviewed",
    }
    query_vector = [0.1] * 1024
    embed_calls = []
    memory_vectors = []
    search_results = iter(([knowledge], [knowledge], [task], [task]))
    monkeypatch.setattr(
        basic_rag,
        "embed_texts",
        lambda texts, api_key, text_type: embed_calls.append((texts, api_key, text_type))
        or [query_vector],
    )
    monkeypatch.setattr(
        basic_rag,
        "bm25_search",
        lambda *_args, **_kwargs: next(search_results),
    )
    monkeypatch.setattr(
        basic_rag,
        "vector_search",
        lambda *_args, **_kwargs: next(search_results),
    )
    monkeypatch.setattr(
        basic_rag,
        "rerank_texts",
        lambda _query, documents, _key: [
            {"index": index, "relevance_score": 1.0} for index in range(len(documents))
        ],
    )
    monkeypatch.setattr(
        personal_rag,
        "get_user_profile",
        lambda *_args: UserProfile("user", "junior_high", True, "created", "updated"),
    )
    monkeypatch.setattr(
        personal_rag,
        "retrieve_personal_memories",
        lambda *_args, **kwargs: memory_vectors.append(kwargs["query_embedding"]) or [],
    )
    monkeypatch.setattr(
        personal_rag,
        "_finalize_selected_task",
        lambda _request, task, *_args, **_kwargs: {
            "status": "allowed",
            "selected_task": task,
            "explanation": "ok",
        },
    )

    result = personal_rag.run_personal_rag(_request(), "user", NullElasticClient(), "key")

    assert result["selected_task"]["task_id"] == "A"
    assert embed_calls == [(["query"], "key", "query")]
    assert memory_vectors == [query_vector]


def test_personal_rag_uses_shared_exact_evidence_and_guard_finalize(monkeypatch):
    from weilv import personal_rag
    from weilv.user_memory import UserProfile

    state = _pipeline_state(tasks=[_task("A", 1)])
    finalized = []
    monkeypatch.setattr(personal_rag, "_run_basic_pipeline", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(
        personal_rag,
        "get_user_profile",
        lambda *_args: UserProfile("user", "junior_high", True, "created", "updated"),
    )
    monkeypatch.setattr(personal_rag, "retrieve_personal_memories", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        personal_rag,
        "_finalize_selected_task",
        lambda *args, **kwargs: finalized.append((args, kwargs))
        or {"status": "allowed", "selected_task": {"task_id": "A"}},
    )
    monkeypatch.setattr(personal_rag, "_surfaced_tasks", lambda *_args, **_kwargs: [])

    result = personal_rag.run_personal_rag(_request(), "user", NullElasticClient(), "key")

    assert result["selected_task"]["task_id"] == "A"
    assert finalized[0][0][1]["task_id"] == "A"
