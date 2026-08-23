# STAGE8_FINAL_FROZEN

- Status: **FROZEN**
- Formal run: `20260818T020417Z_stage8_formal` (never rerun)
- raw_results SHA-256: `906b4ed190594e5db2831e6240180b57b93963408f38750f309eb3922a3ba84d`
- Frozen on: 2026-08-18T05:37:41.107640+00:00

## A. Formal benchmark

- 24 total cases: 20 task + 4 safety (9 memory cases)

## B. Basic RAG

- Gold Utility@1 = 1.30 (26 / 20)
- Preferred@1 = 8 / 20 = 0.4000
- Valid@1 = 18 / 20 = 0.9000
- Invalid Rate = 2 / 20 = 0.1000
- Soft Preference Alignment (3-human consensus) = 10 / 11 = 0.9091

## C. Personal RAG

- Gold Utility@1 = 1.45 (29 / 20)
- Preferred@1 = 12 / 20 = 0.6000
- Valid@1 = 17 / 20 = 0.8500
- Invalid Rate = 3 / 20 = 0.1500
- Memory Preference Alignment = 8 / 9 = 0.8889
- Soft Preference Alignment (3-human consensus) = 10 / 11 = 0.9091

## D. Agentic RAG

- Gold Utility@1 = 1.50 (30 / 20)
- Preferred@1 = 13 / 20 = 0.6500
- Valid@1 = 17 / 20 = 0.8500
- Invalid Rate = 3 / 20 = 0.1500
- Memory Preference Alignment = 8 / 9 = 0.8889
- Soft Preference Alignment (3-human consensus) = 10 / 11 = 0.9091

## E. Agentic vs Personal

- Mean paired Gold Utility@1 delta = +0.05
- Wins / Ties / Losses = 1 / 19 / 0
- Paired bootstrap 95% CI = [0.00, 0.15] (includes 0)
- Winning case: AGX-006

## F. Safety

- Unsafe escapes = 0 (all systems; Agentic-only subset 0 / 4)
- False blocks = 0

## G. Evidence / Guard

- Evidence Contamination = 0 (all systems)
- Unsafe Leakage = 0 (separate from guard fallback)
- Output Guard pass / fallback (honest): Basic 15 / 21 (fallback 6), Personal 15 / 21 (fallback 6), Agentic 21 / 21 (fallback 0)

## H. Factor Coverage

- Macro Required Factor Coverage: NOT_EVALUATED_INSUFFICIENT_CAPTURED_DECOMPOSITION
- Micro Required Factor Coverage: NOT_EVALUATED_INSUFFICIENT_CAPTURED_DECOMPOSITION
- All-Factors-Covered Rate: NOT_EVALUATED_INSUFFICIENT_CAPTURED_DECOMPOSITION

## I. Claims

- CR-AGENT-001 SUPPORTED
- CR-AGENT-002 SUPPORTED
- CR-AGENT-003 SUPPORTED
- CR-AGENT-004 SUPPORTED
- CR-AGENT-005 SUPPORTED
- CR-AGENT-REAL-001 UNSUPPORTED

## J. Limitations

- Synthetic offline benchmark; does not establish real-world health efficacy or
  clinical safety.
- N = 20 task cases for task recommendation metrics.
- Agentic incremental gain observed in only 1 task case (AGX-006); 19 ties,
  0 losses; paired bootstrap 95% CI includes 0.
- Formal factor decomposition text (factor descriptions/subqueries) was not
  persisted by the formal run (factor_ids/factors = null in diagnostics);
  Factor Coverage is therefore NOT_EVALUATED — a documented logging
  limitation, not a production failure.
- Offline results do not establish real-world health outcomes or
  population-level generalization.

## Final research interpretation

Hybrid Retrieval -> trusted evidence retrieval; Personal RAG -> the main
personalization gain (Basic 1.30 -> Personal 1.45, +0.15); Agentic + LangGraph
-> a small additional gain in complex multi-factor handling while preserving
the same personalization and safety boundaries (Personal 1.45 -> Agentic 1.50,
+0.05). Agentic is NOT framed as the project's main innovation;
personalization remains the main contribution.
