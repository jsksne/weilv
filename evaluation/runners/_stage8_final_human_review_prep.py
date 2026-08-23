"""Stage 8 — final human review preparation / formal closeout (derived only).

Uses ONLY the frozen formal run outputs. No production call, no model call,
no raw-results modification.
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
    SYSTEMS,
    load_formal_micro_tasks,
    read_jsonl,
)

RUN_ID = "20260818T020417Z_stage8_formal"
RUN_DIR = ROOT / "evaluation" / "runs" / RUN_ID
PREP_DIR = ROOT / "evaluation" / "stage8" / "final_human_review_prep_v1"
REVIEWS = ROOT / "evaluation" / "reviews"
SOFT_REVIEW_CSV = REVIEWS / "stage8_soft_preference_human_review_v1.csv"
INSTRUCTIONS_MD = REVIEWS / "stage8_soft_preference_human_review_instructions_v1.md"
OLD_FACTOR_CSV = REVIEWS / "stage8_agentic_factor_coverage_human_review_v1.csv"

RAW_SHA_EXPECTED = "906b4ed190594e5db2831e6240180b57b93963408f38750f309eb3922a3ba84d"

SOFT_REVIEW_FIELDS = (
    "case_id", "system", "scenario", "gold_soft_preferences",
    "selected_task_id", "selected_task_title",
    "reviewer_A_alignment", "reviewer_A_notes",
    "reviewer_B_alignment", "reviewer_B_notes",
    "reviewer_C_alignment", "reviewer_C_notes",
    "consensus_alignment", "consensus_status", "consensus_notes",
)

INSTRUCTIONS = """# Stage 8 — Soft Preference Human Review Instructions (v1)

## Task

Three reviewers independently judge each of **33 rows** (11 applicable Gold
task cases x 3 systems) in
`stage8_soft_preference_human_review_v1.csv`.

## Question for every row

> Does this selected formal task **contradict** the stated soft preference in
> this scenario?

## Judgement values

- **ALIGNED** — the selected task does not meaningfully contradict the stated
  soft preference.
- **MISALIGNED** — the selected task meaningfully contradicts the stated soft
  preference.

## What reviewers must NOT use

- System Gold Utility (not shown in the sheet anyway)
- Preferred / Acceptable / Invalid Gold labels
- Any system aggregate score
- Claim results
- Other reviewers' decisions

Reviewers judge ONLY whether the selected task contradicts the stated soft
preference, based on the scenario text, the stated preference, and the selected
task's title/instruction semantics.

## Process

1. Each reviewer reviews all 33 rows independently first, filling only their
   own reviewer_A/B/C_alignment and notes columns.
2. After ALL independent reviews are complete, disagreements are discussed.
3. A final **consensus_alignment** is required for every row.
4. `consensus_status` is PASS (all three agree) or DISCUSSED (consensus reached
   after discussion). If consensus cannot be reached, record DISAGREEMENT and
   notes.

Do NOT fill reviewer fields for rows you did not personally judge.
"""


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    PREP_DIR.mkdir(parents=True, exist_ok=True)

    # ---- raw run integrity --------------------------------------------------
    raw_sha = hashlib.sha256((RUN_DIR / "raw_results.jsonl").read_bytes()).hexdigest()
    if raw_sha != RAW_SHA_EXPECTED:
        raise SystemExit(f"raw_results.jsonl SHA mismatch: {raw_sha}")
    (PREP_DIR / "raw_results_sha256.txt").write_text(
        f"evaluation/runs/{RUN_ID}/raw_results.jsonl\n{raw_sha}\n", encoding="utf-8"
    )

    gold = read_jsonl(FROZEN_GOLD)
    records = read_jsonl(RUN_DIR / "raw_results.jsonl")
    task_by_id = {task["task_id"]: task for task in load_formal_micro_tasks()}
    by_case = {case["case_id"]: case for case in gold}

    # ---- soft preference human review sheet (all 33 rows) --------------------
    soft_cases = [case for case in gold if case.get("gold_soft_preferences")]
    rows = []
    for case in soft_cases:
        for system in SYSTEMS:
            record = next(
                r for r in records
                if r["case_id"] == case["case_id"] and r["system"] == system
            )
            result = record.get("result")
            selected_id = result.get("selected_task_id") if result else None
            rows.append(
                {
                    "case_id": case["case_id"],
                    "system": system,
                    "scenario": case["query"][:80],
                    "gold_soft_preferences": " | ".join(case["gold_soft_preferences"]),
                    "selected_task_id": selected_id,
                    "selected_task_title": (
                        task_by_id[selected_id]["title"] if selected_id in task_by_id else ""
                    ),
                    "reviewer_A_alignment": "",
                    "reviewer_A_notes": "",
                    "reviewer_B_alignment": "",
                    "reviewer_B_notes": "",
                    "reviewer_C_alignment": "",
                    "reviewer_C_notes": "",
                    "consensus_alignment": "",
                    "consensus_status": "",
                    "consensus_notes": "",
                }
            )
    assert len(rows) == 33, f"expected 33 rows, got {len(rows)}"
    blank = all(
        not row[k] for row in rows
        for k in (
            "reviewer_A_alignment", "reviewer_A_notes", "reviewer_B_alignment",
            "reviewer_B_notes", "reviewer_C_alignment", "reviewer_C_notes",
            "consensus_alignment", "consensus_status", "consensus_notes",
        )
    )
    assert blank, "reviewer/consensus fields must be blank"
    write_csv(SOFT_REVIEW_CSV, rows, SOFT_REVIEW_FIELDS)
    write_csv(PREP_DIR / "stage8_soft_preference_human_review_v1.csv", rows, SOFT_REVIEW_FIELDS)
    INSTRUCTIONS_MD.write_text(INSTRUCTIONS, encoding="utf-8")
    (PREP_DIR / "stage8_soft_preference_human_review_instructions_v1.md").write_text(
        INSTRUCTIONS, encoding="utf-8"
    )

    # ---- factor coverage status ----------------------------------------------
    factor_status = f"""# Stage 8 — Factor Coverage Formal Status

