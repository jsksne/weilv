"""Stage 10A questionnaire + cold-start memory tests (pure and fake-ES)."""

from dataclasses import asdict

import pytest
from elasticsearch import ConflictError, NotFoundError

import weilv.questionnaire as questionnaire_module
from weilv.micro_tasks import load_formal_micro_tasks
from weilv.personal_rag import personalize_task_candidates
from weilv.questionnaire import (
    QUESTIONNAIRE_SOURCE,
    completion_state_for,
    get_questionnaire,
    invalid_answer_reasons,
    map_answers_to_memories,
    questionnaire_schema,
    save_questionnaire,
    skip_questionnaire,
)
from weilv.safety_rules import select_safe_tasks
from weilv.user_memory import UserMemoryCandidate, UserProfile, validate_memory_candidate

FULL_ANSWERS = {
    "bedtime": "2130_2230",
    "screen_duration": "30_60",
    "rest_preference": "quiet_rest",
    "annoying_reminders": ["activity"],
    "main_context": "home",
    "leave_seat_allowed": "not_allowed",
    "break_minutes": "10_20",
}


class FakeClient:
    def __init__(self):
        self.docs = {}

    def get(self, *, index, id):
        key = (index, id)
        if key not in self.docs:
            raise NotFoundError("not found", None, None)
        return {"_source": self.docs[key]}

    def create(self, *, index, id, document, refresh="true"):
        key = (index, id)
        if key in self.docs:
            raise ConflictError("conflict", None, None)
        self.docs[key] = document

    def index(self, *, index, id, document, refresh="true"):
        self.docs[(index, id)] = document

    def update(self, *, index, id, doc, refresh=None):
        self.docs[(index, id)].update(doc)

    def delete(self, *, index, id, refresh=None):
        self.docs.pop((index, id), None)

    def search(self, *, index, size, query, source=None, source_excludes=None):
        filters = query.get("bool", {}).get("filter", [])
        terms = {}
        for item in filters:
            if "term" in item:
                terms.update(item["term"])
        hits = [
            {"_source": dict(document)}
            for (_idx, _id), document in self.docs.items()
            if _idx == index and all(document.get(key) == value for key, value in terms.items())
        ]
        return {"hits": {"hits": hits[:size]}}


def _profile_client(user_id="usr_a", target_stage="junior_high"):
    client = FakeClient()
    client.docs[("user_profiles_v1", user_id)] = {
        "user_id": user_id,
        "target_stage": target_stage,
        "memory_enabled": True,
        "created_at": "2026-08-13T10:00:00+08:00",
        "updated_at": "2026-08-13T10:00:00+08:00",
    }
    return client


def _stored_memories(client, user_id):
    return [
        document
        for (index, memory_id), document in client.docs.items()
        if index == "user_memory_v1" and document.get("user_id") == user_id
    ]


def test_save_with_api_key_embeds_persisted_memories(monkeypatch):
    """问卷记忆写入后立即向量化，向量检索才能立即可用（Personal 不退化为 Basic）。"""
    client = _profile_client()
    embedded = []
    monkeypatch.setattr(
        questionnaire_module,
        "embed_memory",
        lambda client, user_id, memory_id, api_key: (
            embedded.append(memory_id),
            {"status": "embedded", "memory_id": memory_id},
        )[1],
    )

    result = save_questionnaire(client, "usr_a", FULL_ANSWERS, api_key="test-key")

    assert result["status"] == "saved"
    assert result["memory_record_ids"]
    assert sorted(embedded) == sorted(result["memory_record_ids"])
    assert result["memory_embedding_count"] == len(result["memory_record_ids"])


def test_embedding_failure_does_not_fail_the_save(monkeypatch):
    """embed 失败不阻断保存：问卷记录已落盘，反馈回路可对同一记忆 id 重试。"""
    client = _profile_client()

    def boom(*_args, **_kwargs):
        raise RuntimeError("embedding service down")

    monkeypatch.setattr(questionnaire_module, "embed_memory", boom)

    result = save_questionnaire(client, "usr_a", FULL_ANSWERS, api_key="test-key")

    assert result["status"] == "saved"
    assert result["memory_record_ids"]
    assert result["memory_embedding_count"] == 0


