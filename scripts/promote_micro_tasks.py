"""Promote the approved Stage 1 micro-task candidate without rewriting task content."""

import json
from pathlib import Path

from weilv.micro_tasks import embedding_text

__all__ = ["embedding_text"]

SOURCE = Path("data/metadata/micro_tasks.final-candidate.v0.2.jsonl")
TARGET = Path("data/metadata/micro_tasks_v1.jsonl")
FIELDS = (
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
)

SAFETY_CAPABILITIES = {
    "MT-BREAK-003": ["continue_study"],
    "MT-BREAK-004": ["requires_standing", "requires_movement"],
    "MT-SED-001": ["requires_standing", "requires_movement", "continue_study"],
    "MT-SED-002": ["requires_standing", "requires_movement"],
    "MT-EYE-001": ["continue_study"],
    "MT-EYE-002": ["continue_study"],
    "MT-EYE-003": ["pause_reading_or_screen", "continue_study"],
    "MT-EYE-004": ["continue_study"],
    "MT-EYE-007": ["continue_study"],
    "MT-OUT-001": ["requires_outdoor"],
    "MT-REC-001": ["requires_movement"],
    "MT-REC-002": ["requires_movement"],
}
def main() -> None:
    candidates = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines()]
    if len(candidates) != 23 or {item["review_status"] for item in candidates} != {
        "pending_human_review"
    }:
        raise RuntimeError("expected exactly 23 pending final candidates")

    reviewed = []
    for candidate in candidates:
        item = {field: candidate[field] for field in FIELDS}
        item["review_status"] = "content_reviewed"
        item["safety_capabilities"] = SAFETY_CAPABILITIES.get(item["task_id"], [])
        reviewed.append(item)

    TARGET.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) for item in reviewed)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
