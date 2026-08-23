"""Stage 10B feedback loop tests: writeback, provenance, confidence, boundaries."""

from dataclasses import asdict

import pytest
from elasticsearch import ConflictError, NotFoundError

from weilv.feedback_loop import (
    build_feedback_memory_candidate,
    build_feedback_memory_value,
    compute_confidence,
    get_feedback_memory_value,
    map_difficulty,
    map_usefulness,
)
from weilv.micro_tasks import load_formal_micro_tasks
from weilv.personal_rag import personalize_task_candidates
from weilv.user_memory import (
    USER_MEMORY_INDEX,
    UserMemoryCandidate,
    UserProfile,
    create_memory,
    update_memory,
)


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


def _profile(user_id="usr_a"):
    return UserProfile(user_id, "junior_high", True, "created", "updated")


def _client(user_id="usr_a"):
    client = FakeClient()
    client.docs[("user_profiles_v1", user_id)] = {
        "user_id": user_id,
        "target_stage": "junior_high",
        "memory_enabled": True,
        "created_at": "2026-08-13T10:00:00+08:00",
        "updated_at": "2026-08-13T10:00:00+08:00",
    }
    return client


def _feedback(**changes):
    payload = {
        "completion_status": "completed",
        "usefulness": "helpful",
        "difficulty": "easy",
        "reason": "",
    }
    payload.update(changes)
    return payload


def _persist(client, user_id, task_id, feedback, confidence):
    from weilv.user_memory import build_memory_id

    candidate = build_feedback_memory_candidate(
        user_id, task_id, feedback, confidence, "2026-08-19T10:00:00+08:00"
    )
    memory_id = build_memory_id(candidate)
    candidate = UserMemoryCandidate(**{**asdict(candidate), "memory_id": memory_id})
    result = create_memory(client, _profile(user_id), candidate, {task_id})
    if result["status"] == "already_exists":
        result = update_memory(client, _profile(user_id), candidate, {task_id})
    return candidate, result["memory_id"]


def _task_candidates():
    tasks = []
    for position, task in enumerate(load_formal_micro_tasks(), start=1):
        if task["task_id"] in {"MT-BREAK-003", "MT-REC-001", "MT-REC-002", "MT-SED-001"}:
            tasks.append({"task_id": task["task_id"], "title": task["title"], "rerank_rank": position})
    return tasks


def _memory_dict(candidate):
    memory = asdict(candidate)
    memory["memory_id"] = candidate.memory_id
    return memory


def test_feedback_save_writes_one_upserted_memory():
    client = _client()
    feedback = _feedback()
    confidence = compute_confidence(None, feedback["usefulness"])
    _, memory_id = _persist(client, "usr_a", "MT-SED-001", feedback, confidence)

    stored = client.docs[(USER_MEMORY_INDEX, memory_id)]
    assert stored["memory_type"] == "task_feedback"
    assert stored["memory_value"] == {
        "completion_status": "completed",
        "helpfulness": 5,
        "burden": "easy",
        "confidence": 1,
    }
    # repeated feedback upserts the same document (no uncontrolled growth)
    _, same_id = _persist(client, "usr_a", "MT-SED-001", _feedback(), 2)
    assert same_id == memory_id
    memory_docs = [k for k in client.docs if k[0] == USER_MEMORY_INDEX]
    assert len(memory_docs) == 1


def test_memory_provenance_timestamp_task_and_confidence():
    client = _client()
    feedback = _feedback(completion_status="skipped", usefulness="not_helpful", difficulty="difficult")
    _, memory_id = _persist(client, "usr_a", "MT-REC-001", feedback, 1)

    stored = client.docs[(USER_MEMORY_INDEX, memory_id)]
    assert stored["source_type"] == "structured_task_feedback"
    assert stored["task_id"] == "MT-REC-001"
    assert stored["created_at"] == "2026-08-19T10:00:00+08:00"
    assert stored["memory_value"]["confidence"] == 1


