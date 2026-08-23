# Stage 6 Final Audit Summary (Stage 6F)

- Date: 2026-08-17
- Ticket: Stage 6F Final Audit & Safety Gold Revision
- Principle compliance: frozen Task Gold untouched; Stage 6E-1 run artifacts untouched; no metric tuning; no Stage 6E-1 re-run; no production code modified.

## Stage 6E — Task Recommendation

Source run (unmodified): `20260816T155009Z_task_recommendation_v1` — metrics independently recomputed from `per_case_results.jsonl`; all match.

| Metric | Value |
|---|---|
| Valid@1 | 23/24 = **0.9583** |
| Preferred@1 | 20/24 = **0.8333** |
| Invalid Recommendation Rate | 1/24 = **0.0417** |
| Valid@3 (macro) | **0.5347** |

Corrected All-Valid@3 diagnostics (audit `evaluation/audits/task_recommendation_metric_audit_v1.md`):

- Gold-set ceiling: 5/24 = **0.2083** (only 5 cases have >=3 valid gold tasks)
- Strict All-Valid@3 = **4/24 = 0.1667**; conditional (complete Top-3) = 4/21 = 0.1905
- Original runner value 0.25 was INVALID (counted short returns TRG-002/TRG-015 as success)
- Short Top-3 cases: TRG-002 (1), TRG-014 (2), TRG-015 (1)

Claims: CR-TASK-001 SUPPORTED, CR-TASK-002 SUPPORTED, CR-TASK-003 SUPPORTED,
CR-TASK-004 **NOT_SUPPORTED (unchanged)** — audit note added: metric has a Gold-set ceiling
(0.2083 < preregistered 0.80); do not use All-Valid@3 as a primary full-benchmark metric.
CR-TASK-REAL-001 UNSUPPORTED (by definition).

Invalid Top-1: TRG-004 only — negative constraint ("不想做额外活动") not modeled by
retrieval/rerank; MT-REC-002 outranked gold MT-BREAK-003/MT-BREAK-001. Diagnosed only; no tuning.

## Evidence

- Prior run `20260816T155329Z_evidence_contract_v1` (unmodified): Exact Match 23/23,
  Contamination 0, Missing 0 — these remain valid (measured `load_task_evidence` directly).
- Prior "3/3 fail-closed" fixtures reclassified: evaluator-internal array comparison,
  production decision point never invoked (scenario B) — NOT measured evidence.
- NEW real integration run `20260817T114145Z_evidence_fail_closed_integration_v1`:
  invokes actual `weilv.basic_rag._finalize_selected_task` with fake ES client;
  4/4 fail-closed fixtures PASS (missing ID / nonexistent ID / wrong review_status /
  wrong proposed_use) + positive control PASS; qwen-plus never called on fail-closed paths;
  model_call_counts = 0/0/0.
- **Production fail-closed verified: YES.**
- CR-EVID-001 SUPPORTED; **CR-EVID-002 SUPPORTED (now measured on the real production path)**;
  CR-EVID-REAL-001 UNSUPPORTED.
- Audit: `evaluation/audits/evidence_fail_closed_audit_v1.md`. No production gap.

## Output Guard

- v1 audit: run `20260816T155455Z_output_guard_v1` verified — 16 rows actually executed
  against production `validate_explanation_output` (runner imports it; per_case_results
  present). Reported Catch 1.00 / Leakage 0 / FP 0 stand.
- v2 contract: NEW dataset `evaluation/datasets/output_guard_contract_v2.jsonl` (24 cases:
  199/200/201-char boundaries, self-ID/title allowed, foreign ID/title blocked,
  evidence-supported vs unsupported quantities incl. decimal/space variants, plain
  explanation allowed, unsupported action blocked, multi-violation outputs, plus 3
  documented-semantics cases: lowercase task ID, empty output, partial foreign title).
- v2 run `20260817T114451Z_output_guard_v2` (against production guard, real 23 formal
  identities): **fixtures 24, Catch 1.00, Unsafe Leakage 0, False Positive 0 — PASS**.
  Hard contract (leakage = 0) satisfied. v1 run not overwritten.

## Safety Implementation & Testability (manifest v2, from-scratch re-audit)

Manifest: `evaluation/manifests/safety_rule_testability_v2.json` (v1 retained; v1 rationales
for SR-006/SR-009..SR-012 were template-corrupted and were NOT copied).

