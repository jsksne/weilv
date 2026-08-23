# Stage 6 Frozen (Stage 6G — Safety Gold Freeze + Formal Safety Evaluation)

- Date: 2026-08-17
- Ticket: 微律 Stage 6G — Safety Gold Freeze + Formal Safety Evaluation
- Recommended model (per ticket header): MiniMax M3
- Source run: `evaluation/runs/20260817T124015Z_safety_v1/`

## Stage 6 closure

| Subsystem | Status |
|---|---|
| Personal RAG | PASS / FROZEN |
| Knowledge Retrieval | PASS / FROZEN |
| Task Recommendation | PASS / FROZEN |
| Evidence Grounding | PASS / FROZEN |
| Output Guard | PASS / FROZEN |
| Safety Evaluation | PASS / FROZEN |

## Safety Gold v1

- Dataset: `evaluation/datasets/safety_gold_v1.jsonl`
- Cases: 20 (consensus_reviewed, 3 reviewers, AGREE / AGREE / AGREE / CONSENSUS_REACHED)
- SHA-256: `aa975d5cd58deec5c837b1ca2b5e4723229fd71c08c64df85ba39d8819372e7f`
- Manifest: `evaluation/manifests/safety_gold_v1_manifest.json`
- Provenance: `input_provenance = synthetic_constructed`,
  `gold_provenance = author_and_multi_reviewer_consensus`
- Task corpus SHA-256 (canonical sorted-JSONL form per
  `evaluation/manifests/task_gold_task_corpus_v1.json`): `40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48`

## Formal Safety Evaluation — headline metrics

| Metric | Value |
|---|---|
| Cases executed | 20 / 20 |
| Safety Decision Accuracy | 20/20 = **1.0000** |
| Trigger assertions | 27 |
| Unsafe Escape Count | **0** |
| Unsafe Escape Rate | **0.0000** (HARD REQUIREMENT MET) |
| Control assertions | 33 |
| False Block Count | 0 |
| False Block Rate | 0.0000 |
| Evaluator failures | 0 |
| Gold fields leaked to production | NO |

### Per-rule results

| Rule | Cases | Assertions | Correct | Unsafe Escape | False Block | Accuracy |
|---|---|---|---|---|---|---|
| SR-001 | 2 | 4 | 4 | 0 | 0 | 1.0000 |
| SR-002 | 2 | 7 | 7 | 0 | 0 | 1.0000 |
| SR-003 | 2 | 4 | 4 | 0 | 0 | 1.0000 |
| SR-005 | 3 | 6 | 6 | 0 | 0 | 1.0000 |
| SR-006 | 3 | 13 | 13 | 0 | 0 | 1.0000 |
| SR-009 | 2 | 7 | 7 | 0 | 0 | 1.0000 |
| SR-010 | 3 | 10 | 10 | 0 | 0 | 1.0000 |
| SR-011 | 2 | 7 | 7 | 0 | 0 | 1.0000 |
| SR-012 | 3 | 8 | 8 | 0 | 0 | 1.0000 |

## Integrity

| Check | Expected | Result |
|---|---|---|
| Frozen Gold SHA-256 | `aa975d5…2e7f` | `aa975d5…2e7f` (unchanged) |
| Task corpus SHA-256 | `40d53d96…bb48` | `40d53d96…bb48` (unchanged) |
| Production safety_rules.py modified | NO | NO |
| Production safety_rules_v0.1.json modified | NO | NO |
| Gold fields leaked to production | NO | NO (per_case leak_check, all cases clean) |
| Safety recommendation results seen before freeze | NO | NO (gold frozen before any run; SHA pinned) |
| Model calls during evaluation | embedding/reranker/qwen_plus = 0 | 0 / 0 / 0 |

## Claims

- `CR-SAFE-001` — Unsafe Escape Rate = 0: **SUPPORTED**
- `CR-SAFE-002` — Safety Decision Accuracy: **Measured (descriptive)** = 1.0000
- `CR-SAFE-003` — False Block Rate: **Measured (descriptive)** = 0.0000
- `CR-SAFE-REAL-001` — Offline synthetic Safety proves real-world safety:
  **UNSUPPORTED** (offline synthetic benchmark does not measure real outcomes)

## Documented limitations (NOT blocking Stage 7)

1. **CR-TASK-004 — All-Valid@3 remains NOT_SUPPORTED.**
   - Strict All-Valid@3 = 4 / 24 = **0.1667**
   - Gold theoretical ceiling = 5 / 24 = **0.2083**
   - Therefore All-Valid@3 is not used as a primary full-benchmark metric.
2. **SR-004 implemented but not testable with current task corpus:**
   - All 23 formal tasks list all 3 stages, so a stage-mismatch case cannot be
     constructed without fabricating stage-restricted tasks. Rule is
     implemented and wired (ES + rule layer); corpus just lacks the case shape.
3. **SR-007 PARTIAL — contraindications:**
   - Formal corpus contraindications are empty across all 23 tasks.
   - No production caller channel populates `matched_contraindication_task_ids`
     (absent from `BasicRagRequest` and `RecommendationRequest`).
   - Rule branch exists; testability deferred to v0.2 (add request channel).
4. **SR-008 PARTIAL / LIMITED — stop conditions:**
   - `matched_stop_condition_task_ids` orchestration matcher deferred to v0.2.
   - Current corpus's only stop condition (vision abnormality signs, 14 / 23
     tasks) is covered upstream by SR-001 (input-level `help_seeking` exits
     the whole flow before task selection), so there is no reachable unsafe
     state in the live pipeline.

These are documented v0.2-scope boundaries and do not block Stage 7.

## Verdict

```
STAGE6_STATUS = FROZEN
STAGE7_STATUS = UNLOCKED
```

No production code was modified, no prior Stage 6 run was overwritten, and
no metric thresholds were tuned after seeing results. The runner
(`evaluation/runners/run_safety_gold_evaluation.py`) directly imports
`weilv.safety_rules.{evaluate_input_risk, filter_task_by_safety, select_safe_tasks}`
from `src/weilv/safety_rules.py` against the actual formal task corpus;
no parallel Safety Rule implementation lives in the evaluator.

STOP. Do NOT start LangGraph. Do NOT start Stage 7 code from this ticket.