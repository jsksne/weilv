"""Run exactly the three non-formal Stage 7A engineering smoke cases."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from elasticsearch import Elasticsearch

from weilv.agentic_rag import run_agentic_rag
from weilv.basic_rag import BasicRagRequest
from weilv.micro_tasks import load_formal_micro_tasks
from weilv.personal_memory_retrieval import embed_memory
from weilv.retrieval_slice import _env_value, load_api_key
from weilv.user_memory import (
    UserMemoryCandidate,
    UserProfile,
    build_memory_id,
    create_memory,
    forget_memory,
    upsert_user_profile,
)


def _summary(result: dict) -> dict:
    diagnostics = result["diagnostics"]
    return {
        "status": result["status"],
        "selected_task_id": diagnostics["selected_task_id"],
        "factor_count": diagnostics["factor_count"],
        "factor_domains": diagnostics["factor_domains"],
        "analysis_fallback": diagnostics["analysis_fallback"],
        "safety_reason_codes": result["reason_codes"],
        "memory_hit_count": diagnostics["memory_hit_count"],
        "guard": result.get("explanation_guard"),
        "model_calls": diagnostics["model_calls"],
    }


def main() -> None:
    env_file = Path(".env")
    api_key = load_api_key(env_file)
    es_url = _env_value("ELASTICSEARCH_URL", env_file) or "http://127.0.0.1:9200"
    client = Elasticsearch(es_url, request_timeout=30)
    eval_user_id = f"stage7a-smoke-{uuid4().hex}"
    memory_id = None
    try:
        case_a = run_agentic_rag(
            BasicRagRequest(
                query=(
                    "我刚连续写了一段时间作业，现在只有5分钟，而且已经比较接近平时睡觉时间，"
                    "我今天不太想做活动，怎么安排更合适？"
                ),
                target_stage="junior_high",
                current_context="home",
                activity_context="writing",
                available_minutes=5,
            ),
            f"{eval_user_id}-a",
            client,
            api_key,
        )
        case_b = run_agentic_rag(
            BasicRagRequest(
                query="我正在晃动的车上看手机屏幕，现在应该怎么安排？",
                target_stage="junior_high",
                current_context="commute",
                activity_context="screen",
                available_minutes=5,
                unstable_environment=True,
            ),
            f"{eval_user_id}-b",
            client,
            api_key,
        )

        preferred_task = next(
            task for task in load_formal_micro_tasks() if task["task_id"] == "MT-EYE-004"
        )
        now = datetime.now(UTC).isoformat()
        profile = UserProfile(eval_user_id, "junior_high", True, now, now)
        upsert_user_profile(client, profile)
        candidate = UserMemoryCandidate(
            memory_id="",
            user_id=eval_user_id,
            memory_type="task_preference",
            source_type="explicit_user_setting",
            task_id=preferred_task["task_id"],
            domain=None,
            memory_key="prefer_task",
            memory_value={"preference": "prefer_task"},
            created_at=now,
            updated_at=now,
        )
        memory_id = build_memory_id(candidate)
        candidate = UserMemoryCandidate(**{**candidate.__dict__, "memory_id": memory_id})
        created = create_memory(
            client,
            profile,
            candidate,
            {task["task_id"] for task in load_formal_micro_tasks()},
        )
        if created["status"] != "created":
            raise RuntimeError(f"smoke memory creation failed: {created['status']}")
        if embed_memory(client, eval_user_id, memory_id, api_key)["status"] != "embedded":
            raise RuntimeError("smoke memory embedding failed")
        case_c = run_agentic_rag(
            BasicRagRequest(
                query=f"我现在有5分钟，想在家里{preferred_task['title']}，请帮我安排。",
                target_stage="junior_high",
                current_context="home",
                activity_context="reading",
                available_minutes=5,
            ),
            eval_user_id,
            client,
            api_key,
        )
        diagnostics_c = case_c["diagnostics"]
        summary_c = _summary(case_c)
        summary_c.update(
            preferred_task_id=preferred_task["task_id"],
            preferred_task_delta=diagnostics_c["personalization_delta_by_task"].get(
                preferred_task["task_id"]
            ),
            candidate_invariance=(
                set(diagnostics_c["task_candidate_ids"])
                == set(diagnostics_c["personal_task_ranking"])
            ),
            base_task_ranking=diagnostics_c["base_task_ranking"],
            personal_task_ranking=diagnostics_c["personal_task_ranking"],
        )
        print(
            json.dumps(
                {"case_a": _summary(case_a), "case_b": _summary(case_b), "case_c": summary_c},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    finally:
        if memory_id:
            forget_memory(client, eval_user_id, memory_id)
        client.options(ignore_status=404).delete(
            index="user_profiles_v1", id=eval_user_id, refresh="wait_for"
        )
        client.close()


if __name__ == "__main__":
    main()
