"""Stage 6G Phase C/D/F — Formal Safety Evaluation.

Mechanics:
- Load frozen Safety Gold v1 (consensus-reviewed, SHA-pinned).
- Load formal micro_tasks_v1.jsonl task corpus.
- For each case, derive ONLY a runtime context that mirrors the BasicRagRequest
  payload (request boolean fields, target_stage, current_context, activity_context,
  available_minutes, derived unstable_reading_or_screen, sleep_displaced_by_study).
  Gold-only fields (case_id, rule_ids, expected_decision, expected_allowed/blocked
  task_ids, gold_basis, review metadata) are NEVER sent into production functions.
- Invoke ACTUAL production weilv.safety_rules functions (evaluate_input_risk,
  filter_task_by_safety, select_safe_tasks) over the real task corpus.
- For SR-012 / no_safe_whitelist_task, use select_safe_tasks against the full
  candidate set (filtered to the case's target_stage, current_context and
  available_minutes) — never an in-evaluator simulation.
- Score: per-case correctness, unsafe_escape, false_block.
- Write per_case_results.jsonl, metrics.json, metrics.csv, rule_metrics.csv,
  provenance.json under evaluation/runs/<run_id>_safety_v1/.

No model calls are made (input-level rules + deterministic task filter).
"""

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# import production safety implementation from src/
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from weilv.safety_rules import (
    evaluate_input_risk,
    filter_task_by_safety,
    load_safety_rules,
    select_safe_tasks,
)

DATASETS = ROOT / "evaluation" / "datasets"
RUNS = ROOT / "evaluation" / "runs"

GOLD = DATASETS / "safety_gold_v1.jsonl"
TASK_CORPUS_PATH = ROOT / "data" / "metadata" / "micro_tasks_v1.jsonl"
PRODUCTION_RULES_PATH = ROOT / "data" / "metadata" / "safety_rules_v0.1.json"
PRODUCTION_SAFETY_PY = SRC / "weilv" / "safety_rules.py"

# Pin sha from Phase B (computed at freeze time).
EXPECTED_GOLD_SHA = "aa975d5cd58deec5c837b1ca2b5e4723229fd71c08c64df85ba39d8819372e7f"
EXPECTED_TASK_CORPUS_SHA = "40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48"

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_safety_v1"
RUN_DIR = RUNS / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)

# Gold-only fields must never enter production function calls.
GOLD_ONLY_KEYS = {
    "case_id", "rule_ids", "expected_decision", "expected_allowed_task_ids",
    "expected_blocked_task_ids", "gold_basis", "input_provenance",
    "gold_provenance", "review_status", "reviewer_count",
    "human_consensus_reviewed", "consensus_review_round", "draft_provenance",
    "case_type", "query", "expected_no_task", "expected_help_or_escalation",
}


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_task_corpus_sha(rows: list[dict]) -> str:
    """SHA-256 over the canonical sorted-JSONL form documented in
    evaluation/manifests/task_gold_task_corpus_v1.json."""
    sorted_rows = sorted(rows, key=lambda r: r["task_id"])
    buf = "\n".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for r in sorted_rows
    ) + "\n"
    return hashlib.sha256(buf.encode("utf-8")).hexdigest()


def derive_runtime_context(case: dict) -> dict:
    """Build the runtime safety context (BasicRagRequest-derived) for a case.

    Mirrors weilv.basic_rag._safety_context but uses case fields without ever
    reading Gold-only fields.
    """
    flags = case.get("safety_flags", {}) or {}
    current_context = case.get("current_context")
    if current_context == "unknown":
        current_context = None
    activity_context = case.get("activity_context", "unknown")
    unstable_env = bool(flags.get("unstable_environment", False))
    unstable_reading_or_screen = (
        unstable_env and activity_context in {"reading", "writing", "screen"}
    )
    return {
        # request booleans only
        "vision_abnormal": bool(flags.get("vision_abnormal", False)),
        "physical_discomfort": bool(flags.get("physical_discomfort", False)),
        "medical_request": bool(flags.get("medical_request", False)),
        "cannot_move": bool(flags.get("cannot_move", False)),
        "unstable_environment": unstable_env,
        "sleep_being_crowded": bool(flags.get("sleep_being_crowded", False)),
        # request metadata
        "target_stage": case.get("target_stage"),
        "current_context": current_context,
        "activity_context": activity_context,
        "available_minutes": case.get("available_minutes"),
        # derived (mirrors basic_rag.py:41-45)
        "unstable_reading_or_screen": unstable_reading_or_screen,
        "sleep_displaced_by_study": bool(flags.get("sleep_being_crowded", False)),
    }


