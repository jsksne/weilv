import json
from pathlib import Path

CANDIDATE_PATH = Path("data/metadata/health_knowledge.final-candidate.v0.1.jsonl")
SOURCE_METADATA_PATH = Path("data/metadata/source_documents.jsonl")
REVIEWED_PATH = Path("data/metadata/health_knowledge_v1.jsonl")
ALLOWED_STAGES = {"primary_upper", "junior_high", "senior_high"}
REQUIRED_FIELDS = {
    "chunk_id",
    "document_id",
    "title",
    "section_path",
    "content",
    "domain",
    "target_stage",
    "applicability",
    "warnings",
    "source_locator",
    "source_url",
    "published_at",
    "knowledge_role",
    "proposed_use",
    "review_status",
}


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_final_candidate_is_complete_and_stays_behind_human_approval_gate():
    chunks = _load_jsonl(CANDIDATE_PATH)
    source_ids = {
        item["document_id"] for item in _load_jsonl(SOURCE_METADATA_PATH)
    }

    assert len(chunks) == 29
    assert len({chunk["chunk_id"] for chunk in chunks}) == 29
    assert all(REQUIRED_FIELDS <= chunk.keys() for chunk in chunks)
    assert all(set(chunk["target_stage"]) <= ALLOWED_STAGES for chunk in chunks)
    assert all(chunk["source_locator"] for chunk in chunks)
    assert all(chunk["document_id"] in source_ids for chunk in chunks)
    assert {chunk["review_status"] for chunk in chunks} == {"pending_human_review"}


def test_src_001_is_source_verified_without_content_approval():
    sources = {item["document_id"]: item for item in _load_jsonl(SOURCE_METADATA_PATH)}

    assert sources["SRC-001"]["review_status"] == "source_verified"
    assert sources["SRC-001"]["allowed_for_knowledge_index"] is False


def test_reviewed_knowledge_matches_candidate_except_for_approved_metadata_changes():
    candidates = {item["chunk_id"]: item for item in _load_jsonl(CANDIDATE_PATH)}
    reviewed = _load_jsonl(REVIEWED_PATH)

    assert len(reviewed) == 29
    assert len({item["chunk_id"] for item in reviewed}) == 29
    assert all(set(item) == REQUIRED_FIELDS for item in reviewed)
    assert {item["review_status"] for item in reviewed} == {"content_reviewed"}

    for item in reviewed:
        candidate = candidates[item["chunk_id"]]
        expected = {field: candidate[field] for field in REQUIRED_FIELDS}
        expected["review_status"] = "content_reviewed"
        if item["chunk_id"] == "KC-SRC-007-005":
            expected["proposed_use"] = [
                "safety_rule_evidence",
                "exclude_from_normal_recommendation",
            ]
        assert item == expected
