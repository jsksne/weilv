# Stage 8 Gold Draft — Short Gold-design Summary

- Ticket: 微律 Stage 8 — Complex Personalization Benchmark Gold Draft
- Status: DRAFT, pending multi-reviewer consensus. Gold frozen BEFORE any Basic / Personal / Agentic result.

## Scope

Blind benchmark for the Stage 8 question: can Agentic + Personal RAG handle
complex multi-factor situations better than Personal RAG, while preserving
personalization, safety, whitelist constraints and evidence grounding?
Basic RAG stays a reference baseline only.

## Research narrative (frozen)

- Hybrid Retrieval → finds trusted evidence
- Personal RAG → adapts to the individual
- Agentic RAG → handles multiple simultaneous factors, then applies the same
  personalization and safety boundaries

No claim of "Agentic is universally better" is made. Personalization remains
the project's main contribution.

## Dataset shape

- 24 cases: AGX-001 … AGX-024
- 20 complex task-recommendation cases + 4 safety / terminal stress cases
- Every task case has ≥ 2 explicit gold factors; 20 of 20 have ≥ 3 factors
- 9 task cases use synthetic User Memory (task_preference / task_feedback only)
- Safety stress cases cover SR-001, SR-003, SR-009, SR-010, SR-011, SR-012

## Coverage (natural scenarios, not forced)

- multiple simultaneous health-behavior needs (eye + sedentary)
- available-time constraints (1 / 2 / 5 / 10 min)
- current context (home / school / study_space / bedroom)
- sleep timing / conflict (soft factor; hard SR-011 kept to safety cases)
- movement availability (recess, indoor-only, cannot_move)
- explicit soft preferences and negative preferences (不想活动)
- screen / reading state
- Personal RAG memory preference across domains

## Gold constraints

- Preferred must pass every hard constraint (context, duration, safety)
- Acceptable = safe and reasonable but weaker for the complete scenario
- Invalid = hard mismatch, semantic mismatch, or sufficiently violating an
  explicit user constraint/preference
- Labels set by semantic fit of the complete scenario, not lexical similarity

## Respecting frozen corpus limits

- All 23 formal tasks support all 3 stages → no stage-mismatch gold
- Durations only 1/2/5/10 min
- Formal contraindications empty → no contraindication-dependent gold
- SR-008 orchestration stop-condition matcher unavailable → not benchmarked
- No fabricated Agentic capabilities

## Artifacts

- `evaluation/datasets/agentic_complex_gold_draft_v1.jsonl` — 24 records, enough
  frozen runtime input to run Basic / Personal / Agentic under identical user state
- `evaluation/reviews/agentic_complex_gold_review_v1.csv` — 24 rows, reviewer fields blank
- `evaluation/reviews/agentic_complex_gold_task_audit_v1.csv` — 20 × 23 = 460 rows
- `evaluation/manifests/stage8_metric_preregistration_v1.json` — metrics frozen, NOT executed
- `evaluation/claims/claim_registry_agentic_draft_v1.csv` — claims preregistered, NOT evaluated
- `evaluation/stage8_gold_draft_validation_v1.json` — mechanical validation PASS, 0 issues

## Integrity

- Mechanical validation: all checks PASS, issue_count = 0
- No Basic / Personal / Agentic call, no embedding, no reranker, no qwen-plus
- No Stage 8 result exists; gold must remain blind until formal run