def leak_check(case: dict, runtime_context: dict) -> list[str]:
    """Assert that no Gold-only field is in the runtime context."""
    leaked = []
    for key in GOLD_ONLY_KEYS:
        if key in runtime_context:
            leaked.append(key)
    return leaked


def load_task_corpus() -> list[dict]:
    tasks = []
    with TASK_CORPUS_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            tasks.append(json.loads(line))
    return tasks


def candidate_pool(tasks: list[dict], ctx: dict) -> list[dict]:
    """Per-rule candidate universe for Safety Rule assertions.

    For per-task assertions (expected_blocked_task_ids, expected_allowed_task_ids)
    we MUST evaluate the rule against every formal task so the Safety Rule itself
    is the gate, not the corpus-level ES filter. The ticket says "do not confuse
    retrieval failure with Safety Rule failure", so we deliberately keep the
    context/time filters OUT of this candidate set. All 23 tasks list all 3
    stages, so target_stage alone leaves 23 tasks.

    For the aggregate SR-012 assertion (select_safe_tasks) we DO apply the
    context/time pre-filter separately because that is what basic_rag feeds.
    """
    out = []
    for task in tasks:
        if task.get("review_status") != "content_reviewed":
            continue
        if ctx["target_stage"] not in task.get("target_stage", []):
            continue
        out.append(task)
    return out


def aggregate_candidate_pool(tasks: list[dict], ctx: dict) -> list[dict]:
    """Candidate set fed to select_safe_tasks for SR-012 aggregate test.

    Mirrors weilv.basic_rag._matches_task_metadata: target_stage +
    execution_context + available_minutes. The Safety Rule then either passes
    or fails each task. SR-012 fires only if no task survives.
    """
    out = []
    for task in tasks:
        if task.get("review_status") != "content_reviewed":
            continue
        if ctx["target_stage"] not in task.get("target_stage", []):
            continue
        if ctx["current_context"] is not None:
            if ctx["current_context"] not in task.get("execution_contexts", []):
                continue
        if ctx["available_minutes"] is not None:
            if task.get("estimated_minutes", ctx["available_minutes"] + 1) > ctx["available_minutes"]:
                continue
        out.append(task)
    return out


def case_status_from_input(input_result: dict) -> str:
    """Map the production input-risk decision to the case-level status used for scoring."""
    return input_result["status"]


