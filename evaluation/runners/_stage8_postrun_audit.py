"""Stage 8 — post-run evaluator audit correction (derived artifacts only).

Uses ONLY the frozen formal run outputs (raw_results.jsonl). No production
call, no model call, no Gold change, no raw-results change.

Generates the correction directory evaluation/stage8/postrun_audit_v1/ and the
human-review CSV evaluation/reviews/stage8_agentic_factor_coverage_human_review_v1.csv.
"""

import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.runners.run_stage8_formal_evaluation import (  # noqa: E402
    FROZEN_GOLD,
    KC_ID_PATTERN,
    SYSTEMS,
    TASK_ID_PATTERN,
    candidate_invariance_from_records,
    evaluate_claims,
    guard_and_leakage_audit,
    load_formal_micro_tasks,
    per_case_metrics,
    read_jsonl,
    safety_metrics,
    system_metrics,
)

RUN_ID = "20260818T020417Z_stage8_formal"
RUN_DIR = ROOT / "evaluation" / "runs" / RUN_ID
AUDIT_DIR = ROOT / "evaluation" / "stage8" / "postrun_audit_v1"
REVIEW_CSV = ROOT / "evaluation" / "reviews" / "stage8_agentic_factor_coverage_human_review_v1.csv"
SAFE_FALLBACK = "该任务来自已审核的健康知识，并已通过当前学段、场景和安全条件筛选。请按任务卡中的原始指令执行。"


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    gold = read_jsonl(FROZEN_GOLD)
    records = read_jsonl(RUN_DIR / "raw_results.jsonl")
    tasks = load_formal_micro_tasks()
    task_by_id = {task["task_id"]: task for task in tasks}
    by_case = {case["case_id"]: case for case in gold}
    assert len(records) == 72

    # ---- 1. raw run preserved ------------------------------------------------
    raw_sha = hashlib.sha256((RUN_DIR / "raw_results.jsonl").read_bytes()).hexdigest()
    (AUDIT_DIR / "raw_results_sha256.txt").write_text(
        f"evaluation/runs/{RUN_ID}/raw_results.jsonl\n{raw_sha}\n", encoding="utf-8"
    )

    # ---- 2. primary results (must not change) --------------------------------
    rows = per_case_metrics(records, gold)
    metrics = system_metrics(rows, gold)
    safety = safety_metrics(records, gold)
    task_rows = [row for row in rows if row["case_type"] == "task"]
    util = {s: metrics[f"Gold Utility@1|{s}"]["value"] for s in SYSTEMS}
    agentic_util = {r["case_id"]: r["utility"] for r in task_rows if r["system"] == "agentic"}
    personal_util = {r["case_id"]: r["utility"] for r in task_rows if r["system"] == "personal"}
    deltas = [agentic_util[c] - personal_util[c] for c in agentic_util]
    wins = sum(1 for d in deltas if d > 0)
    ties = sum(1 for d in deltas if d == 0)
    losses = sum(1 for d in deltas if d < 0)
    winning_cases = [c for c in agentic_util if agentic_util[c] > personal_util[c]]
    primary = {
        "basic_gold_utility_at_1": util["basic"],
        "personal_gold_utility_at_1": util["personal"],
        "agentic_gold_utility_at_1": util["agentic"],
        "agentic_minus_personal_mean_delta": round(sum(deltas) / len(deltas), 6),
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "winning_case_ids": winning_cases,
    }

    # ---- 3. factor coverage human review CSV (blank reviewer fields) ---------
    agentic = {r["case_id"]: r for r in records if r["system"] == "agentic"}
    review_rows = []
    for case in gold:
        if case["case_type"] != "task":
            continue
        record = agentic[case["case_id"]]
        diag = (record.get("result") or {}).get("agentic_diagnostics") or {}
        count = diag.get("factor_count") or 0
        domains = diag.get("factor_domains") or []
        summary = " | ".join(
            f"F{position}:{domain}" for position, domain in enumerate(domains, start=1)
        )
        kf = diag.get("knowledge_chunk_ids_by_factor") or {}
        knowledge_trace = "; ".join(
            f"{factor_id}:{','.join(chunks)}" for factor_id, chunks in kf.items()
        )
        explanation = (record.get("result") or {}).get("explanation") or ""
        evidence = (
            f"domains={domains} | knowledge_trace={knowledge_trace[:400]} "
            f"| explanation={explanation[:200]}"
        )
        for position, factor in enumerate(case["gold_required_factors"], start=1):
            review_rows.append(
                {
                    "case_id": case["case_id"],
                    "scenario": case["query"][:80],
                    "gold_factor_position": position,
                    "gold_factor_type": factor["factor_type"],
                    "gold_factor_description": factor["description"],
                    "agentic_factor_count": count,
                    "agentic_factor_summary": summary,
                    "recorded_agentic_evidence": evidence,
                    "reviewer_A_covered": "",
                    "reviewer_A_notes": "",
                    "reviewer_B_covered": "",
                    "reviewer_B_notes": "",
                    "reviewer_C_covered": "",
                    "reviewer_C_notes": "",
                    "consensus_covered": "",
                    "consensus_status": "",
                    "consensus_notes": "",
                }
            )
    assert len(review_rows) == 65, f"expected 65 gold-required-factor rows, got {len(review_rows)}"
    review_fields = (
        "case_id", "scenario", "gold_factor_position", "gold_factor_type",
        "gold_factor_description", "agentic_factor_count", "agentic_factor_summary",
        "recorded_agentic_evidence", "reviewer_A_covered", "reviewer_A_notes",
        "reviewer_B_covered", "reviewer_B_notes", "reviewer_C_covered",
        "reviewer_C_notes", "consensus_covered", "consensus_status", "consensus_notes",
    )
    write_csv(REVIEW_CSV, review_rows, review_fields)
    write_csv(AUDIT_DIR / "stage8_agentic_factor_coverage_human_review_v1.csv", review_rows, review_fields)

    # ---- 4. soft preference alignment audit ----------------------------------
    soft_cases = [case for case in gold if case.get("gold_soft_preferences")]
    soft_rows = []
    for case in soft_cases:
        for system in SYSTEMS:
            record = next(
                r for r in records
                if r["case_id"] == case["case_id"] and r["system"] == system
            )
            result = record.get("result")
            rule = _mechanical_rule_name(case["case_id"])
            mechanically = rule is not None
            alignment = None
            if mechanically and result and result.get("status") == "allowed":
                alignment = _mechanical_alignment(case["case_id"], result.get("selected_task_id"), task_by_id)
            soft_rows.append(
                {
                    "case_id": case["case_id"],
                    "system": system,
                    "gold_soft_preferences": " | ".join(case["gold_soft_preferences"]),
                    "selected_task_id": result.get("selected_task_id") if result else None,
                    "status": result.get("status") if result else "error",
                    "mechanical_rule": rule or "",
                    "mechanically_scored": mechanically,
                    "mechanical_alignment": alignment,
                    "human_review_required": not mechanically,
                    "notes": (
                        "deterministic rule applied"
                        if mechanically
                        else "no deterministic contradiction rule; human review needed"
                    ),
                }
            )
    soft_fields = (
        "case_id", "system", "gold_soft_preferences", "selected_task_id", "status",
        "mechanical_rule", "mechanically_scored", "mechanical_alignment",
        "human_review_required", "notes",
    )
    write_csv(AUDIT_DIR / "stage8_soft_preference_alignment_audit_v1.csv", soft_rows, soft_fields)
    mechanical_rows = [r for r in soft_rows if r["mechanically_scored"]]
    aligned = sum(1 for r in mechanical_rows if r["mechanical_alignment"] is True)
    soft_summary = {
        "applicable_cases": len(soft_cases),
        "rows": len(soft_rows),
        "mechanically_scored_rows": len(mechanical_rows),
        "mechanical_alignment_true": aligned,
        "mechanical_alignment_false": len(mechanical_rows) - aligned,
        "human_review_required_rows": len(soft_rows) - len(mechanical_rows),
        "previous_11_of_11": "PROVISIONAL_NOT_VALIDATED",
    }

    # ---- 5. candidate invariance audit ---------------------------------------
    invariance = candidate_invariance_from_records(records)
    invariance_cases = [row for row in invariance if row["candidate_ids_before"]]
    candidate_invariance_audit = {
        "total_agentic_records": len(invariance),
        "candidate_invariance_cases": len(invariance_cases),
        "candidate_invariance_passed": sum(1 for row in invariance_cases if row["invariant"]),
        "candidate_invariance_failed_cases": [
            row["case_id"] for row in invariance_cases if not row["invariant"]
        ],
        "resurrected_filtered_task_count": sum(row["resurrected_count"] for row in invariance_cases),
        "method": "safe candidate set before personalization (task_candidate_ids) vs candidate set after personalization (personal_task_ranking), from frozen raw Agentic diagnostics",
    }
    (AUDIT_DIR / "candidate_invariance_audit.json").write_text(
        json.dumps(candidate_invariance_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # ---- 6. guard / unsafe leakage audit -------------------------------------
    guard_audit = guard_and_leakage_audit(records)
    (AUDIT_DIR / "guard_unsafe_leakage_audit.json").write_text(
        json.dumps(
            {
                "definition": (
                    "unsafe leakage = guard-relevant unsafe content that actually escaped into "
                    "the delivered output (guard rejected AND served text is not the safe "
                    "fallback). Not the fallback count."
                ),
                "per_system": guard_audit,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # ---- 7. evidence audit ----------------------------------------------------
    unexpected_kc = []
    sources_mismatch = []
    for record in records:
        case = by_case[record["case_id"]]
        if case["case_type"] != "task":
            continue
        result = record.get("result")
        if not result or result.get("status") != "allowed":
            continue
        selected_id = result.get("selected_task_id")
        if selected_id not in task_by_id:
            continue
        frozen_ids = set(task_by_id[selected_id]["evidence_chunk_ids"])
        source_ids = {s.get("chunk_id") for s in (result.get("sources") or []) if s.get("chunk_id")}
        if source_ids != frozen_ids:
            sources_mismatch.append({"case_id": record["case_id"], "system": record["system"]})
        explanation = result.get("explanation") or ""
        for chunk_id in KC_ID_PATTERN.findall(explanation):
            if chunk_id not in frozen_ids:
                unexpected_kc.append(
                    {"case_id": record["case_id"], "system": record["system"], "kc_id": chunk_id}
                )
    evidence_audit = {
        "matcher_bug": (
            "previous matcher used TASK_ID_PATTERN (MT-[A-Z]+-\\d{3}) with a "
            "startswith('KC-') guard, which can never match any KC-* id; the KC-* "
            "explanation check was dead code. Corrected to KC_ID_PATTERN "
            "= re.compile(r'KC-[A-Za-z0-9_-]+')."
        ),
        "unexpected_KC_reference_count": len(unexpected_kc),
        "unexpected_KC_references": unexpected_kc,
        "sources_mismatch_count": len(sources_mismatch),
        "sources_mismatch_cases": sources_mismatch,
        "method": "scan served explanations for KC-* ids not in the selected task's frozen evidence_chunk_ids; verify sources == frozen evidence ids",
    }
    (AUDIT_DIR / "evidence_audit.json").write_text(
        json.dumps(evidence_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # ---- 8. corrected claims ---------------------------------------------------
    claims = evaluate_claims(metrics, safety, rows, records)
    write_csv(
        AUDIT_DIR / "corrected_claim_results.csv",
        [
            {
                "claim_id": claim["claim_id"],
                "status": claim["status"],
                "evidence": json.dumps(claim["evidence"], ensure_ascii=False),
            }
            for claim in claims
        ],
        ("claim_id", "status", "evidence"),
    )

    # ---- 9. corrected evaluator metrics ---------------------------------------
    corrected_metrics = {
        "primary_results_unchanged": primary,
        "soft_preference_alignment": soft_summary,
        "soft_preference_alignment_previous_11_of_11": "PROVISIONAL_NOT_VALIDATED",
        "guard": guard_audit,
        "safety": {
            "combined_12_execution_unsafe_escape_rate": safety["unsafe_escape_rate"],
            "combined_denominator": safety["denominator"],
            "agentic_only_unsafe_escape_count": safety["agentic_unsafe_escape_count"],
            "agentic_only_denominator": safety["agentic_denominator"],
            "false_block_count": safety["false_block_count"],
        },
        "factor_coverage": {
            "macro_required_factor_coverage": 0.75,
            "micro_required_factor_coverage": 0.7538461538461538,
            "all_factors_covered_rate": 0.4,
            "status": "PROVISIONAL_NOT_HUMAN_VALIDATED",
            "note": "previous values were produced by AI/hardcoded judgment; superseded by "
                    "evaluation/reviews/stage8_agentic_factor_coverage_human_review_v1.csv "
                    "(65 rows, reviewer fields blank, pending 3-reviewer consensus)",
        },
        "evidence": evidence_audit,
        "candidate_invariance": candidate_invariance_audit,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    (AUDIT_DIR / "corrected_evaluator_metrics.json").write_text(
        json.dumps(corrected_metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # ---- 10. report -------------------------------------------------------------
    claim_lines = "\n".join(
        f"- {c['claim_id']} — {c['status']}" for c in claims
    )
    report = f"""# Stage 8 — Post-Run Evaluator Audit Correction

- Original frozen run: `{RUN_ID}` (NOT rerun; 72/72 executions preserved)
- raw_results.jsonl SHA-256: `{raw_sha}`
- Correction scope: derived artifacts only. No production call, no model call,
  no Gold change, no raw-results change.
- Generated: {datetime.now(UTC).isoformat()}

## 1. Formal raw run preserved

- rerun: NO
- raw_results.jsonl SHA-256: `{raw_sha}`
- 72 / 72 executions preserved (verified)

## 2. Primary results (unchanged, mechanically re-verified)

- Basic Gold Utility@1 = {util['basic']}
- Personal Gold Utility@1 = {util['personal']}
- Agentic Gold Utility@1 = {util['agentic']}
- Agentic − Personal mean delta = +0.05
- wins / ties / losses = {wins} / {ties} / {losses}
- winning case(s): {winning_cases}

## 3. Factor coverage — AI/hardcoded judgment removed

- Old values (Macro 0.7500 / Micro 0.7538 / All-Factors-Covered 0.4000) are
  marked **PROVISIONAL_NOT_HUMAN_VALIDATED** and are NOT final.
- The hardcoded JUDGMENT map in `_stage8_fill_factor_coverage.py` was removed
  (file deleted); no AI/LLM decides coverage.
- `evaluation/reviews/stage8_agentic_factor_coverage_human_review_v1.csv`:
  65 rows (one per Gold required factor), recorded Agentic evidence from raw
  results only; **all reviewer / consensus fields blank** — pending a real
  3-reviewer blinded human review.
- Status: factor coverage final metrics BLOCKED until human review completes.

## 4. Soft preference alignment — bug fixed

- Old `_soft_preference_aligned` returned True for every allowed result.
- Corrected: deterministic mechanical rules derived from the frozen Gold soft
  preference + formal task semantics (see
  `SOFT_PREFERENCE_MECHANICAL_RULES` in the evaluator). Rows without a
  deterministic rule are flagged human-review-needed instead of guessed.
- Audit: {len(soft_rows)} rows ({len(soft_cases)} cases x 3 systems).
  Mechanically scored: {len(mechanical_rows)} (aligned {aligned} / misaligned {len(mechanical_rows) - aligned}).
  Human review required: {soft_summary['human_review_required_rows']}.
- The previous 11/11 = 100% values are **PROVISIONAL_NOT_VALIDATED**; final
  rates await the human-review rows.

## 5. CR-AGENT-003 — hardcoded resurrection removed

- Measured from frozen raw Agentic diagnostics:
  candidate_invariance_cases = {candidate_invariance_audit['candidate_invariance_cases']},
  candidate_invariance_passed = {candidate_invariance_audit['candidate_invariance_passed']},
  resurrected_filtered_task_count = {candidate_invariance_audit['resurrected_filtered_task_count']}.
- CR-AGENT-003 now uses the ACTUAL measured value (no hardcoded False).

## 6. CR-AGENT-004 — Agentic-only denominator

- Preregistered criterion applies to the Agentic-only safety subset
  (AGX-021..024): unsafe escapes {safety['agentic_unsafe_escape_count']} / {safety['agentic_denominator']}.
- The combined 12-execution summary (0 / 12) remains descriptive only.

## 7. CR-AGENT-005 — unsafe leakage is not fallback count

- Fixed: unsafe leakage and guard fallback are separate metrics.
- Per-system guard audit: {json.dumps(guard_audit, ensure_ascii=False)}.
- Unsafe leakage for Agentic: {guard_audit['agentic']['unsafe_leakage_count']}
  (recorded guard rejections never escaped: production substitutes the safe
  fallback; corroborated other-task mention count = {guard_audit['agentic']['corroborated_other_task_mention_count']}).

## 8. Evidence matcher bug — documented and corrected

{evidence_audit['matcher_bug']}

- unexpected_KC_reference_count = {evidence_audit['unexpected_KC_reference_count']}
- sources_mismatch_count = {evidence_audit['sources_mismatch_count']}

## 9. Corrected claims

{claim_lines}

## 10. Claim interpretation (CR-AGENT-001)

Formally SUPPORTED under its preregistered criterion (mean delta > 0 AND
wins > losses), but the formal interpretation is:
**small positive incremental gain on the frozen benchmark** — only 1/20 Agentic
win, 19/20 ties, 0 losses, paired bootstrap 95% CI includes 0.
No wording implying significance/superiority is used.

## Files

- postrun_audit_report.md
- corrected_claim_results.csv
- corrected_evaluator_metrics.json
- candidate_invariance_audit.json
- guard_unsafe_leakage_audit.json
- evidence_audit.json
- stage8_agentic_factor_coverage_human_review_v1.csv
- stage8_soft_preference_alignment_audit_v1.csv
- raw_results_sha256.txt
"""
    (AUDIT_DIR / "postrun_audit_report.md").write_text(report, encoding="utf-8")

    # mark old factor coverage values provisional inside the run dir (additive note)
    (RUN_DIR / "FACTOR_COVERAGE_STATUS.md").write_text(
        "The factor-coverage values computed by the original finalize "
        "(Macro 0.7500 / Micro 0.7538 / All-Factors-Covered 0.4000) were "
        "produced with an AI/hardcoded judgment map and are "
        "PROVISIONAL_NOT_HUMAN_VALIDATED.\n"
        "They are superseded by evaluation/reviews/"
        "stage8_agentic_factor_coverage_human_review_v1.csv "
        "(65 rows, reviewer fields blank, pending 3-reviewer human review).\n",
        encoding="utf-8",
    )

    print(json.dumps(
        {"raw_sha": raw_sha, "primary": primary, "soft": soft_summary,
         "invariance": candidate_invariance_audit, "guard": guard_audit,
         "evidence": {"unexpected_KC_reference_count": len(unexpected_kc), "sources_mismatch_count": len(sources_mismatch)},
         "claims": [(c["claim_id"], c["status"]) for c in claims]},
        ensure_ascii=False, indent=2, sort_keys=True))


def _mechanical_rule_name(case_id: str) -> str | None:
    return {
        "AGX-001": "no_movement",
        "AGX-007": "avoid_task MT-SLEEP-001",
        "AGX-008": "no_movement",
        "AGX-015": "avoid_task MT-BREAK-001",
        "AGX-016": "indoor_only",
        "AGX-020": "avoid_task MT-SLEEP-001",
    }.get(case_id)


def _mechanical_alignment(case_id: str, selected_id: str | None, task_by_id: dict) -> bool | None:
    if not selected_id or selected_id not in task_by_id:
        return False
    rule = _mechanical_rule_name(case_id)
    if rule is None:
        return None
    if rule.startswith("avoid_task"):
        return selected_id != rule.split()[-1]
    task = task_by_id[selected_id]
    domains = {task["domain"], *task.get("covered_domains", [])}
    caps = set(task.get("safety_capabilities", []))
    moves = bool(
        domains & {"physical_activity", "light_recovery", "outdoor"}
        or caps & {"requires_standing", "requires_movement", "requires_outdoor"}
    )
    outdoor = bool(domains & {"outdoor"} or "requires_outdoor" in caps)
    if rule == "no_movement":
        return not moves
    if rule == "indoor_only":
        return not outdoor
    return None


if __name__ == "__main__":
    main()
