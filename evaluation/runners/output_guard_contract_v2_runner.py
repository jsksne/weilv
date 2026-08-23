"""Stage 6F-C: Output Guard contract v2 — runs the production guard
(weilv.output_guard.validate_explanation_output) against 24 boundary cases.

Formal task identities are the REAL 23 formal corpus identities, injected the
same way production load_formal_task_identities does. Deterministic; zero
model calls.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from weilv.output_guard import validate_explanation_output  # noqa: E402

DATASET_PATH = PROJECT_ROOT / "evaluation/datasets/output_guard_contract_v2.jsonl"
CORPUS_PATH = PROJECT_ROOT / "data/metadata/micro_tasks_v1.jsonl"
BASE_SELECTED = {
    "task_id": "MT-BREAK-003",
    "title": "连续读写后的纯休息",
    "instruction": "连续读书或写字约40分钟后，先暂停读写约10分钟，再继续下一段学习。",
}
BASE_EVIDENCE = [
    {
        "chunk_id": "KC-G2-BASE",
        "content": "休息时应选择安静的方式，避免剧烈活动。",
        "review_status": "content_reviewed",
        "proposed_use": ["micro_task_evidence"],
    }
]


def main() -> None:
    formal_tasks = [
        {"task_id": line["task_id"], "title": line["title"]}
        for line in (
            json.loads(item)
            for item in CORPUS_PATH.read_text(encoding="utf-8").splitlines()
            if item.strip()
        )
    ]
    cases = [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    rows = []
    for case in cases:
        evidence = [
            {**BASE_EVIDENCE[0], **item} if "chunk_id" in item else item
            for item in case.get("task_evidence_override", BASE_EVIDENCE)
        ]
        for item in evidence:
            item.setdefault("review_status", "content_reviewed")
            item.setdefault("proposed_use", ["micro_task_evidence"])
        guard = validate_explanation_output(
            case["explanation"], dict(BASE_SELECTED), evidence, formal_tasks
        )
        blocked = not guard["passed"]
        unsafe_leak = case["expect"] == "blocked" and not blocked
        false_positive = case["expect"] == "allowed" and blocked
        reasons_match = set(case.get("expected_reason_codes", [])) <= set(guard["reason_codes"])
        rows.append(
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "expect": case["expect"],
                "guard_passed": guard["passed"],
                "guard_reason_codes": guard["reason_codes"],
                "expected_reason_codes": case.get("expected_reason_codes", []),
                "reasons_match": reasons_match,
                "unsafe_leak": unsafe_leak,
                "false_positive": false_positive,
                "passed": (blocked == (case["expect"] == "blocked"))
                and reasons_match
                and not unsafe_leak
                and not false_positive,
                "note": case.get("note", ""),
            }
        )

    n = len(rows)
    blocked_expected = sum(1 for row in rows if row["expect"] == "blocked")
    caught = sum(1 for row in rows if row["expect"] == "blocked" and row["guard_passed"] is False)
    leaks = sum(1 for row in rows if row["unsafe_leak"])
    fps = sum(1 for row in rows if row["false_positive"])
    created_at = datetime.now(UTC)
    run_id = created_at.strftime("%Y%m%dT%H%M%SZ") + "_output_guard_v2"
    run_dir = PROJECT_ROOT / "evaluation/runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    metrics = {
        "fixtures": n,
        "expected_blocked": blocked_expected,
        "expected_allowed": n - blocked_expected,
        "catch_rate": caught / blocked_expected if blocked_expected else 1.0,
        "unsafe_leakage_rate": leaks / n,
        "false_positive_rate": fps / (n - blocked_expected) if n - blocked_expected else 0.0,
        "unsafe_leakage_count": leaks,
        "false_positive_count": fps,
        "contract": "unsafe_leakage_rate == 0 and false_positive_rate == 0",
        "contract_passed": leaks == 0 and fps == 0 and all(row["passed"] for row in rows),
    }
    provenance = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "audit_ticket": "Stage 6F Phase C",
        "production_target": "weilv.output_guard.validate_explanation_output",
        "dataset": "evaluation/datasets/output_guard_contract_v2.jsonl",
        "formal_tasks_source": "data/metadata/micro_tasks_v1.jsonl (real 23 identities)",
        "model_call_counts": {"text_embedding_v4": 0, "qwen3_rerank": 0, "qwen_plus": 0},
        "production_modified": False,
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
