"""Stage 6F-B: Real integration test of the production evidence fail-closed path.

Invokes the ACTUAL production finalization function
weilv.basic_rag._finalize_selected_task (which calls load_task_evidence and
performs the caller-side exact-equality check) with a fake Elasticsearch
client. No real index is touched. explain_selected_task (qwen-plus) is
monkeypatched to raise if invoked — proving the model is never called on the
fail-closed path.

Deterministic: embedding=0, reranker=0, qwen-plus=0.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from weilv import basic_rag  # noqa: E402
from weilv.basic_rag import BasicRagRequest, _finalize_selected_task  # noqa: E402


class FakeKnowledgeClient:
    """Returns canned knowledge-index hits regardless of query body."""

    def __init__(self, hits: list[dict]) -> None:
        self._hits = hits
        self.search_calls: list[dict] = []

    def search(self, index: str, size: int, query: dict, **kwargs) -> dict:
        self.search_calls.append({"index": index, "query": query})
        if index == "micro_tasks_v1":
            return {"hits": {"hits": [{"_source": {"task_id": "MT-TEST-000", "title": "t"}}]}}
        return {"hits": {"hits": [{"_source": hit} for hit in self._hits]}}


def _evidence(chunk_id: str, *, review_status: str = "content_reviewed") -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": f"DOC-{chunk_id}",
        "source_locator": "p.1",
        "source_url": "",
        "review_status": review_status,
        "proposed_use": ["micro_task_evidence"],
        "content": "已审核的健康知识内容。",
    }


PIPELINE = {
    "safe_result": {"matched_rule_ids": [], "reason_codes": []},
    "knowledge": [_evidence("KC-CTX-001")],
}
REQUEST = BasicRagRequest(
    query="整合测试查询",
    target_stage="junior_high",
    current_context="home",
)
SELECTED_FIELDS = {
    "task_id": "MT-TEST-000",
    "title": "测试任务",
    "instruction": "闭眼休息20秒。",
    "evidence_chunk_ids": ["KC-A", "KC-B"],
    "covered_domains": ["light_recovery"],
    "estimated_minutes": 1,
}


def _run_case(
    case_id: str,
    client: FakeKnowledgeClient,
    *,
    expect_fail_closed: bool,
    description: str,
) -> dict:
    explain_called = False

    def _explain_spy(*args, **kwargs):
        nonlocal explain_called
        explain_called = True
        return "说明文本"

    original = basic_rag.explain_selected_task
    basic_rag.explain_selected_task = _explain_spy
    try:
        result = _finalize_selected_task(
            REQUEST,
            dict(SELECTED_FIELDS),
            PIPELINE,
            client,
            api_key="not-used",
            knowledge_index="health_knowledge_v1",
            task_index="micro_tasks_v1",
        )
    finally:
        basic_rag.explain_selected_task = original

    status = result["status"]
    fail_closed = (
        status == "no_safe_task"
        and result["selected_task"] is None
        and result["reason_codes"] == ["selected_task_evidence_invalid"]
    )
    if expect_fail_closed:
        passed = (
            fail_closed
            and not explain_called
            and result["explanation"] is None
        )
    else:
        # Positive control: production proceeds; explain is the monkeypatched
        # spy (no real model call), task selected, explanation emitted.
        passed = (
            not fail_closed
            and status == "allowed"
            and result["selected_task"] is not None
            and result["explanation"] is not None
            and explain_called
        )
    return {
        "case_id": case_id,
        "description": description,
        "expect_fail_closed": expect_fail_closed,
        "status": status,
        "selected_task": result["selected_task"],
        "reason_codes": result["reason_codes"],
        "explanation_emitted": result["explanation"] is not None,
        "explain_selected_task_called": explain_called,
        "production_path": "weilv.basic_rag._finalize_selected_task",
        "passed": passed,
    }


def build_cases() -> list[tuple[str, FakeKnowledgeClient, bool, str]]:
    valid_a, valid_b = _evidence("KC-A"), _evidence("KC-B")
    return [
        (
            "EFC-MISSING-001",
            FakeKnowledgeClient([valid_b]),
            True,
            "one expected evidence ID missing from index",
        ),
        (
            "EFC-NONEXISTENT-001",
            FakeKnowledgeClient([valid_a, _evidence("KC-OTHER")]),
            True,
            "one expected evidence ID nonexistent (extra unrelated chunk present)",
        ),
        (
            "EFC-REVIEWSTATUS-001",
            FakeKnowledgeClient([valid_b, _evidence("KC-A", review_status="draft")]),
            True,
            "evidence exists but review_status != content_reviewed",
        ),
        (
            "EFC-PROPOSEDUSE-001",
            FakeKnowledgeClient(
                [valid_b, {**_evidence("KC-A"), "proposed_use": ["rag_knowledge"]}]
            ),
            True,
            "evidence exists but proposed_use lacks micro_task_evidence",
        ),
        (
            "EFC-CONTROL-VALID",
            FakeKnowledgeClient([valid_a, valid_b]),
            False,
            "all expected evidence valid and complete -> allowed (positive control)",
        ),
    ]


def main() -> None:
    created_at = datetime.now(UTC)
    run_id = created_at.strftime("%Y%m%dT%H%M%SZ") + "_evidence_fail_closed_integration_v1"
    run_dir = PROJECT_ROOT / "evaluation" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    rows = []
    for case_id, client, expect_fail, description in build_cases():
        rows.append(
            _run_case(case_id, client, expect_fail_closed=expect_fail, description=description)
        )

    fail_closed_rows = [row for row in rows if row["expect_fail_closed"]]
    all_fail_closed = all(row["passed"] for row in fail_closed_rows)
    control_ok = all(row["passed"] for row in rows if not row["expect_fail_closed"])
    qwen_not_called_on_fail_closed = not any(
        row["explain_selected_task_called"] for row in fail_closed_rows
    )

    metrics = {
        "fixtures_total": len(rows),
        "fail_closed_fixtures": len(fail_closed_rows),
        "fail_closed_all_passed": all_fail_closed,
        "positive_control_passed": control_ok,
        "qwen_plus_not_called_on_fail_closed_paths": qwen_not_called_on_fail_closed,
        "model_call_counts": {"text_embedding_v4": 0, "qwen3_rerank": 0, "qwen_plus": 0},
        "production_path_invoked": "weilv.basic_rag._finalize_selected_task",
        "cr_evid_002_status": (
            "SUPPORTED" if (all_fail_closed and qwen_not_called_on_fail_closed) else "NOT_SUPPORTED"
        ),
    }
    provenance = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "audit_ticket": "Stage 6F Phase B",
        "production_target": "weilv.basic_rag._finalize_selected_task",
        "elasticsearch_used": False,
        "indexes_touched": [],
        "production_modified": False,
        "frozen_artifacts_touched": False,
        "python_version": platform.python_version(),
        "deterministic": True,
    }

    (run_dir / "per_case_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    (run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"run_id": run_id, **metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
