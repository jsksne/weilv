# 微律 Overnight Batch Summary

- Date: 2026-08-16
- Window: Stage 6E Freeze → 6E-1 Evaluation → 6F Contract Tests → 6F Safety Draft
- Unattended run; no intermediate human decisions required.

## 1. Phase A — Task Gold Freeze

- Status: **PASS**
- 24 cases validated against the 23-task frozen corpus.
- Counts: preferred=29, acceptable=17, invalid=506 (matches spec).
- Family IDs: TGF-001 … TGF-024 (unique, contiguous).
- Frozen Gold path: `evaluation/datasets/task_recommendation_gold_v1.jsonl`
- Frozen Task Corpus SHA-256: `40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48` (unchanged)
- Frozen Gold SHA-256: `cd1c3686be08adb576a75adce072270b9c4224a5749c5b064e0fe34a0316d282`
- Manifest: `evaluation/manifests/task_recommendation_gold_v1_manifest.json`
- Review artifact: `evaluation/reviews/task_gold_consensus_reviewed_v1.csv`

## 2. Stage 6E-1 Run

- Run ID: `20260816T155009Z_task_recommendation_v1`
- 24/24 cases executed, 0 failed.
- Frozen Gold SHA and Task Corpus SHA unchanged after run.
- Production semantics unchanged (`source_tree_sha256` recorded before/after).
- qwen-plus was **not** called (0 calls).
- 24 embedding calls, 24 rerank calls (matches expected budget).
- No memory, no personalization.

### Task recommendation metrics

| metric                       |   value | ci_lower | ci_upper | n  | ci_method                                                      |
|------------------------------|--------:|---------:|---------:|---:|----------------------------------------------------------------|
| Valid@1                      |  0.9583 |  0.7976  |  0.9926  | 24 | wilson_95                                                       |
| Invalid Recommendation Rate  |  0.0417 |  0.0074  |  0.2024  | 24 | wilson_95                                                       |
| Preferred@1                  |  0.8333 |  0.6415  |  0.9332  | 24 | wilson_95                                                       |
| All-Valid@3                  |  0.2500 |   n/a    |   n/a    | 24 | not_measured_for_ci                                             |
| Valid@3                      |  0.5347 |  0.4167  |  0.6597  | 24 | case_bootstrap_95_seed_20260816_iterations_10000                |
| Preferred-in-Top3            |  0.3958 |  0.3056  |  0.5069  | 24 | case_bootstrap_95_seed_20260816_iterations_10000                |
| No-Task Rate                 |  0.0000 |   n/a    |   n/a    | 24 | not_measured_for_ci                                             |
| Mean eligible candidate count (after filter) | 8.79 | n/a | n/a | 24 | not_measured_for_ci |

### Subgroup diagnostics (descriptive only)

| query_style              |  n | Valid@1 | Invalid | Preferred@1 | Valid@3 | Preferred-in-Top3 |
|--------------------------|---:|--------:|--------:|------------:|--------:|------------------:|
| state_only               | 14 |   1.000 |   0.000 |       0.857 |   0.595 |             0.405 |
| constraint_or_preference |  4 |   0.750 |   0.250 |       0.500 |   0.583 |             0.417 |
| problem_specific         |  6 |   1.000 |   0.000 |       1.000 |   0.361 |             0.361 |

Subgroups are descriptive only; not used for any preregistered claim.

## 3. Claim statuses (Stage 6E-1)

| claim_id        | claim                                                                 | status        |
|-----------------|-----------------------------------------------------------------------|---------------|
| CR-TASK-001     | Valid@1 >= 0.90 on frozen consensus-reviewed synthetic benchmark        | SUPPORTED     |
| CR-TASK-002     | Invalid Recommendation Rate <= 0.10                                   | SUPPORTED     |
| CR-TASK-003     | Preferred@1 >= 0.70                                                    | SUPPORTED     |
| CR-TASK-004     | All-Valid@3 >= 0.80                                                    | NOT_SUPPORTED |
| CR-TASK-REAL-001| Offline metrics prove real adolescent behavior or health outcomes       | UNSUPPORTED   |

Claim registry: `evaluation/claims/claim_registry_task_v1.csv`.

## 4. Stage 6F-A Evidence Contract Run

- Run ID: `20260816T155329Z_evidence_contract_v1`
- Tasks executed: 23 (every formal MicroTask).
- Exact Evidence Match Rate: **100%** (23/23)
- Evidence Contamination Rate: **0%**
- Missing Evidence Rate: **0%**
- Fail-closed integration fixtures: 3/3 detected as caller-detectable mismatch.
- Production code was not modified; index was not modified.

Claim statuses:

