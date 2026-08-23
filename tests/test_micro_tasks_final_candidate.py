import json
import runpy
from pathlib import Path

TASK_PATH = Path("data/metadata/micro_tasks.final-candidate.v0.2.jsonl")
KNOWLEDGE_PATH = Path("data/metadata/health_knowledge_v1.jsonl")
REVIEWED_PATH = Path("data/metadata/micro_tasks_v1.jsonl")
ALLOWED_CONTEXTS = {"home", "school", "study_space", "commute", "bedroom", "outdoor"}
REQUIRED_FIELDS = {
    "task_id",
    "title",
    "instruction",
    "domain",
    "covered_domains",
    "evidence_chunk_ids",
    "safety_evidence_chunk_ids",
    "target_stage",
    "context_tags",
    "trigger",
    "execution_contexts",
    "device_required_during_execution",
    "estimated_minutes",
    "burden_level",
    "safety_level",
    "applicability",
    "contraindications",
    "stop_conditions",
    "review_status",
}


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_micro_task_candidate_stays_complete_and_behind_approval_gate():
    tasks = _load_jsonl(TASK_PATH)

    assert len(tasks) == 23
    assert len({task["task_id"] for task in tasks}) == 23
    assert all(REQUIRED_FIELDS <= task.keys() for task in tasks)
    assert {task["review_status"] for task in tasks} == {"pending_human_review"}
    assert all(task["execution_contexts"] for task in tasks)
    assert all(set(task["execution_contexts"]) <= ALLOWED_CONTEXTS for task in tasks)
    assert all(type(task["device_required_during_execution"]) is bool for task in tasks)


def test_all_evidence_is_valid_and_many_to_many_relationships_are_preserved():
    tasks = _load_jsonl(TASK_PATH)
    knowledge = {item["chunk_id"]: item for item in _load_jsonl(KNOWLEDGE_PATH)}
    evidence_ids = [chunk_id for task in tasks for chunk_id in task["evidence_chunk_ids"]]
    safety_ids = [
        chunk_id for task in tasks for chunk_id in task["safety_evidence_chunk_ids"]
    ]

    assert all(chunk_id in knowledge for chunk_id in evidence_ids)
    assert all(knowledge[chunk_id]["review_status"] == "content_reviewed" for chunk_id in evidence_ids)
    assert all("micro_task_evidence" in knowledge[chunk_id]["proposed_use"] for chunk_id in evidence_ids)
    assert all(chunk_id in knowledge for chunk_id in safety_ids)
    assert any(len(task["evidence_chunk_ids"]) > 1 for task in tasks)
    assert len(evidence_ids) > len(set(evidence_ids))


def test_reviewed_micro_tasks_match_candidate_except_for_status_promotion():
    candidates = {item["task_id"]: item for item in _load_jsonl(TASK_PATH)}
    reviewed = _load_jsonl(REVIEWED_PATH)

    assert len(reviewed) == 23
    assert len({item["task_id"] for item in reviewed}) == 23
    assert all(set(item) == REQUIRED_FIELDS | {"safety_capabilities"} for item in reviewed)
    assert {item["review_status"] for item in reviewed} == {"content_reviewed"}

    for item in reviewed:
        expected = {field: candidates[item["task_id"]][field] for field in REQUIRED_FIELDS}
        expected["review_status"] = "content_reviewed"
        expected["safety_capabilities"] = item["safety_capabilities"]
        assert item == expected


def test_embedding_text_uses_only_task_retrieval_fields():
    embedding_text = runpy.run_path("scripts/promote_micro_tasks.py")["embedding_text"]
    task = _load_jsonl(REVIEWED_PATH)[0]
    expected_parts = [
        task["title"],
        task["instruction"],
        task["trigger"],
        task["domain"],
        *task["covered_domains"],
        *task["context_tags"],
        *task["execution_contexts"],
    ]

    assert embedding_text(task) == "\n".join(expected_parts)