def test_save_without_api_key_skips_embedding(monkeypatch):
    """离线调用（无 api_key）保持旧行为：完全不触发 embedding。"""
    client = _profile_client()
    calls = []
    monkeypatch.setattr(
        questionnaire_module,
        "embed_memory",
        lambda *args, **kwargs: calls.append(args),
    )

    result = save_questionnaire(client, "usr_a", FULL_ANSWERS)

    assert result["status"] == "saved"
    assert calls == []
    assert result["memory_embedding_count"] == 0


def test_resubmission_replaces_previous_cold_start_preferences_only(monkeypatch):
    """重提交问卷替代上一版冷启动偏好；真实反馈记忆不受影响。"""
    monkeypatch.setattr(
        questionnaire_module,
        "embed_memory",
        lambda client, user_id, memory_id, api_key: {
            "status": "embedded",
            "memory_id": memory_id,
        },
    )
    client = _profile_client()

    first = save_questionnaire(client, "usr_a", FULL_ANSWERS, api_key="test-key")

    # 用户后续真实行为产生的反馈记忆（必须不被问卷重提交触碰）
    feedback_id = "fb-feedback-1"
    client.docs[("user_memory_v1", feedback_id)] = {
        "memory_id": feedback_id,
        "user_id": "usr_a",
        "memory_type": "task_feedback",
        "source_type": "interaction_feedback",
        "task_id": "MT-BREAK-003",
        "memory_key": "task_feedback",
        "retrieval_text": "type=task_feedback task=MT-BREAK-003",
        "active": True,
        "review_status": "valid",
    }

    changed = {
        **FULL_ANSWERS,
        "rest_preference": "outdoor",
        "annoying_reminders": ["none"],
    }
    second = save_questionnaire(client, "usr_a", changed, api_key="test-key")

    surviving_ids = {
        document["memory_id"]
        for document in _stored_memories(client, "usr_a")
        if document.get("source_type") == "questionnaire_cold_start"
    }
    superseded = set(first["memory_record_ids"]) - set(second["memory_record_ids"])
    # 上一版独有偏好（quiet_rest 的 prefer、activity 的 avoid 系列）不再 active
    assert superseded and not superseded & surviving_ids
    # 新版偏好全部存在且可见（检索过滤 active/valid 后只剩当前有效集）
    assert set(second["memory_record_ids"]) <= surviving_ids
    assert any(
        document.get("task_id") == "MT-OUT-001"
        for document in _stored_memories(client, "usr_a")
    )
    assert not any(
        document.get("task_id") == "MT-BREAK-003"
        and document.get("source_type") == "questionnaire_cold_start"
        for document in _stored_memories(client, "usr_a")
    )
    # 真实反馈记忆原样保留
    assert ("user_memory_v1", feedback_id) in client.docs
    assert client.docs[("user_memory_v1", feedback_id)]["memory_type"] == "task_feedback"


def test_resubmission_keeps_feedback_memory_with_same_task(monkeypatch):
    """反馈记忆与新版问卷偏好指向同一任务时也不能被问卷清扫误删。"""
    monkeypatch.setattr(
        questionnaire_module,
        "embed_memory",
        lambda client, user_id, memory_id, api_key: {
            "status": "embedded",
            "memory_id": memory_id,
        },
    )
    client = _profile_client()
    save_questionnaire(client, "usr_a", FULL_ANSWERS, api_key="test-key")
    # 反馈回路写入：同一任务的 task_feedback，id 与偏好记忆不同（memory_type 不同）
    feedback_id = "fb-same-task"
    client.docs[("user_memory_v1", feedback_id)] = {
        "memory_id": feedback_id,
        "user_id": "usr_a",
        "memory_type": "task_feedback",
        "source_type": "interaction_feedback",
        "task_id": "MT-BREAK-003",
        "memory_key": "task_feedback",
        "retrieval_text": "type=task_feedback task=MT-BREAK-003",
        "active": True,
        "review_status": "valid",
    }

    save_questionnaire(client, "usr_a", FULL_ANSWERS, api_key="test-key")

    assert client.docs[("user_memory_v1", feedback_id)]["active"] is True


