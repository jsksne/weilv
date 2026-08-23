# Stage 8 Gold Draft v1.2 — Final Pre-Human-Review Patch Summary

- Ticket: 微律 Stage 8 Gold v1.2 — Final Pre-Human-Review Patch
- Status: DRAFT, pending multi-reviewer consensus. Gold frozen BEFORE any Basic / Personal / Agentic result.
- v1 / v1.1 artifacts preserved unchanged for audit history; v1.2 artifacts created as new files.

## Patch changes

1. AGX-004 — MT-OUT-001 moved acceptable → invalid (environment_mismatch).
   The scenario establishes school recess and a light-movement preference but
   does NOT establish that an outdoor execution environment is available;
   outdoor availability is not inferred. Other AGX-004 labels unchanged
   (MT-BREAK-004 preferred, MT-SED-001 acceptable).

2. Factor Coverage terminology corrected in
   `stage8_metric_preregistration_v1_2.json`:
   - Macro Required Factor Coverage = mean of per-case factor coverage values
   - Micro Required Factor Coverage = sum of covered required factors across
     all task cases / sum of all required factors across all task cases
   - All-Factors-Covered Rate unchanged (Wilson 95% CI)
   - Descriptive mechanism diagnostics only; no thresholds; no Basic/Personal
     comparison; not used for superiority claims.

## Validation (all PASS, issue_count = 0)

- cases = 24 (20 task + 4 safety), memory cases = 9
- memory_query_leakage_count = 0
- AGX-004 MT-OUT-001 = invalid confirmed
- every task case >= 1 preferred; preferred/acceptable disjoint
- full 23-task partition per task case; no unsupported task IDs
- context / duration / safety valid for all Preferred
- reviewer fields blank; review_status = pending_multi_reviewer_consensus
- model calls: embedding 0 / reranker 0 / qwen_plus 0
- no model/result leakage

## Artifacts (new v1.2)

- `evaluation/datasets/agentic_complex_gold_draft_v1_2.jsonl`
- `evaluation/reviews/agentic_complex_gold_review_v1_2.csv`
- `evaluation/reviews/agentic_complex_gold_task_audit_v1_2.csv`
- `evaluation/manifests/stage8_metric_preregistration_v1_2.json`
- `evaluation/claims/claim_registry_agentic_draft_v1_2.csv`
- `evaluation/stage8_gold_draft_validation_v1_2.json`

## Integrity

- No Basic / Personal / Agentic call, no embedding, no reranker, no qwen-plus
- No Stage 8 result exists; Gold must remain blind until formal run
