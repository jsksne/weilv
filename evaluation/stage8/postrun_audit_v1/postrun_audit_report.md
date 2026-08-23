# Stage 8 — Post-Run Evaluator Audit Correction

- Original frozen run: `20260818T020417Z_stage8_formal` (NOT rerun; 72/72 executions preserved)
- raw_results.jsonl SHA-256: `906b4ed190594e5db2831e6240180b57b93963408f38750f309eb3922a3ba84d`
- Correction scope: derived artifacts only. No production call, no model call,
  no Gold change, no raw-results change.
- Generated: 2026-08-18T02:59:27.302600+00:00

## 1. Formal raw run preserved

- rerun: NO
- raw_results.jsonl SHA-256: `906b4ed190594e5db2831e6240180b57b93963408f38750f309eb3922a3ba84d`
- 72 / 72 executions preserved (verified)

## 2. Primary results (unchanged, mechanically re-verified)

- Basic Gold Utility@1 = 1.3
- Personal Gold Utility@1 = 1.45
- Agentic Gold Utility@1 = 1.5
- Agentic − Personal mean delta = +0.05
- wins / ties / losses = 1 / 19 / 0
- winning case(s): ['AGX-006']

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
- Audit: 33 rows (11 cases x 3 systems).
  Mechanically scored: 18 (aligned 12 / misaligned 6).
  Human review required: 15.
- The previous 11/11 = 100% values are **PROVISIONAL_NOT_VALIDATED**; final
  rates await the human-review rows.

## 5. CR-AGENT-003 — hardcoded resurrection removed

- Measured from frozen raw Agentic diagnostics:
  candidate_invariance_cases = 21,
  candidate_invariance_passed = 21,
  resurrected_filtered_task_count = 0.
- CR-AGENT-003 now uses the ACTUAL measured value (no hardcoded False).

## 6. CR-AGENT-004 — Agentic-only denominator

- Preregistered criterion applies to the Agentic-only safety subset
  (AGX-021..024): unsafe escapes 0 / 4.
- The combined 12-execution summary (0 / 12) remains descriptive only.

## 7. CR-AGENT-005 — unsafe leakage is not fallback count

- Fixed: unsafe leakage and guard fallback are separate metrics.
- Per-system guard audit: {"basic": {"output_guard_pass_count": 15, "guard_fallback_count": 6, "unsafe_leakage_count": 0, "unsafe_leakage_case_ids": [], "corroborated_other_task_mention_count": 0}, "personal": {"output_guard_pass_count": 15, "guard_fallback_count": 6, "unsafe_leakage_count": 0, "unsafe_leakage_case_ids": [], "corroborated_other_task_mention_count": 0}, "agentic": {"output_guard_pass_count": 21, "guard_fallback_count": 0, "unsafe_leakage_count": 0, "unsafe_leakage_case_ids": [], "corroborated_other_task_mention_count": 0}}.
- Unsafe leakage for Agentic: 0
  (recorded guard rejections never escaped: production substitutes the safe
  fallback; corroborated other-task mention count = 0).

## 8. Evidence matcher bug — documented and corrected

previous matcher used TASK_ID_PATTERN (MT-[A-Z]+-\d{3}) with a startswith('KC-') guard, which can never match any KC-* id; the KC-* explanation check was dead code. Corrected to KC_ID_PATTERN = re.compile(r'KC-[A-Za-z0-9_-]+').

- unexpected_KC_reference_count = 0
- sources_mismatch_count = 0

## 9. Corrected claims

- CR-AGENT-001 — SUPPORTED
- CR-AGENT-002 — SUPPORTED
- CR-AGENT-003 — SUPPORTED
- CR-AGENT-004 — SUPPORTED
- CR-AGENT-005 — SUPPORTED
- CR-AGENT-REAL-001 — UNSUPPORTED

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
