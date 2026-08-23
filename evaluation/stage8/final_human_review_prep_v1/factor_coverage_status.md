# Stage 8 — Factor Coverage Formal Status

## Status

**NOT_EVALUATED_INSUFFICIENT_CAPTURED_DECOMPOSITION**

## Reason

The preregistered Factor Coverage metric requires judging whether the Agentic
**structured decomposition** explicitly represents each substantive Gold factor.

Audit of the frozen formal raw results
(`evaluation/runs/20260818T020417Z_stage8_formal/raw_results.jsonl`, SHA-256 `906b4ed190594e5db2831e6240180b57b93963408f38750f309eb3922a3ba84d`) shows:

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