def test_completion_marks_completed_and_generates_memory():
    client = _profile_client()
    result = save_questionnaire(client, "usr_a", FULL_ANSWERS)

    assert result["completion_state"] == "completed"
    assert result["completed_at"]
    assert result["questionnaire_id"] == "v1"
    assert result["memory_record_ids"]
    assert completion_state_for(FULL_ANSWERS) == "completed"
    assert _stored_memories(client, "usr_a")


def test_skip_generates_no_memory_and_keeps_product_usable():
    client = _profile_client()
    result = skip_questionnaire(client, "usr_a")

    assert result["completion_state"] == "skipped"
    assert result["answers"] == {}
    assert result["memory_record_ids"] == []
    assert _stored_memories(client, "usr_a") == []
    # a skipped user can still be served via Basic/current-context behavior
    assert get_questionnaire(client, "usr_a")["completion_state"] == "skipped"


def test_resume_from_partial_is_idempotent():
    client = _profile_client()
    partial = {
        "rest_preference": "quiet_rest",
        "main_context": "home",
    }
    first = save_questionnaire(client, "usr_a", partial)
    assert first["completion_state"] == "partially_completed"
    assert first["completed_at"] is None

    second = save_questionnaire(client, "usr_a", FULL_ANSWERS)
    assert second["completion_state"] == "completed"
    assert second["completed_at"]
    # memory records are upserted in place: ids stay stable across resume
    assert set(second["memory_record_ids"]) >= set(first["memory_record_ids"])
    assert get_questionnaire(client, "usr_a")["completion_state"] == "completed"


def test_valid_stage_mapping_for_all_supported_target_stages():
    for stage in ("primary_upper", "junior_high", "senior_high"):
        client = _profile_client(target_stage=stage)
        result = save_questionnaire(client, "usr_a", FULL_ANSWERS)
        assert result["status"] == "saved"
        assert _stored_memories(client, "usr_a")


def test_preference_maps_to_task_preference_memory():
    answers = {
        "rest_preference": "quiet_rest",
        "annoying_reminders": ["activity"],
    }
    candidates = map_answers_to_memories(answers)
    prefer = {c.task_id for c in candidates if c.memory_value["preference"] == "prefer_task"}
    avoid = {c.task_id for c in candidates if c.memory_value["preference"] == "avoid_task"}
    assert prefer == {"MT-BREAK-003"}
    assert {"MT-REC-001", "MT-REC-002", "MT-SED-001", "MT-SED-002", "MT-BREAK-004"} <= avoid
    assert all(c.source_type == QUESTIONNAIRE_SOURCE for c in candidates)


def test_constraint_maps_to_context_and_user_constraint_memory():
    answers = {
        "main_context": "home",
        "leave_seat_allowed": "not_allowed",
        "break_minutes": "10_20",
    }
    candidates = map_answers_to_memories(answers)
    contexts = [c.memory_value for c in candidates if c.memory_type == "context_preference"]
    constraints = [c.memory_value for c in candidates if c.memory_type == "user_constraint"]
    avoids = {c.task_id for c in candidates if c.memory_type == "task_preference"}
    assert contexts == [{"preferred_context": "home"}]
    assert constraints == [{"preferred_max_task_minutes": 20}]
    assert avoids == {"MT-BREAK-004", "MT-SED-001"}


def test_no_fake_task_feedback_is_generated():
    candidates = map_answers_to_memories(FULL_ANSWERS)
    assert candidates
    assert all(c.memory_type != "task_feedback" for c in candidates)


def _candidate_tasks():
    tasks = []
    for position, task in enumerate(load_formal_micro_tasks(), start=1):
        if task["task_id"] in {
            "MT-BREAK-001",
            "MT-BREAK-002",
            "MT-BREAK-003",
            "MT-SED-001",
            "MT-REC-001",
            "MT-REC-002",
        }:
            tasks.append(
                {
                    "task_id": task["task_id"],
                    "title": task["title"],
                    "rerank_rank": position,
                }
            )
    return tasks


def test_candidate_set_invariance_after_cold_start_memory():
    tasks = _candidate_tasks()
    memory = [asdict(candidate) for candidate in map_answers_to_memories(FULL_ANSWERS)]
    baseline_ids = [task["task_id"] for task in tasks]

    personalized = personalize_task_candidates(tasks, memory)

    assert [task["task_id"] for task in personalized] != baseline_ids  # ranking may differ
    assert {task["task_id"] for task in personalized} == set(baseline_ids)  # set invariant