## Status

**NOT_EVALUATED_INSUFFICIENT_CAPTURED_DECOMPOSITION**

## Reason

The preregistered Factor Coverage metric requires judging whether the Agentic
**structured decomposition** explicitly represents each substantive Gold factor.

Audit of the frozen formal raw results
(`evaluation/runs/{RUN_ID}/raw_results.jsonl`, SHA-256 `{raw_sha}`) shows:

- `agentic_diagnostics.factor_count` — present
- `agentic_diagnostics.factor_domains` — present
- `agentic_diagnostics.factor_ids` — null
- `agentic_diagnostics.factors` — null

The formal run did **not** persist the decomposition factor descriptions /
subqueries. The structured decomposition content required for the
preregistered metric therefore cannot be reliably reconstructed.

This is a **formal logging omission, not a production failure**. Production
behavior is unchanged and no claim depends on factor coverage.

## Formal metric values

| Metric | Value |
|---|---|
| Macro Required Factor Coverage | NOT_EVALUATED_INSUFFICIENT_CAPTURED_DECOMPOSITION |
| Micro Required Factor Coverage | NOT_EVALUATED_INSUFFICIENT_CAPTURED_DECOMPOSITION |
| All-Factors-Covered Rate | NOT_EVALUATED_INSUFFICIENT_CAPTURED_DECOMPOSITION |

## What was NOT used as a substitute

The final explanation, selected task, retrieved knowledge and final ranking are
NOT decomposition content and were NOT used to infer decomposition coverage.

## Memory-preference Gold factors

Gold contains `memory_preference` factors. These are intentionally supplied
later through the User Memory pipeline and are not query-visible decomposition
inputs (memory_query_leakage = 0 in the frozen Gold validation). They are
therefore outside the scope of the query-based structured decomposition.

## Prior sheets

- `stage8_agentic_factor_coverage_human_review_v1.csv` is marked
  **SUPERSEDED_NOT_VALID_FOR_FORMAL_FACTOR_COVERAGE** (see its STATUS note).
  It contained factor_domains, knowledge traces and final explanations but not
  the actual structured factor descriptions/subqueries, so it cannot support
  the preregistered metric. Preserved for audit history; reviewer fields were
  never filled.
- The earlier provisional values (Macro 0.7500 / Micro 0.7538 / All-Factors
  Covered 0.4000) are NOT final and are not reported as formal results.

The metric preregistration itself is unchanged.
"""
    (PREP_DIR / "factor_coverage_status.md").write_text(factor_status, encoding="utf-8")
    (REVIEWS / "stage8_agentic_factor_coverage_human_review_v1.SUPERSEDED.md").write_text(
        "SUPERSEDED_NOT_VALID_FOR_FORMAL_FACTOR_COVERAGE\n\n"
        "This sheet recorded factor_domains, knowledge traces and final "
        "explanations from the frozen raw results, but the formal run did not "
        "persist the structured factor descriptions/subqueries "
        "(agentic_diagnostics.factor_ids = null, factors = null). The "
        "preregistered Factor Coverage metric therefore cannot be reconstructed "
        "from it. Do NOT fill its reviewer fields. Preserved for audit history. "
        "See evaluation/stage8/final_human_review_prep_v1/factor_coverage_status.md\n",
        encoding="utf-8",
    )

    # ---- closeout status ------------------------------------------------------
    closeout = {
        "formal_run_frozen": True,
        "formal_run_rerun": False,
        "raw_results_sha256": raw_sha,
        "primary_metrics_final": True,
        "primary_metrics": {
            "basic_gold_utility_at_1": 1.3,
            "personal_gold_utility_at_1": 1.45,
            "agentic_gold_utility_at_1": 1.5,
            "agentic_minus_personal_mean_delta": 0.05,
            "wins_ties_losses": "1/19/0",
            "bootstrap_95_ci_includes_zero": True,
            "interpretation": "small positive incremental gain on the frozen benchmark",
        },
        "claims_final": True,
        "claims": {
            "CR-AGENT-001": "SUPPORTED",
            "CR-AGENT-002": "SUPPORTED",
            "CR-AGENT-003": "SUPPORTED",
            "CR-AGENT-004": "SUPPORTED",
            "CR-AGENT-005": "SUPPORTED",
            "CR-AGENT-REAL-001": "UNSUPPORTED",
        },
        "factor_coverage_status": "NOT_EVALUATED_INSUFFICIENT_CAPTURED_DECOMPOSITION",
        "soft_preference_status": "PENDING_3_REVIEWER_CONSENSUS",
        "soft_preference_review_rows": 33,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    (PREP_DIR / "final_closeout_status.json").write_text(
        json.dumps(closeout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(json.dumps(closeout, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