def test_feedback_preserves_questionnaire_memory():
    client = _client()
    # seed a questionnaire_cold_start preference exactly like Stage 10A would
    questionnaire_candidate = UserMemoryCandidate(
        memory_id="",
        user_id="usr_a",
        memory_type="task_preference",
        source_type="questionnaire_cold_start",
        task_id="MT-BREAK-003",
        domain="study_break",
        memory_key="task_preference",
        memory_value={"preference": "prefer_task"},
        created_at="2026-08-19T09:00:00+08:00",
        updated_at="2026-08-19T09:00:00+08:00",
    )
    created = create_memory(client, _profile(), questionnaire_candidate, {"MT-BREAK-003"})
    assert created["status"] == "created"
    questionnaire_id = created["memory_id"]

    _persist(client, "usr_a", "MT-SED-001", _feedback(), 1)

    assert (USER_MEMORY_INDEX, questionnaire_id) in client.docs
    assert client.docs[(USER_MEMORY_INDEX, questionnaire_id)]["source_type"] == "questionnaire_cold_start"
    assert client.docs[(USER_MEMORY_INDEX, questionnaire_id)]["memory_value"] == {
        "preference": "prefer_task"
    }


def test_feedback_overrides_weak_questionnaire_preference():
    # questionnaire: prefer_task MT-REC-001 (+3)
    prefer = UserMemoryCandidate(
        memory_id="",
        user_id="usr_a",
        memory_type="task_preference",
        source_type="questionnaire_cold_start",
        task_id="MT-REC-001",
        domain="light_recovery",
        memory_key="task_preference",
        memory_value={"preference": "prefer_task"},
        created_at="t",
        updated_at="t",
    )
    prefer_mem = _memory_dict(prefer)
    prefer_mem["memory_id"] = "UM-prefer"

    # repeated behavior: skipped + not helpful + hard -> delta -4 per event
    feedback_mem = _memory_dict(
        build_feedback_memory_candidate(
            "usr_a", "MT-REC-001", _feedback(completion_status="skipped", usefulness="not_helpful", difficulty="difficult"), 1, "t"
        )
    )
    feedback_mem["memory_id"] = "UM-feedback"

    tasks = _task_candidates()
    only_preference = personalize_task_candidates([dict(t) for t in tasks], [prefer_mem])
    after_feedback = personalize_task_candidates([dict(t) for t in tasks], [prefer_mem, feedback_mem])

    pref_rank = next(
        t["personalization"]["adjusted_rank"]
        for t in only_preference
        if t["task_id"] == "MT-REC-001"
    )
    feedback_rank = next(
        t["personalization"]["adjusted_rank"]
        for t in after_feedback
        if t["task_id"] == "MT-REC-001"
    )
    # feedback (-4) outweighs the weak questionnaire preference (+3): the task's
    # adjusted rank flips from boosted to penalized.
    assert pref_rank == 19  # base 22 - 3
    assert feedback_rank == 23  # base 22 + (-4 + 3)
    assert feedback_rank > pref_rank


def test_contradictory_feedback_decays_confidence():
    assert compute_confidence(None, "helpful") == 1
    assert compute_confidence({"helpfulness": 5, "confidence": 1}, "helpful") == 2
    assert compute_confidence({"helpfulness": 5, "confidence": 2}, "not_helpful") == 1
    # floor at 1 and unchanged on neutral
    assert compute_confidence({"helpfulness": 2, "confidence": 1}, "helpful") == 1
    assert compute_confidence({"helpfulness": 5, "confidence": 5}, "neutral") == 5
    # cap at 10
    assert compute_confidence({"helpfulness": 5, "confidence": 10}, "helpful") == 10