def score_case(case: dict, runtime_ctx: dict, rules: list[dict],
              per_rule_universe: list[dict],
              aggregate_universe: list[dict]) -> dict:
    """Run actual production safety rules on the case and compare to Gold.

    - per_rule_universe: ALL formal tasks at the same target_stage (no
      context/time pre-filter). Used to evaluate per-task Safety Rules so the
      rule itself is the gate.
    - aggregate_universe: target_stage + execution_context + available_minutes
      pre-filtered. Used to evaluate select_safe_tasks (SR-012 aggregate).

    Scoring semantics per ticket Phase C1:
      - Input-level rules (SR-001, SR-003): ONLY the input-risk status counts.
        filter_task_by_safety is never reached when the input fires; the Gold
        "expected_blocked_task_ids" for these cases is conceptual only and
        therefore skipped as an assertion.
      - Task-filter rules (SR-002, SR-005, SR-006, SR-009, SR-010, SR-011):
        per-task blocked/allowed assertions over the per-rule universe.
      - SR-012: aggregate select_safe_tasks status — no_safe_task when Gold
        expects no safe whitelist task, allowed otherwise.
    """
    # 1. Input-level rule (SR-001/003) — production evaluate_input_risk
    input_result = evaluate_input_risk(runtime_ctx, rules)
    # 2. Aggregate over aggregate_universe using production select_safe_tasks
    safe_result = select_safe_tasks(aggregate_universe, runtime_ctx, rules)

    # Per-task blocking trace over the per-rule universe (so the rule is the gate).
    per_rule_trace = {}
    for task in per_rule_universe:
        tr = filter_task_by_safety(task, runtime_ctx, rules)
        per_rule_trace[task["task_id"]] = {
            "blocked": tr["status"] == "blocked",
            "matched_rule_ids": tr["matched_rule_ids"],
            "reason_codes": tr["reason_codes"],
        }

    # Per-task blocking trace over the aggregate universe (for the headline
    # production_blocked_ids / production_allowed_ids — what basic_rag would
    # actually deliver). This matches what SR-012 sees.
    aggregate_trace = {}
    for task in aggregate_universe:
        tr = filter_task_by_safety(task, runtime_ctx, rules)
        aggregate_trace[task["task_id"]] = {
            "blocked": tr["status"] == "blocked",
            "matched_rule_ids": tr["matched_rule_ids"],
            "reason_codes": tr["reason_codes"],
        }

    production_blocked_ids = sorted([tid for tid, v in aggregate_trace.items() if v["blocked"]])
    production_allowed_ids = sorted([tid for tid, v in aggregate_trace.items() if not v["blocked"]])

    aggregate_status = safe_result["status"]
    # A "no task delivered" outcome happens at three production statuses:
    # help_seeking (SR-001), blocked (SR-003), or no_safe_task (SR-012).
    aggregate_no_safe_task = aggregate_status == "no_safe_task"

    expected_decision = case["expected_decision"]
    expected_allowed = list(case.get("expected_allowed_task_ids", []) or [])
    expected_blocked = list(case.get("expected_blocked_task_ids", []) or [])
    expected_no_task = bool(case.get("expected_no_task", False))
    expected_help = bool(case.get("expected_help_or_escalation", False))

    assertions: list[dict] = []

    # Detect input-level-trigger cases: Gold expects help_seeking or blocked
    # (i.e. the input-risk status is the headline semantic).
    gold_input_status = None
    if expected_decision == "help_seeking":
        gold_input_status = "help_seeking"
    elif expected_decision == "blocked":
        gold_input_status = "blocked"

    input_level_fired = gold_input_status is not None

    # ---- Input-level assertions (always evaluated when Gold pins a status) ----
    if input_level_fired:
        passed = (input_result["status"] == gold_input_status)
        assertions.append({
            "kind": "input_level",
            "rule_ids": case.get("rule_ids", []),
            "expected_status": gold_input_status,
            "actual_status": input_result["status"],
            "actual_matched_rule_ids": input_result["matched_rule_ids"],
            "actual_reason_codes": input_result["reason_codes"],
            "passed": passed,
            "trigger_assertion": True,
        })

    # ---- Aggregate no-task-delivered assertion ----
    # Applies whenever Gold says expected_no_task=True OR Gold explicitly lists
    # SR-012 in rule_ids. The semantic is "system returned no task to user"
    # which the production system delivers via help_seeking / blocked / no_safe_task.
    aggregate_asserted = expected_no_task or any(r == "SR-012" for r in case.get("rule_ids", []))
    if aggregate_asserted:
        # Did the production system deliver ANY task?
        no_task_delivered = aggregate_status in {"help_seeking", "blocked", "no_safe_task"}
        passed = no_task_delivered == expected_no_task
        assertions.append({
            "kind": "aggregate_no_task",
            "expected_no_task": expected_no_task,
            "actual_status": aggregate_status,
            "actual_no_task_delivered": no_task_delivered,
            "actual_matched_rule_ids": safe_result["matched_rule_ids"],
            "actual_reason_codes": safe_result["reason_codes"],
            "passed": passed,
            "trigger_assertion": expected_no_task,
            "control_assertion": not expected_no_task,
        })

    # ---- Per-task assertions (skipped when the input-level rule fires) ----
    # Per ticket Phase C1: input-level rules mean filter_task_by_safety is never
    # reached. Gold's expected_blocked_task_ids for those cases is conceptual,
    # not an actionable Safety Rule assertion. Skipping avoids confusing
    # "retrieval failure" with "Safety Rule failure" for cases that bypass the
    # task-filter layer entirely.
    if not input_level_fired:
        # Per-blocked-task assertions
        for tid in expected_blocked:
            trace = per_rule_trace.get(tid)
            if trace is None:
                assertions.append({
                    "kind": "blocked_task",
                    "task_id": tid,
                    "expected_blocked": True,
                    "actual_blocked": False,
                    "actual_matched_rule_ids": [],
                    "actual_reason_codes": [],
                    "passed": False,
                    "trigger_assertion": True,
                    "error": "task_id_not_in_per_rule_universe",
                })
                continue
            assertions.append({
                "kind": "blocked_task",
                "task_id": tid,
                "expected_blocked": True,
                "actual_blocked": trace["blocked"],
                "actual_matched_rule_ids": trace["matched_rule_ids"],
                "actual_reason_codes": trace["reason_codes"],
                "passed": bool(trace["blocked"]),
                "trigger_assertion": True,
            })

        # Per-allowed-task assertions (control)
        for tid in expected_allowed:
            trace = per_rule_trace.get(tid)
            if trace is None:
                assertions.append({
                    "kind": "allowed_task",
                    "task_id": tid,
                    "expected_allowed": True,
                    "actual_blocked": True,  # unknown — conservative
                    "actual_matched_rule_ids": [],
                    "actual_reason_codes": [],
                    "passed": False,
                    "trigger_assertion": False,
                    "control_assertion": True,
                    "error": "task_id_not_in_per_rule_universe",
                })
                continue
            assertions.append({
                "kind": "allowed_task",
                "task_id": tid,
                "expected_allowed": True,
                "actual_blocked": trace["blocked"],
                "actual_matched_rule_ids": trace["matched_rule_ids"],
                "actual_reason_codes": trace["reason_codes"],
                "passed": not trace["blocked"],
                "trigger_assertion": False,
                "control_assertion": True,
            })

    # ---- Case-level correctness ----
    case_passed = all(a["passed"] for a in assertions)

    # ---- Unsafe escape / false block counts ----
    unsafe_escape = sum(
        1 for a in assertions
        if a.get("trigger_assertion") and not a["passed"]
    )
    false_block = sum(
        1 for a in assertions
        if a.get("control_assertion") and not a["passed"]
    )

    # Per-rule attribution: each Gold rule_id gets the case's total assertion
    # counts attributed to it. This is a per-case roll-up.
    rule_observations: dict[str, dict] = {}
    for rid in (case.get("rule_ids") or []):
        rule_observations[rid] = {"rule_id": rid, "assertions": 0, "passed": 0, "failed": 0,
                                   "trigger_assertions": 0, "control_assertions": 0,
                                   "unsafe_escape": 0, "false_block": 0}

    for a in assertions:
        for rid in (case.get("rule_ids") or []):
            obs = rule_observations[rid]
            obs["assertions"] += 1
            if a["passed"]:
                obs["passed"] += 1
            else:
                obs["failed"] += 1
            if a.get("trigger_assertion"):
                obs["trigger_assertions"] += 1
                if not a["passed"]:
                    obs["unsafe_escape"] += 1
            if a.get("control_assertion"):
                obs["control_assertions"] += 1
                if not a["passed"]:
                    obs["false_block"] += 1

    return {
        "case_id": case["case_id"],
        "rule_ids": case.get("rule_ids", []),
        "case_type": case.get("case_type"),
        "expected_decision": expected_decision,
        "expected_no_task": expected_no_task,
        "expected_help_or_escalation": expected_help,
        "expected_allowed_task_ids": expected_allowed,
        "expected_blocked_task_ids": expected_blocked,
        "actual_input_status": input_result["status"],
        "actual_input_matched_rule_ids": input_result["matched_rule_ids"],
        "actual_input_reason_codes": input_result["reason_codes"],
        "actual_aggregate_status": aggregate_status,
        "actual_aggregate_matched_rule_ids": safe_result["matched_rule_ids"],
        "actual_aggregate_reason_codes": safe_result["reason_codes"],
        "actual_blocked_task_ids": production_blocked_ids,
        "actual_allowed_task_ids": production_allowed_ids,
        "per_rule_universe_size": len(per_rule_universe),
        "aggregate_universe_size": len(aggregate_universe),
        "assertions": assertions,
        "case_passed": case_passed,
        "unsafe_escape": unsafe_escape,
        "false_block": false_block,
        "input_level_fired": input_level_fired,
        "rule_observations": rule_observations,
    }


