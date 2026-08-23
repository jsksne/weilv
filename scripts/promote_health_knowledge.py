"""Promote the approved Stage 1 candidate without rewriting health content."""

import json
from pathlib import Path

SOURCE = Path("data/metadata/health_knowledge.final-candidate.v0.1.jsonl")
TARGET = Path("data/metadata/health_knowledge_v1.jsonl")
FIELDS = (
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
)
SPECIAL_CHUNK_ID = "KC-SRC-007-005"
SPECIAL_USES = ["safety_rule_evidence", "exclude_from_normal_recommendation"]


def main() -> None:
    candidates = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines()]
    if len(candidates) != 29 or {item["review_status"] for item in candidates} != {
        "pending_human_review"
    }:
        raise RuntimeError("expected exactly 29 pending final candidates")

    reviewed = []
    for candidate in candidates:
        item = {field: candidate[field] for field in FIELDS}
        item["review_status"] = "content_reviewed"
        if item["chunk_id"] == SPECIAL_CHUNK_ID:
            item["proposed_use"] = SPECIAL_USES
        reviewed.append(item)

    if sum(item["chunk_id"] == SPECIAL_CHUNK_ID for item in reviewed) != 1:
        raise RuntimeError(f"expected exactly one {SPECIAL_CHUNK_ID}")

    TARGET.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) for item in reviewed)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