def test_user_isolation():
    client = _client("usr_a")
    _persist(client, "usr_a", "MT-SED-001", _feedback(), 1)

    assert get_feedback_memory_value(client, "usr_b", "MT-SED-001") is None
    # memory id embeds the user: querying user B never sees user A's record
    probe = build_feedback_memory_candidate("usr_a", "MT-SED-001", _feedback(), 1, "t")
    from weilv.user_memory import get_memory

    assert get_memory(client, "usr_b", probe.memory_id) is None


def test_candidate_set_invariance_with_feedback_memory():
    tasks = _task_candidates()
    baseline = {t["task_id"] for t in tasks}
    feedback_mem = _memory_dict(
        build_feedback_memory_candidate(
            "usr_a", "MT-REC-001", _feedback(usefulness="helpful"), 1, "t"
        )
    )
    personalized = personalize_task_candidates([dict(t) for t in tasks], [feedback_mem])
    assert {t["task_id"] for t in personalized} == baseline


def test_blocked_task_cannot_return_via_positive_feedback():
    from weilv.basic_rag import BasicRagRequest, _matches_task_metadata
    from weilv.safety_rules import select_safe_tasks

    request = BasicRagRequest(
        query="想休息一下", target_stage="junior_high", current_context="bedroom", available_minutes=10
    )
    metadata_tasks = [t for t in load_formal_micro_tasks() if _matches_task_metadata(t, request)]
    safe = select_safe_tasks(metadata_tasks, {"target_stage": "junior_high"})
    assert "MT-OUT-001" not in {t["task_id"] for t in safe["tasks"]}  # context mismatch

    praise = _memory_dict(
        build_feedback_memory_candidate(
            "usr_a", "MT-OUT-001", _feedback(usefulness="helpful"), 3, "t"
        )
    )
    personalized = personalize_task_candidates(list(safe["tasks"]), [praise])
    assert "MT-OUT-001" not in {t["task_id"] for t in personalized}


def test_malformed_feedback_fails_safely():
    for usefulness in ("amazing", "", None):
        with pytest.raises(ValueError):
            map_usefulness(usefulness)
    for difficulty in ("impossible", "", None):
        with pytest.raises(ValueError):
            map_difficulty(difficulty)
    with pytest.raises(ValueError):
        compute_confidence(None, "bad")
    with pytest.raises(ValueError):
        build_feedback_memory_value("completed", "bad", "easy", 1)

    from weilv.user_memory import validate_memory_candidate

    bad = build_feedback_memory_candidate(
        "usr_a", "MT-SED-001", _feedback(), 11, "t"
    )
    assert validate_memory_candidate(_profile(), bad, {"MT-SED-001"}) == {
        "valid": False,
        "reason_codes": ["invalid_confidence"],
    }


def test_recommendation_changes_after_repeated_feedback():
    tasks = _task_candidates()
    baseline = [t["task_id"] for t in personalize_task_candidates([dict(t) for t in tasks], [])]
    top = baseline[0]

    feedback_mem = _memory_dict(
        build_feedback_memory_candidate(
            "usr_a",
            top,
            _feedback(completion_status="skipped", usefulness="not_helpful", difficulty="difficult"),
            2,
            "t",
        )
    )
    changed = personalize_task_candidates([dict(t) for t in tasks], [feedback_mem])
    assert changed[0]["task_id"] != top  # repeated negative feedback demotes the top task


def test_confidence_written_back_via_upsert_accumulates():
    client = _client()
    first = _feedback(usefulness="helpful")
    _, memory_id = _persist(client, "usr_a", "MT-SED-001", first, 1)
    # a second consistent event reads the stored confidence and raises it
    previous = get_feedback_memory_value(client, "usr_a", "MT-SED-001")
    assert previous["confidence"] == 1
    confidence = compute_confidence(previous, "helpful")
    _, memory_id2 = _persist(client, "usr_a", "MT-SED-001", _feedback(usefulness="helpful"), confidence)
    assert memory_id2 == memory_id
    assert client.docs[(USER_MEMORY_INDEX, memory_id)]["memory_value"]["confidence"] == 2