def test_blocked_task_cannot_resurrect_via_memory():
    from weilv.basic_rag import BasicRagRequest, _matches_task_metadata

    request = BasicRagRequest(
        query="想休息一下",
        target_stage="junior_high",
        current_context="bedroom",
        available_minutes=10,
    )
    tasks = load_formal_micro_tasks()
    metadata_tasks = [task for task in tasks if _matches_task_metadata(task, request)]
    safe = select_safe_tasks(metadata_tasks, {"target_stage": "junior_high"})
    safe_ids = {task["task_id"] for task in safe["tasks"]}
    assert "MT-OUT-001" not in safe_ids  # execution-context mismatch blocks outdoor task

    memory = [
        asdict(candidate)
        for candidate in map_answers_to_memories({"rest_preference": "outdoor"})
    ]
    personalized = personalize_task_candidates(list(safe["tasks"]), memory)
    assert "MT-OUT-001" not in {task["task_id"] for task in personalized}


def test_malformed_and_empty_answers_fail_safely():
    client = _profile_client()
    for answers in (
        {},
        {"rest_preference": "teleport"},
        {"unknown_question": "quiet_rest"},
        {"annoying_reminders": ["activity", "none"]},
        {"annoying_reminders": []},
    ):
        result = save_questionnaire(client, "usr_a", answers)
        assert result["status"] == "rejected"
        assert result["reason_codes"]

    partial = {"rest_preference": "quiet_rest", "main_context": "home"}
    assert invalid_answer_reasons(partial) == ["missing_required_answers"]
    assert completion_state_for(partial) == "partially_completed"
    with pytest.raises(ValueError):
        map_answers_to_memories({"rest_preference": "teleport"})


def test_source_provenance_is_stored():
    client = _profile_client()
    result = save_questionnaire(client, "usr_a", FULL_ANSWERS)

    memories = _stored_memories(client, "usr_a")
    assert {memory["source_type"] for memory in memories} == {QUESTIONNAIRE_SOURCE}
    assert {memory["memory_id"] for memory in memories} == set(result["memory_record_ids"])
    record = get_questionnaire(client, "usr_a")
    assert record["questionnaire_id"] == "v1"
    assert record["answers"] == FULL_ANSWERS


def test_existing_users_without_questionnaire_still_work():
    client = _profile_client("usr_no_q")
    assert get_questionnaire(client, "usr_no_q")["completion_state"] == "not_started"

    tasks = _candidate_tasks()
    baseline_ids = [task["task_id"] for task in tasks]
    unchanged = personalize_task_candidates(tasks, [])  # no memory -> no reordering
    assert [task["task_id"] for task in unchanged] == baseline_ids


def test_questionnaire_cold_start_passes_and_respects_existing_gate():
    profile = UserProfile("usr_a", "junior_high", True, "created", "updated")
    candidate = map_answers_to_memories(
        {"rest_preference": "quiet_rest", "main_context": "home"}
    )[0]
    candidate = UserMemoryCandidate(
        **{**asdict(candidate), "user_id": profile.user_id}
    )
    assert validate_memory_candidate(profile, candidate, {"MT-BREAK-003"})["valid"]

    fake_feedback = UserMemoryCandidate(
        memory_id="",
        user_id="usr_a",
        memory_type="task_feedback",
        source_type=QUESTIONNAIRE_SOURCE,
        task_id="MT-BREAK-003",
        domain="study_break",
        memory_key="task_feedback",
        memory_value={
            "completion_status": "completed",
            "helpfulness": 5,
            "burden": "easy",
        },
        created_at="now",
        updated_at="now",
    )
    assert validate_memory_candidate(profile, fake_feedback, {"MT-BREAK-003"}) == {
        "valid": False,
        "reason_codes": ["source_type_mismatch"],
    }


def test_schema_serves_7_questions_with_option_values():
    schema = questionnaire_schema()
    assert schema["questionnaire_id"] == "v1"
    assert len(schema["questions"]) == 7
    assert all(item["options"] for item in schema["questions"])
    assert all(item["question_id"] for item in schema["questions"])


