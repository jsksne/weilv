# Stage 8 Gold Draft v1.1 — Project Review Patch Summary

- Ticket: 微律 Stage 8 Gold Draft v1.1 — Project Review Patch
- Status: DRAFT, pending multi-reviewer consensus. Gold frozen BEFORE any Basic / Personal / Agentic result.
- v1 artifacts preserved unchanged for audit history; v1.1 artifacts created as new files.

## Patch changes

1. Memory-query leakage (CRITICAL, 9/9 fixed)
   - AGX-005 / 008 / 009 / 011 / 013 / 015 / 017 / 018 / 020 queries rewritten to
     remove historical memory phrases (以前试过 / 说过喜欢 / 之前执行过 / 觉得没用 …).
   - Historical signal now exists ONLY inside `synthetic_memory_fixture`.
   - Current-state preferences that belong to the current interaction are retained.
   - Gold labels still incorporate hidden memory because Personal/Agentic receive the fixture.
   - Validation: `memory_query_leakage_count = 0`.

2. AGX-007 — MT-SLEEP-001 moved acceptable → invalid (contradicts the explicit
   must-use-device requirement). Preferred stays MT-SLEEP-004.

3. AGX-020 — MT-SLEEP-001 moved acceptable → invalid (user must still use the
   tablet briefly). Preferred stays MT-EYE-002; MT-SLEEP-004 stays acceptable
   (negative memory is a soft signal).

4. AGX-023 — rewritten to a current commute scenario (moving, shaky vehicle;
   cannot_move, unstable_environment, reading). Outcome recomputed from formal
   task metadata: only MT-EYE-003 survives SR-010 and its execution_contexts
   include commute → status = allowed, expected allowed set = [MT-EYE-003].

5. AGX-024 — rewritten to a natural nighttime moving-vehicle case (sleep
   displaced by study + unstable + cannot_move at commute). Recomputed from
   metadata: MT-EYE-003 is blocked by SR-011 (continue_study) → no_safe_task.
   Mechanical simulation confirms.

6. AGX-014 — removed the unsupported exact one-hour wake-time rule.
   gold_soft_preferences now contains only the user's expressed desire to
   sleep later on the weekend.

7. Factor-coverage mechanism metrics preregistered in
   `stage8_metric_preregistration_v1_1.json`:
   Required Factor Coverage (micro + case-macro) and All-Factors-Covered Rate
   (Wilson 95% CI). Mechanism diagnostics only; no Basic/Personal comparison;
   not used for superiority claims.

## Validation

- 24 cases (20 task + 4 safety), 9 memory cases, all checks PASS, issue_count = 0
- memory_query_leakage_count = 0
- Gold partition complete over 23 formal tasks per task case
- Preferred context/duration/safety valid
- AGX-007 / AGX-020 MT-SLEEP-001 invalid confirmed
- AGX-023 / AGX-024 outcomes confirmed by metadata simulation
- AGX-014 no unsupported one-hour rule
- no model/result leakage; model calls embedding 0 / reranker 0 / qwen_plus 0

## Artifacts (new v1.1)

- `evaluation/datasets/agentic_complex_gold_draft_v1_1.jsonl`
- `evaluation/reviews/agentic_complex_gold_review_v1_1.csv`
- `evaluation/reviews/agentic_complex_gold_task_audit_v1_1.csv`
- `evaluation/manifests/stage8_metric_preregistration_v1_1.json`
- `evaluation/claims/claim_registry_agentic_draft_v1_1.csv`
- `evaluation/stage8_gold_draft_validation_v1_1.json`

## Integrity

- No Basic / Personal / Agentic call, no embedding, no reranker, no qwen-plus
- No Stage 8 result exists; Gold must remain blind until formal run
