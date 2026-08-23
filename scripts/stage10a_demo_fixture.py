"""Stage 10A demo fixture: two questionnaire profiles, one shared request.

Deterministic and offline: it reuses the frozen pure pipeline pieces
(safety screening + formal task corpus + personalization), so it needs no
Elasticsearch and no model API keys.  It demonstrates that cold-start
questionnaire memory may re-rank a recommendation but can never change the
safe candidate set or any Safety rule outcome.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weilv.basic_rag import BasicRagRequest, _matches_task_metadata, _safety_context
from weilv.micro_tasks import load_formal_micro_tasks
from weilv.personal_rag import personalize_task_candidates
from weilv.questionnaire import map_answers_to_memories
from weilv.safety_rules import select_safe_tasks

SHARED_REQUEST = {
    "query": "连续读写快40分钟了，想休息一下",
    "target_stage": "junior_high",
    "current_context": "home",
    "available_minutes": 10,
}

USER_A = {
    "name": "User A（喜欢安静休息，不喜欢活动打断）",
    "answers": {
        "bedtime": "2130_2230",
        "screen_duration": "60_120",
        "rest_preference": "quiet_rest",
        "annoying_reminders": ["activity"],
        "main_context": "home",
        "leave_seat_allowed": "not_allowed",
        "break_minutes": "10_20",
    },
}

USER_B = {
    "name": "User B（喜欢轻微活动与户外）",
    "answers": {
        "bedtime": "2230_2330",
        "screen_duration": "30_60",
        "rest_preference": "light_activity",
        "annoying_reminders": ["none"],
        "main_context": "school",
        "leave_seat_allowed": "allowed",
        "break_minutes": "5_10",
    },
}


def _safe_candidates() -> list[dict]:
    request = BasicRagRequest(**SHARED_REQUEST)
    formal_tasks = load_formal_micro_tasks()
    metadata_tasks = [task for task in formal_tasks if _matches_task_metadata(task, request)]
    safe = select_safe_tasks(metadata_tasks, _safety_context(request))
    assert safe["status"] == "allowed", safe
    # deterministic base ranks follow the formal corpus order
    positions = {task["task_id"]: position for position, task in enumerate(formal_tasks)}
    for task in safe["tasks"]:
        task["rerank_rank"] = positions[task["task_id"]] + 1
    return safe["tasks"]


def _run(profile: dict, tasks: list[dict], user_id: str) -> dict:
    memories = [
        _memory_doc(memory, user_id) for memory in map_answers_to_memories(profile["answers"])
    ]
    personalized = personalize_task_candidates(
        [dict(task) for task in tasks],
        memories,
    )
    return {
        "memory_count": len(memories),
        "memory_records": memories,
        "ranking": [
            {
                "rank": position,
                "task_id": task["task_id"],
                "title": task["title"],
                "personalization_delta": task["personalization"]["personalization_delta"],
                "reason_codes": task["personalization"]["reason_codes"],
            }
            for position, task in enumerate(personalized, start=1)
        ],
    }


def _memory_doc(candidate, user_id: str) -> dict:
    from dataclasses import asdict

    from weilv.user_memory import UserMemoryCandidate, build_memory_id

    candidate = UserMemoryCandidate(**{**asdict(candidate), "user_id": user_id})
    memory = asdict(candidate)
    memory["memory_id"] = build_memory_id(candidate)
    return memory


def main() -> None:
    safe_tasks = _safe_candidates()
    baseline = [
        {
            "rank": position,
            "task_id": task["task_id"],
            "title": task["title"],
            "rerank_rank": task["rerank_rank"],
        }
        for position, task in enumerate(safe_tasks, start=1)
    ]
    result_a = _run(USER_A, safe_tasks, "demo_user_a")
    result_b = _run(USER_B, safe_tasks, "demo_user_b")

    safe_set = {item["task_id"] for item in baseline}
    ranked_a = {item["task_id"] for item in result_a["ranking"]}
    ranked_b = {item["task_id"] for item in result_b["ranking"]}
    assert safe_set == ranked_a == ranked_b, "candidate set must stay invariant"
    assert all(
        memory["memory_type"] != "task_feedback"
        for memory in [*result_a["memory_records"], *result_b["memory_records"]]
    )
    assert result_a["ranking"][:3] != result_b["ranking"][:3], "rankings should differ"

    report = {
        "artifact": "stage10a_demo_fixture",
        "created_at": datetime.now(UTC).isoformat(),
        "same_request": SHARED_REQUEST,
        "safe_candidate_set": [item["task_id"] for item in baseline],
        "safe_matched_rule_ids": [],
        "no_safety_rule_change": True,
        "users": {
            "user_a": {"name": USER_A["name"], "answers": USER_A["answers"], **result_a},
            "user_b": {"name": USER_B["name"], "answers": USER_B["answers"], **result_b},
        },
        "assertions": {
            "candidate_set_invariant": True,
            "no_fake_task_feedback": True,
            "different_ranking": True,
            "top1_user_a": result_a["ranking"][0]["task_id"],
            "top1_user_b": result_b["ranking"][0]["task_id"],
        },
    }

    out_dir = ROOT / ".runtime" / "stage10a_demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "stage10a_demo_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"demo report: {report_path}")
    print(f"safe candidate set ({len(baseline)}): {', '.join(sorted(safe_set))}")
    print("baseline top3 :", [(i["rank"], i["task_id"]) for i in baseline[:3]])
    print("User A top3   :", [(i["rank"], i["task_id"]) for i in result_a["ranking"][:3]])
    print("User B top3   :", [(i["rank"], i["task_id"]) for i in result_b["ranking"][:3]])
    print("assertions:", report["assertions"])


if __name__ == "__main__":
    main()
