"""Run EXACTLY ONE Stage 7A.1 live smoke — the previous complex Case A.

No formal claims. Required observation: Output Guard passed == true.
The raw LLM explanation is captured (via a runner-side wrapper, no production
change) so a Guard rejection can be reported with the exact explanation.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from elasticsearch import Elasticsearch

from weilv import agentic_rag
from weilv.basic_rag import BasicRagRequest
from weilv.retrieval_slice import _env_value, load_api_key

CASE_A_QUERY = (
    "我刚连续写了一段时间作业，"
    "现在只有5分钟，而且已经比较接近平时睡觉时间，"
    "我今天不太想做活动，怎么安排更合适？"
)


def main() -> None:
    env_file = Path(".env")
    api_key = load_api_key(env_file)
    es_url = _env_value("ELASTICSEARCH_URL", env_file) or "http://127.0.0.1:9200"
    client = Elasticsearch(es_url, request_timeout=30)
    raw_explanations: list[str] = []
    original = agentic_rag.compose_agentic_explanation
    agentic_rag.compose_agentic_explanation = lambda *args, **kwargs: (
        raw_explanations.append(original(*args, **kwargs)) or raw_explanations[-1]
    )
    try:
        result = agentic_rag.run_agentic_rag(
            BasicRagRequest(
                query=CASE_A_QUERY,
                target_stage="junior_high",
                current_context="home",
                activity_context="writing",
                available_minutes=5,
            ),
            "stage7a1-smoke-case-a",
            client,
            api_key,
        )
        diagnostics = result["diagnostics"]
        summary = {
            "classification": "non_formal_engineering_smoke",
            "case": "A",
            "status": result["status"],
            "selected_task_id": diagnostics["selected_task_id"],
            "factor_count": diagnostics["factor_count"],
            "factor_domains": diagnostics["factor_domains"],
            "analysis_fallback": diagnostics["analysis_fallback"],
            "safety_reason_codes": result["reason_codes"],
            "guard": result.get("explanation_guard"),
            "raw_explanation": raw_explanations[-1] if raw_explanations else None,
            "served_explanation": result.get("explanation"),
            "model_calls": diagnostics["model_calls"],
        }
        print(
            json.dumps(
                {"result": summary, "run_at": datetime.now(UTC).isoformat()},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        out_dir = Path("evaluation/stage7a1_acceptance")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "live_smoke_result.json").write_text(
            json.dumps(
                {"result": summary, "run_at": datetime.now(UTC).isoformat()},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
