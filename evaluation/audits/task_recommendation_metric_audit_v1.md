# Task Recommendation Metric Audit v1

- Audited run: `20260816T155009Z_task_recommendation_v1` (read-only; not modified, not re-run)
- Frozen Gold SHA-256: `cd1c3686be08adb576a75adce072270b9c4224a5749c5b064e0fe34a0316d282`
- Task Corpus SHA-256: `40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48`
- Audit date: 2026-08-17
- Method: independent recomputation from `per_case_results.jsonl` (24 cases) and gold labels.

## A1. Recomputed headline metrics

| Metric | Recomputed | Prior report | Match |
|---|---|---|---|
| Valid@1 | 23/24 = 0.958333 | 0.958333 | YES |
| Invalid Recommendation Rate | 1/24 = 0.041667 | 0.041667 | YES |
| Preferred@1 | 20/24 = 0.833333 | 0.833333 | YES |
| Valid@3 (macro over cases) | 12.833333/24 = 0.534722 | ~0.5347 | YES |

No material discrepancy. Headline metrics stand.

## A2. All-Valid@3 methodology audit (correction)

Metric contract: All-Valid@3 requires ALL returned Top-3 tasks to be valid; if fewer than 3
tasks are returned the case is NOT a success. The original runner counted short returns
(1 or 2 tasks, all valid) as success — methodology error.

Recomputed per-case `gold_valid_count` = len(preferred + acceptable):

- 16 cases with 1 valid task
- 3 cases with 2 valid tasks (TRG-004, TRG-010, TRG-018)
- 5 cases with >=3 valid tasks (TRG-001: 5, TRG-006: 6, TRG-007: 5, TRG-012: 4, TRG-024: 5)

Diagnostics:

- `gold_valid_count >= 3` cases: 5 / 24
- Theoretical maximum All-Valid@3 (strict, all cases): **5/24 = 0.208333**
  (conditional on complete Top-3: 5/21 = 0.238095)
- `complete_top3_case_count` (returned >= 3): **21**
- `short_top3_case_count`: **3** — TRG-002 (returned 1), TRG-014 (returned 2), TRG-015 (returned 1)
- `strict_all_valid_top3_success_count`: **4** — TRG-006, TRG-007, TRG-012, TRG-024
  (each returned 3 tasks, all in preferred ∪ acceptable)

Corrected results:

- Strict All-Valid@3 (all cases) = **4/24 = 0.166667**
- Conditional All-Valid@3 (complete Top-3 cases) = **4/21 = 0.190476**
- Original runner value 6/24 = 0.25 is INVALID (counted short returns TRG-002/TRG-015 as success)

Achieved 4 of a possible 5 (ceiling 0.2083 strict); the one missed ceiling case is TRG-001
(gold has 5 valid tasks but Top-3 included MT-OUT-001, invalid for that case).

## A3. CR-TASK-004 claim handling

CR-TASK-004 preregistered `All-Valid@3 >= 0.80`.

- Threshold NOT changed. NOT relabeled.
- Status remains: **NOT_SUPPORTED**.
- Audit note (added, history not rewritten): post-run methodology audit found the metric has
  a Gold-set ceiling of 5/24 = 0.2083 because 19 of 24 cases contain fewer than three valid
  tasks. Therefore CR-TASK-004 remains NOT_SUPPORTED, and All-Valid@3 should not be used as
  a primary full-benchmark metric in later paper interpretation. The 0.80 threshold was
  preregistered against an unreachable bar — an evaluation-design defect, not a recommender
  performance result.

## A4. Invalid Top-1 diagnosis (TRG-004)

- query: 「在家连续读了四十分钟，现在有十分钟。我今天不想做额外活动，只想安静休息一下，怎么安排比较合适？」
  (query_style: constraint_or_preference)
- Gold: preferred = MT-BREAK-003; acceptable = MT-BREAK-001
- System Top-1: **MT-REC-002** (label: invalid); ranked order:
  MT-REC-002 > MT-REC-001 > MT-OUT-001 > MT-BREAK-001(4th) > MT-BREAK-003(5th)
- Safety status: allowed; no safety rule matched (safety_flags all false) — this is a
  preference-constraint ranking miss, not a safety failure.
- Likely cause: the query states a NEGATIVE constraint ("不想做额外活动") plus a positive
  one ("只想安静休息"). BM25/embedding/rerank match surface semantics — MT-REC-002's
  retrieval text (recovery/rest-adjacent vocabulary) overlaps "休息/恢复" tokens strongly,
  while the negative constraint is not modeled anywhere in retrieval or rerank. Both gold
  tasks (break-style quiet rest) ranked below three recovery/outdoor tasks.
- Action per ticket: recorded only. Recommender NOT tuned.

## Integrity

- Frozen artifacts unmodified (byte hashes re-verified during audit).
- This audit adds new artifacts only; it does not alter the run, gold, corpus, or any claim registry retroactively.
