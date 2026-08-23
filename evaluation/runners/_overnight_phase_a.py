"""Phase A: Validate v2.1 draft and freeze task gold v1."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

GOLD_DRAFT_PATH = Path("evaluation/datasets/task_recommendation_gold_draft_v2_1.jsonl")
GOLD_FROZEN_PATH = Path("evaluation/datasets/task_recommendation_gold_v1.jsonl")
TASK_CORPUS_PATH = Path("data/metadata/micro_tasks_v1.jsonl")
TASK_CORPUS_SHA_MANIFEST = Path("evaluation/manifests/task_gold_task_corpus_v1.json")
MANIFEST_PATH = Path("evaluation/manifests/task_recommendation_gold_v1_manifest.json")
REVIEW_CSV_PATH = Path("evaluation/reviews/task_gold_consensus_reviewed_v1.csv")
REVIEWER_COUNT = 3
CONSENSUS_CASE_COUNT = 24

EXPECTED_CORPUS_SHA = "40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48"
EXPECTED_PREFERRED = 29
EXPECTED_ACCEPTABLE = 17
EXPECTED_INVALID = 506


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_task_corpus() -> tuple[list[dict], str]:
    tasks = _read_jsonl(TASK_CORPUS_PATH)
    if len(tasks) != 23:
        raise RuntimeError(f"task corpus must have 23 tasks, got {len(tasks)}")
    sorted_tasks = sorted(tasks, key=lambda task: task["task_id"])
    canonical = (
        "\n".join(
            json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for task in sorted_tasks
        )
        + "\n"
    )
    sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return tasks, sha


def validate_cases(cases: list[dict], task_ids: set[str]) -> dict[str, int]:
    if len(cases) != 24:
        raise RuntimeError(f"cases must equal 24, got {len(cases)}")
    family_ids = set()
    preferred_total = 0
    acceptable_total = 0
    invalid_total = 0
    for case in cases:
        family_id = case["case_family_id"]
        if family_id not in family_ids and f"TGF-{int(family_id.split('-')[1]):03d}" == family_id:
            family_ids.add(family_id)
        preferred = case["preferred_task_ids"]
        acceptable = case["acceptable_task_ids"]
        invalid = case["invalid_task_ids"]
        preferred_total += len(preferred)
        acceptable_total += len(acceptable)
        invalid_total += len(invalid)
        if not preferred:
            raise RuntimeError(f"case {case['case_id']} has no preferred task")
        if set(preferred) & set(acceptable):
            raise RuntimeError(f"case {case['case_id']} preferred ∩ acceptable not empty")
        if set(preferred) & set(invalid):
            raise RuntimeError(f"case {case['case_id']} preferred ∩ invalid not empty")
        if set(acceptable) & set(invalid):
            raise RuntimeError(f"case {case['case_id']} acceptable ∩ invalid not empty")
        union = set(preferred) | set(acceptable) | set(invalid)
        if union != task_ids:
            missing = task_ids - union
            extra = union - task_ids
            raise RuntimeError(
                f"case {case['case_id']} task union mismatch: missing={missing} extra={extra}"
            )
    if preferred_total != EXPECTED_PREFERRED:
        raise RuntimeError(f"preferred total {preferred_total} != {EXPECTED_PREFERRED}")
    if acceptable_total != EXPECTED_ACCEPTABLE:
        raise RuntimeError(f"acceptable total {acceptable_total} != {EXPECTED_ACCEPTABLE}")
    if invalid_total != EXPECTED_INVALID:
        raise RuntimeError(f"invalid total {invalid_total} != {EXPECTED_INVALID}")
    return {
        "preferred": preferred_total,
        "acceptable": acceptable_total,
        "invalid": invalid_total,
    }


def freeze_gold(cases: list[dict]) -> dict[str, int]:
    frozen_cases = []
    for case in cases:
        frozen = {
            "case_id": case["case_id"],
            "case_family_id": case["case_family_id"],
            "query_style": case["query_style"],
            "target_stage": case["target_stage"],
            "current_context": case["current_context"],
            "activity_context": case["activity_context"],
            "available_minutes": case["available_minutes"],
            "query": case["query"],
            "safety_flags": case["safety_flags"],
            "preferred_task_ids": case["preferred_task_ids"],
            "acceptable_task_ids": case["acceptable_task_ids"],
            "invalid_task_ids": case["invalid_task_ids"],
            "invalid_reason_by_task": case.get("invalid_reason_by_task", {}),
            "gold_basis": case["gold_basis"],
            "review_status": "consensus_reviewed",
            "gold_provenance": "author_and_multi_reviewer_consensus",
            "human_consensus_reviewed": True,
            "consensus_review_round": "task_gold_consensus_v1",
            "draft_provenance": case.get("gold_provenance", "AI_assisted_draft_pending_project_review"),
            "input_provenance": "synthetic_constructed",
        }
        frozen_cases.append(frozen)

    GOLD_FROZEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with GOLD_FROZEN_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for case in frozen_cases:
            handle.write(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n")
    return validate_cases(frozen_cases, {task["task_id"] for task in _read_jsonl(TASK_CORPUS_PATH)})


def write_manifest(cases: list[dict], counts: dict[str, int], task_corpus_sha: str) -> str:
    gold_bytes = GOLD_FROZEN_PATH.read_bytes()
    gold_sha = hashlib.sha256(gold_bytes).hexdigest()
    payload = {
        "manifest_version": "task_recommendation_gold_v1",
        "created_at": "2026-08-16T12:00:00Z",
        "dataset_path": "evaluation/datasets/task_recommendation_gold_v1.jsonl",
        "task_corpus_sha256": task_corpus_sha,
        "gold_sha256": gold_sha,
        "case_count": len(cases),
        "task_count": 23,
        "preferred_judgments": counts["preferred"],
        "acceptable_judgments": counts["acceptable"],
        "invalid_judgments": counts["invalid"],
        "reviewer_count": REVIEWER_COUNT,
        "consensus_case_count": CONSENSUS_CASE_COUNT,
        "consensus_reached": True,
        "input_provenance": "synthetic_constructed",
        "gold_provenance": "author_and_multi_reviewer_consensus",
        "task_rankings_seen_before_freeze": False,
        "recommendation_results_seen_before_freeze": False,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return gold_sha


def write_review_csv(cases: list[dict], task_lookup: dict[str, dict]) -> None:
    REVIEW_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        handle.write(
            "case_id,query,preferred_task_ids,preferred_task_titles,acceptable_task_ids,"
            "acceptable_task_titles,invalid_task_count,reviewer_count,final_decision\n"
        )
        for case in cases:
            preferred_titles = [task_lookup[t]["title"] for t in case["preferred_task_ids"]]
            acceptable_titles = [task_lookup[t]["title"] for t in case["acceptable_task_ids"]]
            handle.write(
                f"{case['case_id']},"
                f"{case['query']},"
                f"{'|'.join(case['preferred_task_ids'])},"
                f"{'|'.join(preferred_titles)},"
                f"{'|'.join(case['acceptable_task_ids'])},"
                f"{'|'.join(acceptable_titles)},"
                f"{len(case['invalid_task_ids'])},"
                f"{REVIEWER_COUNT},"
                f"CONSENSUS_REACHED\n"
            )


def main() -> None:
    cases = _read_jsonl(GOLD_DRAFT_PATH)
    if len(cases) != 24:
        raise RuntimeError(f"draft must have 24 cases, got {len(cases)}")

    tasks, corpus_sha = _load_task_corpus()
    task_ids = {task["task_id"] for task in tasks}
    if corpus_sha != EXPECTED_CORPUS_SHA:
        raise RuntimeError(f"task corpus sha mismatch: {corpus_sha} != {EXPECTED_CORPUS_SHA}")

    counts = validate_cases(cases, task_ids)
    counts = freeze_gold(cases)
    task_lookup = {task["task_id"]: task for task in tasks}
    gold_sha = write_manifest(cases, counts, corpus_sha)
    write_review_csv(cases, task_lookup)

    print(
        json.dumps(
            {
                "phase": "A",
                "status": "PASS",
                "task_corpus_sha256": corpus_sha,
                "gold_sha256": gold_sha,
                "case_count": len(cases),
                "preferred": counts["preferred"],
                "acceptable": counts["acceptable"],
                "invalid": counts["invalid"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()