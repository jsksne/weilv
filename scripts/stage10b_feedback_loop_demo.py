"""Stage 10B demo fixture: two users, same request, different feedback memory.

Deterministic and offline: it reuses the frozen pure pipeline pieces (safety
screening + formal task corpus + personalization) and the Stage 10B feedback
mapping.  It demonstrates that behavior feedback shifts ranking per user while
the safe candidate set and all Safety outcomes stay identical.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weilv.basic_rag import BasicRagRequest, _matches_task_metadata, _safety_context
from weilv.feedback_loop import build_feedback_memory_candidate, compute_confidence
from weilv.micro_tasks import load_formal_micro_tasks
from weilv.personal_rag import personalize_task_candidates
from weilv.safety_rules import select_safe_tasks
from weilv.user_memory import build_memory_id

SHARED_REQUEST = {
    "query": "连续读写快40分钟了，想休息一下",
    "target_stage": "junior_high",
    "current_context": "home",
    "available_minutes": 10,
}

USER_A_FEEDBACK = [
    # likes the quiet rest task, dislikes the movement task
    {"task_id": "MT-BREAK-003", "completion_status": "completed", "usefulness": "helpful", "difficulty": "easy"},
    {"task_id": "MT-REC-001", "completion_status": "skipped", "usefulness": "not_helpful", "difficulty": "difficult"},
    {"task_id": "MT-REC-002", "completion_status": "skipped", "usefulness": "not_helpful", "difficulty": "difficult"},
]

USER_B_FEEDBACK = [
    # likes the movement tasks, dislikes the quiet rest task
    {"task_id": "MT-REC-001", "completion_status": "completed", "usefulness": "helpful", "difficulty": "easy"},
    {"task_id": "MT-REC-002", "completion_status": "completed", "usefulness": "helpful", "difficulty": "easy"},
    {"task_id": "MT-BREAK-003", "completion_status": "skipped", "usefulness": "not_helpful", "difficulty": "difficult"},
]


def _safe_candidates() -> list[dict]:
    request = BasicRagRequest(**SHARED_REQUEST)
    formal_tasks = load_formal_micro_tasks()
    metadata_tasks = [task for task in formal_tasks if _matches_task_metadata(task, request)]
    safe = select_safe_tasks(metadata_tasks, _safety_context(request))
    assert safe["status"] == "allowed", safe
    positions = {task["task_id"]: position for position, task in enumerate(formal_tasks)}
    for task in safe["tasks"]:
        task["rerank_rank"] = positions[task["task_id"]] + 1
    return safe["tasks"]


def _feedback_memories(user_id: str, events: list[dict]) -> list[dict]:
    from dataclasses import asdict

    memories = []
    previous = None
    for event in events:
        confidence = compute_confidence(previous, event["usefulness"])
        candidate = build_feedback_memory_candidate(user_id, event["task_id"], event, confidence, "t")
        memory = asdict(candidate)
        memory["memory_id"] = build_memory_id(candidate)
        memories.append(memory)
        previous = {"helpfulness": candidate.memory_value["helpfulness"], "confidence": confidence}
    return memories


def main() -> None:
    safe_tasks = _safe_candidates()
    baseline = [{"rank": i + 1, "task_id": t["task_id"], "title": t["title"]} for i, t in enumerate(safe_tasks)]
    memories_a = _feedback_memories("demo_user_a", USER_A_FEEDBACK)
    memories_b = _feedback_memories("demo_user_b", USER_B_FEEDBACK)
    ranking_a = personalize_task_candidates([dict(t) for t in safe_tasks], memories_a)
    ranking_b = personalize_task_candidates([dict(t) for t in safe_tasks], memories_b)

    def top3(ranking):
        return [
            {"rank": i + 1, "task_id": t["task_id"], "delta": t["personalization"]["personalization_delta"]}
            for i, t in enumerate(ranking[:3])
        ]

    report = {
        "artifact": "stage10b_feedback_loop_demo",
        "created_at": datetime.now(UTC).isoformat(),
        "same_request": SHARED_REQUEST,
        "safe_candidate_set": [t["task_id"] for t in baseline],
        "no_safety_rule_change": True,
        "user_a": {"feedback_events": USER_A_FEEDBACK, "memory_records": memories_a, "top3": top3(ranking_a)},
        "user_b": {"feedback_events": USER_B_FEEDBACK, "memory_records": memories_b, "top3": top3(ranking_b)},
        "assertions": {
            "same_input": True,
            "different_memory": memories_a != memories_b,
            "different_ranking": top3(ranking_a) != top3(ranking_b),
            "candidate_set_invariant": {t["task_id"] for t in ranking_a} == {t["task_id"] for t in baseline} == {t["task_id"] for t in ranking_b},
        },
    }

    assert report["assertions"]["different_memory"]
    assert report["assertions"]["different_ranking"]
    assert report["assertions"]["candidate_set_invariant"]

    out_dir = ROOT / ".runtime" / "stage10b_demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "stage10b_demo_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"demo report: {report_path}")
    print("safe candidate set:", len(baseline))
    print("baseline top3:", [(i["rank"], i["task_id"]) for i in baseline[:3]])
    print("User A top3  :", [(i["rank"], i["task_id"]) for i in top3(ranking_a)])
    print("User B top3  :", [(i["rank"], i["task_id"]) for i in top3(ranking_b)])
    print("assertions:", report["assertions"])


if __name__ == "__main__":
    main()