def test_questionnaire_mapping_only_references_formal_task_ids():
    formal_ids = {task["task_id"] for task in load_formal_micro_tasks()}
    mapped_ids = {
        candidate.task_id
        for candidate in map_answers_to_memories(FULL_ANSWERS)
        if candidate.task_id
    }
    assert mapped_ids <= formal_ids
    assert len(formal_ids) == 23


def _questionnaire_api_client(monkeypatch, *, saved=None, rejected=None, skipped=None):
    from fastapi.testclient import TestClient

    from weilv.api import app as api

    calls = []
    monkeypatch.setattr(
        api,
        "save_questionnaire",
        lambda *_args, **_kwargs: calls.append(("save", _args)) or (
            rejected
            if rejected is not None
            else saved
        ),
        raising=False,
    )
    monkeypatch.setattr(
        api,
        "skip_questionnaire",
        lambda *_args, **_kwargs: calls.append(("skip", _args)) or (
            rejected if rejected is not None else skipped
        ),
        raising=False,
    )
    api.app.state.es_client = object()
    api.app.state.api_key = "server-only-key"
    return TestClient(api.app), calls


def test_questionnaire_api_schema_requires_no_dependencies():
    from fastapi.testclient import TestClient

    from weilv.api import app as api

    with TestClient(api.app) as client:
        response = client.get("/api/v1/questionnaire")

    assert response.status_code == 200
    assert response.json()["questionnaire_id"] == "v1"
    assert len(response.json()["questions"]) == 7


def test_questionnaire_api_put_returns_minimal_contract(monkeypatch):
    saved = {
        "status": "saved",
        "user_id": "usr_a",
        "questionnaire_id": "v1",
        "completion_state": "completed",
        "updated_at": "2026-08-19T08:00:00+00:00",
        "completed_at": "2026-08-19T08:00:00+00:00",
        "answers": {"rest_preference": "quiet_rest"},
        "memory_record_ids": ["UM-1"],
    }
    client, calls = _questionnaire_api_client(monkeypatch, saved=saved)

    response = client.put("/api/v1/users/usr_a/questionnaire", json={"answers": saved["answers"]})

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "usr_a",
        "questionnaire_id": "v1",
        "completion_state": "completed",
        "updated_at": "2026-08-19T08:00:00+00:00",
        "completed_at": "2026-08-19T08:00:00+00:00",
        "answers": {"rest_preference": "quiet_rest"},
        "memory_record_ids": ["UM-1"],
    }
    assert len(calls) == 1 and calls[0][0] == "save"
    assert calls[0][1][1] == "usr_a"
    assert calls[0][1][2] == saved["answers"]


def test_questionnaire_api_rejects_malformed_and_missing_profile(monkeypatch):
    rejected = {"status": "rejected", "reason_codes": ["invalid_rest_preference"]}
    client, _ = _questionnaire_api_client(monkeypatch, rejected=rejected)

    response = client.put(
        "/api/v1/users/usr_a/questionnaire",
        json={"answers": {"rest_preference": "teleport"}},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid_rest_preference"}


def test_questionnaire_api_skip_endpoint(monkeypatch):
    skipped = {
        "status": "skipped",
        "user_id": "usr_a",
        "questionnaire_id": "v1",
        "completion_state": "skipped",
        "updated_at": "2026-08-19T08:00:00+00:00",
        "completed_at": "2026-08-19T08:00:00+00:00",
        "answers": {},
        "memory_record_ids": [],
    }
    client, calls = _questionnaire_api_client(monkeypatch, skipped=skipped)

    response = client.post("/api/v1/users/usr_a/questionnaire/skip")

    assert response.status_code == 200
    assert response.json()["completion_state"] == "skipped"
    assert response.json()["memory_record_ids"] == []
    assert calls[0][0] == "skip"


def test_questionnaire_api_forbids_extra_client_fields(monkeypatch):
    client, calls = _questionnaire_api_client(monkeypatch, saved={})

    response = client.put(
        "/api/v1/users/usr_a/questionnaire",
        json={"answers": {"rest_preference": "quiet_rest"}, "api_key": "client-key"},
    )

    assert response.status_code == 422
    assert calls == []
