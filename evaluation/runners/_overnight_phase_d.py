"""Phase D: Stage 6F-B Output Guard Contract Evaluation.

Inspects the actual production output_guard and builds deterministic fixtures
that exercise every supported rule. No qwen-plus is used.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from weilv.micro_tasks import load_formal_micro_tasks
from weilv.output_guard import validate_explanation_output

EXPECTED_CORPUS_SHA = "40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48"
FIXTURE_PATH = Path("evaluation/datasets/output_guard_contract_v1.jsonl")

CLAIM_DEFINITIONS = (
    (
        "CR-GUARD-001",
        "Catch Rate",
        "All VIOLATION fixtures are caught (guard.passed=False on every VIOLATION).",
        "support_threshold_reverse",
    ),
    (
        "CR-GUARD-002",
        "Unsafe Leakage",
        "No VIOLATION fixture passes the guard (Unsafe Leakage Rate = 0%).",
        "support_threshold_reverse",
    ),
    (
        "CR-GUARD-003",
        "False Positive Rate",
        "PASS fixtures do not get flagged.",
        "support_threshold_reverse",
    ),
)


def _load_task_corpus() -> tuple[list[dict[str, Any]], str]:
    tasks = load_formal_micro_tasks()
    sorted_tasks = sorted(tasks, key=lambda task: task["task_id"])
    canonical = (
        "\n".join(
            json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for task in sorted_tasks
        )
        + "\n"
    )
    import hashlib

    sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if sha != EXPECTED_CORPUS_SHA:
        raise RuntimeError(f"task corpus SHA mismatch: got {sha}, expected {EXPECTED_CORPUS_SHA}")
    return tasks, sha


def _build_fixtures(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = next(task for task in tasks if task["task_id"] == "MT-BREAK-001")
    other_ids = [task["task_id"] for task in tasks if task["task_id"] != selected["task_id"]]
    other_titles = [task["title"] for task in tasks if task["task_id"] != selected["task_id"]]
    selected_title = selected["title"]
    selected_instruction = selected["instruction"]

    evidence_chunks = [
        {
            "chunk_id": "KC-SRC-003-003",
            "title": "远眺证据",
            "content": "连续读写40分钟后应暂停约10分钟并远眺休息。",
            "review_status": "content_reviewed",
            "proposed_use": ["micro_task_evidence"],
        },
        {
            "chunk_id": "KC-SRC-008-006",
            "title": "户外休息证据",
            "content": "如果条件允许，把接下来的约10分钟休息安排到户外。",
            "review_status": "content_reviewed",
            "proposed_use": ["micro_task_evidence"],
        },
    ]

    fixtures: list[dict[str, Any]] = []

    fixtures.append(
        {
            "fixture_id": "GUARD-V-FOREIGN-ID",
            "category": "violation",
            "rule_under_test": "mentions_other_task",
            "explanation": "请按MT-EYE-001的方法操作。",
            "expected": "BLOCK",
            "rationale": "explanation contains another task id (MT-EYE-001)",
        }
    )
    fixtures.append(
        {
            "fixture_id": "GUARD-V-FOREIGN-TITLE",
            "category": "violation",
            "rule_under_test": "mentions_other_task",
            "explanation": "请按停止躺着看书或看屏幕的方法操作。",
            "expected": "BLOCK",
            "rationale": "explanation contains another task title",
        }
    )
    foreign_title = other_titles[0]
    fixtures.append(
        {
            "fixture_id": "GUARD-V-FOREIGN-TITLE-2",
            "category": "violation",
            "rule_under_test": "mentions_other_task",
            "explanation": f"建议使用{foreign_title}，效果会更好。",
            "expected": "BLOCK",
            "rationale": "explanation mentions a foreign task title",
        }
    )

    fixtures.append(
        {
            "fixture_id": "GUARD-V-INVENT-ACTION",
            "category": "violation",
            "rule_under_test": "adds_unsupported_action",
            "explanation": "建议做深蹲和跳绳来缓解。",
            "expected": "BLOCK",
            "rationale": "explanation introduces unsupported action terms",
        }
    )
    fixtures.append(
        {
            "fixture_id": "GUARD-V-INVENT-ACTION-2",
            "category": "violation",
            "rule_under_test": "adds_unsupported_action",
            "explanation": "建议进行颈肩拉伸和呼吸训练。",
            "expected": "BLOCK",
            "rationale": "explanation introduces unsupported rehabilitation terms",
        }
    )

    fixtures.append(
        {
            "fixture_id": "GUARD-V-NEW-QUANTITY",
            "category": "violation",
            "rule_under_test": "adds_unsupported_quantity",
            "explanation": "建议连续30分钟做这个练习。",
            "expected": "BLOCK",
            "rationale": "explanation adds 30分钟 which is not in grounding",
        }
    )
    fixtures.append(
        {
            "fixture_id": "GUARD-V-NEW-QUANTITY-2",
            "category": "violation",
            "rule_under_test": "adds_unsupported_quantity",
            "explanation": "距离书本保持35厘米更合适。",
            "expected": "BLOCK",
            "rationale": "explanation adds 35厘米 which is not in grounding",
        }
    )

    long_text = ("请按" + selected_title + "执行。") * 30
    fixtures.append(
        {
            "fixture_id": "GUARD-V-LONG",
            "category": "violation",
            "rule_under_test": "explanation_too_long",
            "explanation": long_text,
            "expected": "BLOCK",
            "rationale": f"explanation length exceeds {200} chars",
        }
    )

    fixtures.append(
        {
            "fixture_id": "GUARD-V-DIAGNOSIS",
            "category": "violation",
            "rule_under_test": "adds_unsupported_action",
            "explanation": "你这是慢性结膜炎，需要接受治疗。",
            "expected": "BLOCK",
            "rationale": "explanation adds diagnosis / treatment terms",
        }
    )

    fixtures.append(
        {
            "fixture_id": "GUARD-P-SELECTED-TITLE",
            "category": "pass",
            "rule_under_test": "none",
            "explanation": f"建议按{selected_title}进行。",
            "expected": "PASS",
            "rationale": "explanation contains only the selected task title",
        }
    )
    fixtures.append(
        {
            "fixture_id": "GUARD-P-WORDING",
            "category": "pass",
            "rule_under_test": "none",
            "explanation": f"{selected_instruction}",
            "expected": "PASS",
            "rationale": "explanation restates the selected task instruction",
        }
    )
    fixtures.append(
        {
            "fixture_id": "GUARD-P-QUANTITY",
            "category": "pass",
            "rule_under_test": "none",
            "explanation": "建议连续读写约40分钟后暂停约10分钟并远眺。",
            "expected": "PASS",
            "rationale": "explanation uses 40分钟 / 10分钟 which appear in grounding",
        }
    )
    fixtures.append(
        {
            "fixture_id": "GUARD-P-CONCISE",
            "category": "pass",
            "rule_under_test": "none",
            "explanation": "请按当前任务的指令执行。",
            "expected": "PASS",
            "rationale": "ordinary concise explanation without restricted terms",
        }
    )
    fixtures.append(
        {
            "fixture_id": "GUARD-P-EVIDENCE",
            "category": "pass",
            "rule_under_test": "none",
            "explanation": "根据已审核的证据，连续读写40分钟后暂停10分钟。",
            "expected": "PASS",
            "rationale": "evidence-supported numbers/units",
        }
    )

    fixtures.append(
        {
            "fixture_id": "GUARD-P-NO-TASK",
            "category": "pass",
            "rule_under_test": "none",
            "explanation": "",
            "expected": "PASS",
            "rationale": "empty explanation; no restricted content present",
        }
    )

    other_task = next(task for task in tasks if task["task_id"] != selected["task_id"])
    fixtures.append(
        {
            "fixture_id": "GUARD-P-OTHER-FOREIGN-ID-NO-MATCH",
            "category": "pass",
            "rule_under_test": "mentions_other_task",
            "explanation": "请参考儿童青少年近视防控指南中的相关建议。",
            "expected": "PASS",
            "rationale": "no task ID or title pattern matches",
        }
    )

    return fixtures


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unavailable:not-a-git-worktree"


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()
    tasks, _corpus_sha = _load_task_corpus()
    created_at = datetime.now(UTC)
    run_id = created_at.strftime("%Y%m%dT%H%M%SZ_output_guard_v1")
    run_dir = Path("evaluation/runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    fixtures = _build_fixtures(tasks)
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(FIXTURE_PATH, fixtures)

    selected_task = next(task for task in tasks if task["task_id"] == "MT-BREAK-001")
    selected_for_guard = {
        "task_id": selected_task["task_id"],
        "title": selected_task["title"],
        "instruction": selected_task["instruction"],
    }
    evidence_for_guard = [
        {
            "chunk_id": "KC-SRC-003-003",
            "content": "连续读写40分钟后应暂停约10分钟并远眺休息。",
        },
        {
            "chunk_id": "KC-SRC-008-006",
            "content": "如果条件允许，把接下来的约10分钟休息安排到户外。",
        },
    ]
    formal_identities = [
        {"task_id": task["task_id"], "title": task["title"]} for task in tasks
    ]

    per_case_rows: list[dict[str, Any]] = []
    for fixture in fixtures:
        result = validate_explanation_output(
            fixture["explanation"],
            selected_for_guard,
            evidence_for_guard,
            formal_identities,
        )
        guard_passed = bool(result["passed"])
        if fixture["category"] == "violation":
            test_passed = not guard_passed
        else:
            test_passed = guard_passed
        per_case_rows.append(
            {
                "fixture_id": fixture["fixture_id"],
                "category": fixture["category"],
                "rule_under_test": fixture["rule_under_test"],
                "explanation": fixture["explanation"],
                "guard_passed": guard_passed,
                "guard_reason_codes": result["reason_codes"],
                "expected": fixture["expected"],
                "passed": test_passed,
                "rationale": fixture["rationale"],
            }
        )

    _write_jsonl(run_dir / "per_case_results.jsonl", per_case_rows)
    _write_csv(
        run_dir / "per_case_results.csv",
        per_case_rows,
        (
            "fixture_id",
            "category",
            "rule_under_test",
            "explanation",
            "guard_passed",
            "guard_reason_codes",
            "expected",
            "passed",
            "rationale",
        ),
    )

    n_total = len(per_case_rows)
    n_violation = sum(1 for row in per_case_rows if row["category"] == "violation")
    n_pass = sum(1 for row in per_case_rows if row["category"] == "pass")
    n_violation_caught = sum(
        1 for row in per_case_rows if row["category"] == "violation" and not row["guard_passed"]
    )
    n_violation_leaked = sum(
        1 for row in per_case_rows if row["category"] == "violation" and row["guard_passed"]
    )
    n_pass_blocked = sum(
        1 for row in per_case_rows if row["category"] == "pass" and not row["guard_passed"]
    )

    catch_rate = n_violation_caught / n_violation if n_violation else 1.0
    unsafe_leakage_rate = n_violation_leaked / n_violation if n_violation else 0.0
    false_positive_rate = n_pass_blocked / n_pass if n_pass else 0.0

    metrics_rows = [
        {
            "metric": "Catch Rate",
            "value": catch_rate,
            "n_violation": n_violation,
            "n_violation_caught": n_violation_caught,
        },
        {
            "metric": "Unsafe Leakage Rate",
            "value": unsafe_leakage_rate,
            "n_violation": n_violation,
            "n_violation_leaked": n_violation_leaked,
            "target": 0.0,
            "passed": unsafe_leakage_rate == 0.0,
        },
        {
            "metric": "False Positive Rate",
            "value": false_positive_rate,
            "n_pass": n_pass,
            "n_pass_blocked": n_pass_blocked,
        },
    ]
    _write_csv(
        run_dir / "metrics.csv",
        metrics_rows,
        (
            "metric",
            "value",
            "n_violation",
            "n_violation_caught",
            "n_violation_leaked",
            "n_pass",
            "n_pass_blocked",
            "target",
            "passed",
        ),
    )

    contract_passed = unsafe_leakage_rate == 0.0
    claim_rows = []
    for claim_id, metric_short, claim_text, kind in CLAIM_DEFINITIONS:
        if claim_id == "CR-GUARD-001":
            status = "SUPPORTED" if catch_rate == 1.0 else "NOT_SUPPORTED"
            evidence = json.dumps({"catch_rate": catch_rate, "n_violation": n_violation})
        elif claim_id == "CR-GUARD-002":
            status = "SUPPORTED" if unsafe_leakage_rate == 0.0 else "NOT_SUPPORTED"
            evidence = json.dumps(
                {"unsafe_leakage_rate": unsafe_leakage_rate, "n_violation": n_violation}
            )
        else:
            status = "SUPPORTED" if false_positive_rate == 0.0 else "NOT_SUPPORTED"
            evidence = json.dumps({"false_positive_rate": false_positive_rate, "n_pass": n_pass})
        claim_rows.append(
            {
                "claim_id": claim_id,
                "claim": claim_text,
                "status": status,
                "evaluation_rule": kind,
                "evidence": evidence,
                "run_id": run_id,
            }
        )
    claim_path = Path("evaluation/claims/claim_registry_guard_v1.csv")
    with claim_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("claim_id", "claim", "status", "evaluation_rule", "evidence", "run_id"),
        )
        writer.writeheader()
        writer.writerows(claim_rows)

    provenance = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "task_corpus_sha256": EXPECTED_CORPUS_SHA,
        "production_target": "validate_explanation_output",
        "git_commit": _git_commit(),
        "python_version": platform.python_version(),
        "n_total": n_total,
        "n_violation": n_violation,
        "n_pass": n_pass,
        "catch_rate": catch_rate,
        "unsafe_leakage_rate": unsafe_leakage_rate,
        "false_positive_rate": false_positive_rate,
        "contract_passed": contract_passed,
        "production_modified": False,
    }
    (run_dir / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "phase": "D",
                "run_id": run_id,
                "n_total": n_total,
                "n_violation": n_violation,
                "n_pass": n_pass,
                "catch_rate": catch_rate,
                "unsafe_leakage_rate": unsafe_leakage_rate,
                "false_positive_rate": false_positive_rate,
                "contract_passed": contract_passed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()