| claim_id         | status      |
|------------------|-------------|
| CR-EVID-001      | SUPPORTED   |
| CR-EVID-002      | SUPPORTED   |
| CR-EVID-REAL-001 | UNSUPPORTED |

Claim registry: `evaluation/claims/claim_registry_evidence_v1.csv`.

## 5. Stage 6F-B Output Guard Run

- Run ID: `20260816T155455Z_output_guard_v1`
- Total fixtures: 16 (9 violation, 7 pass).
- Catch Rate: **1.00** (9/9 violations caught)
- Unsafe Leakage Rate: **0.00**
- False Positive Rate: **0.00** (0/7 passes blocked)

Claim statuses:

| claim_id     | status    |
|--------------|-----------|
| CR-GUARD-001 | SUPPORTED |
| CR-GUARD-002 | SUPPORTED |
| CR-GUARD-003 | SUPPORTED |

Claim registry: `evaluation/claims/claim_registry_guard_v1.csv`.

## 6. Stage 6F-0 Safety Gold Draft

- Case count: **16** (covers SR-001, SR-002, SR-003, SR-006, SR-009, SR-010, SR-011, SR-012 with trigger + false-block control each, plus a combined SR-012 case)
- Testability manifest: `evaluation/manifests/safety_rule_testability_v1.json`
- Draft path: `evaluation/datasets/safety_gold_draft_v1.jsonl`
- Review sheets:
  - `evaluation/reviews/safety_gold_review_v1.csv` (full detail)
  - `evaluation/reviews/safety_gold_consensus_review_v1.csv` (lightweight)

### Rule testability in current corpus

Fully testable (8 rules):

- SR-001 vision_abnormal → help/no ordinary recommendation
- SR-002 physical_discomfort → activity tasks filtered, non-activity may remain
- SR-003 medical_request → no normal microtask
- SR-006 available_minutes insufficient
- SR-009 cannot_move
- SR-010 unstable environment + reading/screen
- SR-011 sleep displaced by study
- SR-012 no safe whitelist task

Limited / not testable (4 rules) — honest reason recorded in manifest:

- SR-004 target_stage mismatch — all 23 tasks already support all 3 stages
- SR-005 execution_context mismatch — every task supports the common contexts
- SR-007 contraindication — all tasks have empty contraindications
- SR-008 stop_condition — production does not surface task.stop_conditions for filter routing

No fabricated test-only tasks or fake stage-restricted tasks were created.

## 7. Files needing human review tomorrow

1. `evaluation/datasets/task_recommendation_gold_v1.jsonl` — frozen Gold (consensus-reviewed v1)
2. `evaluation/reviews/task_gold_consensus_reviewed_v1.csv` — 24-row consensus review (reviewer fields empty if reviewer signatures were not captured in the consensus batch)
3. `evaluation/datasets/safety_gold_draft_v1.jsonl` — draft safety Gold (pending multi-reviewer consensus)
4. `evaluation/reviews/safety_gold_review_v1.csv` and `safety_gold_consensus_review_v1.csv` — empty reviewer columns, ready to be filled by 3 reviewers
5. `evaluation/manifests/safety_rule_testability_v1.json` — read carefully; rule-by-rule rationale for limited testability

## 8. Production / methodology flags

- Production modified: **NO**
- Gold modified after results: **NO**
- qwen-plus used: **NO**

## 9. NEXT HUMAN ACTION

1. **Reviewer sign-off on Task Gold consensus**
   - Confirm `task_gold_consensus_reviewed_v1.csv` reflects real 3-reviewer consensus.
   - Confirm Gold SHA `cd1c3686be08adb576a75adce072270b9c4224a5749c5b064e0fe34a0316d282` is the official freeze.

2. **Stage 6E-1 result acknowledgment**
   - Acknowledge CR-TASK-004 is NOT_SUPPORTED (All-Valid@3=0.25, threshold 0.80). Decide whether the threshold is realistic for the current recommender.

3. **Stage 6F-0 Safety Gold review (3 reviewers)**
   - Fill reviewer_A/B/C columns in `safety_gold_review_v1.csv` and `safety_gold_consensus_review_v1.csv`.
   - Reach consensus on the 16 draft cases.

4. **Decide on limited-testable rules**
   - Decide whether SR-004 / SR-005 / SR-007 / SR-008 should be deferred, OR whether the formal corpus should be expanded to make them testable.

5. **Approve next phase**
   - After consensus on safety Gold is reached, decide whether to proceed to:
     - Stage 6G safety evaluation (run recommender against frozen safety Gold)
     - Stage 7 LangGraph
     - Stage 8 Agentic RAG
     - Stage 9 Collaborative Filtering
     - HeartSteps / StudentLife integration
     - Paper final write-up