| Rule | Implemented | Testable | Basis |
|---|---|---|---|
| SR-001 vision abnormal -> help seeking | IMPLEMENTED | TESTABLE | input-level, exits before retrieval |
| SR-002 physical discomfort blocks activity | IMPLEMENTED | TESTABLE | domain filter; MT-REC/MT-OUT verified |
| SR-003 medical request -> blocked | IMPLEMENTED | TESTABLE | input-level |
| SR-004 stage mismatch | IMPLEMENTED | NOT TESTABLE | all 23 tasks list all 3 stages — mismatch unconstructible (corpus-verified) |
| SR-005 context mismatch | IMPLEMENTED | TESTABLE | v1 manifest WRONG; corpus contexts differ (MT-BREAK-004 school-only, MT-SED-002 home-only, ...) |
| SR-006 time insufficient | IMPLEMENTED | TESTABLE | durations 1-10 min |
| SR-007 contraindication | PARTIAL | NOT TESTABLE | rule branch exists; corpus contraindications ALL empty + no caller channel populates matched_contraindication_task_ids |
| SR-008 stop condition | PARTIAL | LIMITED | branch exists (safety_rules.py:83-84) but no producer for matched_stop_condition_task_ids (absent from BasicRagRequest/RecommendationRequest); corpus's only stop condition (vision abnormality, 14/23 tasks) is enforced upstream by SR-001 help_seeking which exits the whole flow — no reachable unsafe state; v0.1 design explicitly assigns matching to the caller |
| SR-009 cannot move | IMPLEMENTED | TESTABLE | capability filter verified |
| SR-010 unstable environment | IMPLEMENTED | TESTABLE | only MT-EYE-003 has pause capability; exercised in formal run TRG-015 |
| SR-011 sleep displaced | IMPLEMENTED | TESTABLE | 7 continue_study tasks |
| SR-012 no safe task | IMPLEMENTED | TESTABLE | deterministic constructible (outdoor + 1 min) |

SR-008 classification detail (ticket A/B/C): between A and B — the deterministic rule-layer
contract IS implemented per the v0.1 design ("caller supplies already-matched stop-condition
task IDs"); the orchestration layer provides no channel to supply them (B-layer wiring gap).
Because the only corpus stop condition is fully covered by the stronger SR-001 input rule,
this is a documented design scope boundary for v0.2 (add request channel or matcher), NOT a
P0/P1 production safety gap. No STOP triggered. Human review should ratify or challenge this
classification.

## Safety Gold v2

- Dataset: `evaluation/datasets/safety_gold_draft_v2.jsonl` — **20 cases**, blind-drafted
  (recommender outputs never consulted), corpus+rule-fact cross-checked.
- Coverage: every fully testable rule has >=1 trigger + 1 false-block control:
  SR-001 (2), SR-002 (2), SR-003 (2, control NEW), SR-005 (3, NEW), SR-006 (2),
  SR-009 (2), SR-010 (2), SR-011 (2), SR-012 (3, control NEW + combined stress case).
  SR-004/SR-007 excluded (not testable, no fabricated data); SR-008 excluded from gold
  (limited testability, unit-level only).
- v1 draft cases were re-evaluated, not copied: v1 errors found and fixed in v2
  (e.g. SAF-010 allowed home-only tasks in bedroom context; SAF-014 listed a 2-minute
  task as executable in 1 minute).
- Provenance: input=synthetic_constructed, gold=AI_assisted_draft_pending_project_review,
  review_status=pending_multi_reviewer_consensus.
- Review files: `evaluation/reviews/safety_gold_review_v2.csv` and
  `evaluation/reviews/safety_gold_consensus_review_v2.csv` — reviewer fields EMPTY,
  no consensus marked.
- Model calls for Safety Gold creation: embedding 0, reranker 0, qwen-plus 0.
- Safety recommendation evaluation NOT run (per ticket).

## Frozen artifact integrity

| Check | Expected | Result |
|---|---|---|
| Task Gold modified after freeze? | NO | NO — SHA re-verified `cd1c3686…1d282` |
| Task Corpus modified? | NO | NO — SHA re-verified `40d53d96…bb48` |
| Stage 6E formal run overwritten? | NO | NO — per_case_results intact, untouched |
| Evidence v1 / Guard v1 runs overwritten? | NO | NO — new runs created separately |
| Production code modified? | NO | NO — zero diffs under src/ |
| Gold leaked into recommender input? | NO | NO — audit-only reads; no re-run performed |

## Final verdict

**STAGE6_READY_FOR_SAFETY_HUMAN_REVIEW**

No STOP condition was triggered: evidence path fails closed (measured on the real production
path), guard v2 leakage = 0, and the SR-007/SR-008 PARTIAL findings are corpus/design-scope
limitations with no reachable unsafe state (SR-001 covers the only corpus stop condition) —
documented for v0.2, flagged for human ratification rather than auto-fixed.

## Next human actions

1. Three-reviewer consensus on `safety_gold_draft_v2.jsonl` (fill review CSVs; do not mark
   consensus until all three reviewers sign off).
2. Ratify or challenge the SR-007/SR-008 PARTIAL classification and the SR-004
   not-testable finding.
3. Decide v0.2 scope: request-schema channel (or matcher) for matched_stop_condition_task_ids /
   matched_contraindication_task_ids; stage-restricted and contraindication-carrying corpus
   tasks if those rules must become measurable.
4. After gold freeze: run Safety recommendation evaluation (not started, per ticket).