def main() -> None:
    # 1. SHA pinning
    actual_gold_sha = hash_file(GOLD)
    if actual_gold_sha != EXPECTED_GOLD_SHA:
        raise SystemExit(f"GOLD SHA mismatch: got {actual_gold_sha} expected {EXPECTED_GOLD_SHA}")
    # Load corpus, compute canonical SHA per documented contract.
    raw_corpus_rows = []
    with TASK_CORPUS_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw_corpus_rows.append(json.loads(line))
    actual_task_sha = canonical_task_corpus_sha(raw_corpus_rows)
    if actual_task_sha != EXPECTED_TASK_CORPUS_SHA:
        raise SystemExit(f"TASK CORPUS SHA mismatch: got {actual_task_sha} expected {EXPECTED_TASK_CORPUS_SHA}")

    # 2. Load production rules + corpus
    rules = load_safety_rules(PRODUCTION_RULES_PATH)
    # Use the rows already loaded during SHA pin; load_task_corpus() would re-read.
    tasks = raw_corpus_rows
    production_safety_py_hash = hash_file(PRODUCTION_SAFETY_PY)

    # 3. Load gold cases (SHA-locked)
    cases = []
    with GOLD.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))

    # 4. Per-case evaluation
    per_case = []
    leaked_total: list[str] = []
    for case in cases:
        runtime_ctx = derive_runtime_context(case)
        leak = leak_check(case, runtime_ctx)
        if leak:
            leaked_total.append(f"{case['case_id']}:{','.join(leak)}")
        per_rule_universe = candidate_pool(tasks, runtime_ctx)
        aggregate_universe = aggregate_candidate_pool(tasks, runtime_ctx)
        rec = score_case(case, runtime_ctx, rules, per_rule_universe, aggregate_universe)
        per_case.append(rec)

    gold_fields_leaked = bool(leaked_total)

    # 5. Aggregate metrics
    total = len(per_case)
    case_passed_count = sum(1 for r in per_case if r["case_passed"])
    safety_decision_accuracy = case_passed_count / total

    trigger_assertion_count = sum(
        sum(1 for a in r["assertions"] if a.get("trigger_assertion"))
        for r in per_case
    )
    control_assertion_count = sum(
        sum(1 for a in r["assertions"] if a.get("control_assertion"))
        for r in per_case
    )
    unsafe_escape_count = sum(r["unsafe_escape"] for r in per_case)
    false_block_count = sum(r["false_block"] for r in per_case)

    unsafe_escape_rate = (
        unsafe_escape_count / trigger_assertion_count
        if trigger_assertion_count else 0.0
    )
    false_block_rate = (
        false_block_count / control_assertion_count
        if control_assertion_count else 0.0
    )

    # 6. Per-rule metrics
    rule_metrics: dict[str, dict] = {}
    for rid in ("SR-001", "SR-002", "SR-003", "SR-005", "SR-006",
                "SR-009", "SR-010", "SR-011", "SR-012"):
        rule_metrics[rid] = {
            "rule_id": rid,
            "case_count": 0,
            "assertion_count": 0,
            "correct": 0,
            "incorrect": 0,
            "unsafe_escape": 0,
            "false_block": 0,
            "accuracy": 0.0,
        }
    for rec in per_case:
        for rid, obs in rec["rule_observations"].items():
            bucket = rule_metrics.setdefault(rid, {
                "rule_id": rid, "case_count": 0, "assertion_count": 0,
                "correct": 0, "incorrect": 0, "unsafe_escape": 0,
                "false_block": 0, "accuracy": 0.0,
            })
            bucket["case_count"] += 1
            bucket["assertion_count"] += obs["assertions"]
            bucket["correct"] += obs["passed"]
            bucket["incorrect"] += obs["failed"]
            bucket["unsafe_escape"] += obs["unsafe_escape"]
            bucket["false_block"] += obs["false_block"]
    for rid, b in rule_metrics.items():
        b["accuracy"] = (b["correct"] / b["assertion_count"]) if b["assertion_count"] else 0.0

    # 7. Write artifacts
    per_case_path = RUN_DIR / "per_case_results.jsonl"
    with per_case_path.open("w", encoding="utf-8") as fh:
        for rec in per_case:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    metrics = {
        "run_id": RUN_ID,
        "case_count": total,
        "case_passed_count": case_passed_count,
        "case_failed_count": total - case_passed_count,
        "safety_decision_accuracy": safety_decision_accuracy,
        "trigger_assertion_count": trigger_assertion_count,
        "control_assertion_count": control_assertion_count,
        "unsafe_escape_count": unsafe_escape_count,
        "false_block_count": false_block_count,
        "unsafe_escape_rate": unsafe_escape_rate,
        "false_block_rate": false_block_rate,
        "rule_metrics": rule_metrics,
        "evaluator_failures": 0,
        "gold_fields_leaked_to_production": gold_fields_leaked,
    }
    metrics_path = RUN_DIR / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # metrics.csv — flat row of headline metrics
    metrics_csv_path = RUN_DIR / "metrics.csv"
    with metrics_csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["metric", "value"])
        writer.writerow(["run_id", RUN_ID])
        writer.writerow(["case_count", total])
        writer.writerow(["case_passed_count", case_passed_count])
        writer.writerow(["case_failed_count", total - case_passed_count])
        writer.writerow(["safety_decision_accuracy", f"{safety_decision_accuracy:.6f}"])
        writer.writerow(["trigger_assertion_count", trigger_assertion_count])
        writer.writerow(["control_assertion_count", control_assertion_count])
        writer.writerow(["unsafe_escape_count", unsafe_escape_count])
        writer.writerow(["false_block_count", false_block_count])
        writer.writerow(["unsafe_escape_rate", f"{unsafe_escape_rate:.6f}"])
        writer.writerow(["false_block_rate", f"{false_block_rate:.6f}"])
        writer.writerow(["evaluator_failures", 0])
        writer.writerow(["gold_fields_leaked_to_production", str(gold_fields_leaked)])

    # rule_metrics.csv
    rule_csv_path = RUN_DIR / "rule_metrics.csv"
    with rule_csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["rule_id", "case_count", "assertion_count", "correct",
                         "incorrect", "unsafe_escape", "false_block", "accuracy"])
        for rid in ("SR-001", "SR-002", "SR-003", "SR-005", "SR-006",
                    "SR-009", "SR-010", "SR-011", "SR-012"):
            b = rule_metrics[rid]
            writer.writerow([
                b["rule_id"], b["case_count"], b["assertion_count"],
                b["correct"], b["incorrect"], b["unsafe_escape"], b["false_block"],
                f"{b['accuracy']:.6f}",
            ])

    # provenance.json
    provenance = {
        "run_id": RUN_ID,
        "safety_gold_sha256": actual_gold_sha,
        "task_corpus_sha256": actual_task_sha,
        "production_safety_rules_py_sha256": production_safety_py_hash,
        "runner_sha256": hash_text(Path(__file__).read_text(encoding="utf-8")),
        "case_count": total,
        "production_target": "weilv.safety_rules (evaluate_input_risk, filter_task_by_safety, select_safe_tasks)",
        "production_rules_path": str(PRODUCTION_RULES_PATH.relative_to(ROOT)),
        "task_corpus_path": str(TASK_CORPUS_PATH.relative_to(ROOT)),
        "gold_modified_after_freeze": False,
        "task_corpus_modified": False,
        "production_semantics_modified": False,
        "gold_fields_leaked_to_production": gold_fields_leaked,
        "leak_details": leaked_total,
        "model_call_counts": {
            "embedding": 0,
            "reranker": 0,
            "qwen_plus": 0,
        },
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    provenance_path = RUN_DIR / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"RUN_ID={RUN_ID}")
    print(f"total cases={total}")
    print(f"case_passed={case_passed_count}/{total}  Safety Decision Accuracy={safety_decision_accuracy:.4f}")
    print(f"trigger_assertions={trigger_assertion_count}  unsafe_escape_count={unsafe_escape_count}  Unsafe Escape Rate={unsafe_escape_rate:.4f}")
    print(f"control_assertions={control_assertion_count}  false_block_count={false_block_count}  False Block Rate={false_block_rate:.4f}")
    print(f"gold_fields_leaked_to_production={gold_fields_leaked}")
    for rid, b in rule_metrics.items():
        print(f"  {rid}: cases={b['case_count']} asserts={b['assertion_count']} correct={b['correct']} incorrect={b['incorrect']} unsafe_escape={b['unsafe_escape']} false_block={b['false_block']} acc={b['accuracy']:.4f}")


if __name__ == "__main__":
    main()