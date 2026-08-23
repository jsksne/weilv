# Stage 8 — Test / Integrity Summary

## Pre-evaluation tests

- Full regression suite (non-integration, non-live): **251 passed**, 13 deselected
  (integration/live_model markers), 0 failures.
- Stage 8 evaluator tests (`tests/test_stage8_formal_evaluator.py`, 8 tests):
  - Gold-label leak guard: `runtime_fields()` never exposes preferred/acceptable/
    gold_* to production; input hash is label-independent.
  - Gold Utility@1 scoring: preferred=2, acceptable=1, invalid=0, non-allowed
    status=0, error=0.
  - Wilson 95% CI correctness.
  - Factor coverage macro/micro/all-covered computation.
  - Memory-preference alignment logic.
  - Aggregate metrics recomputed mechanically from raw results.

## Post-run mechanical verification (all PASS)

| Check | Result |
|---|---|
| Frozen Stage 8 Gold SHA unchanged | PASS |
| Stage 6 Safety Gold SHA unchanged | PASS |
| Formal task corpus canonical SHA unchanged | PASS |
| Production sources unchanged during evaluation | PASS |
| No Gold label leak into any runtime request | PASS |
| 72 / 72 expected executions recorded, none dropped | PASS |
| Aggregate metrics recomputed from raw_results match CSVs | PASS |
| Cross-system memory leakage = 0 | PASS |
| Cross-case memory leakage = 0 | PASS |
| Memory-query leakage = 0 | PASS |
| Temporary Stage 8 profiles remaining = 0 | PASS |
| Temporary Stage 8 memories remaining = 0 | PASS |
| Retry log empty (no infrastructure failures) | PASS |

## Documented limitations (do not affect metrics/claims)

1. Evaluator-side model-call wrapper counted qwen-plus calls reliably; embedding
   and rerank counts for Basic/Personal were not captured because production
   modules bind those functions at import time. Agentic model-call counts come
   from production diagnostics and are authoritative. No metric, claim or
   threshold depends on model-call counts.
2. Factor-coverage judgment uses the recorded decomposition evidence (factor
   domains, per-factor knowledge retrieval trace, served explanation). Raw
   factor subqueries are internal to the LangGraph state and not exposed by the
   production result. Memory-preference Gold factors are hidden from the query
   by design (memory_query_leakage = 0) and are handled by the memory/
   personalization pipeline, so they are recorded as not covered by the
   query-based structured decomposition.
3. This is an offline synthetic benchmark on the frozen Stage 8 Gold. Results
   are performance on this evaluation set only; no real-world health outcomes
   or clinical safety are claimed.
