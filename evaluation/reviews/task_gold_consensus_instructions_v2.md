# Task Gold v2 — Multi-reviewer Consensus Instructions

**Scope:** 24 cases (TRG-001 … TRG-024) over 23 formal MicroTasks (`micro_tasks_v1`, frozen corpus SHA-256 = `40d53d96a89124f387d65dea3e97bbeb8da878ef1e9ccd2fbc971cd08096bb48`).

**Purpose:** lightweight independent review of the AI-drafted v2 gold labels before any Task Recommendation Experiment is executed. Each reviewer reads only the user scenario and the draft Preferred / Acceptable task lists (plus task titles), then chooses AGREE or CHANGE per case.

## Reviewer Workflow

For each case row in `task_gold_consensus_review_v2.csv`:

1. Read the `query` exactly as written (do **not** paraphrase, do **not** read the v1 draft query).
2. Read `current_context`, `activity_context`, `available_minutes`, `query_style`.
3. Inspect the drafted `preferred_task_titles` and `acceptable_task_titles`.
4. Open the frozen MicroTask metadata only if you need to confirm a trigger / execution_context / safety_capability.
5. Decide **AGREE** or **CHANGE** for this case.
6. If **CHANGE**:
   - Add notes specifying which task should be added / removed / moved between Preferred and Acceptable, and why.
   - You do **not** need to audit the full invalid set unless you believe a task was mis-labelled.

## Reviewer Fields (per row)

| Field | Meaning |
| --- | --- |
| `reviewer_A_decision` | `AGREE` or `CHANGE` |
| `reviewer_A_notes` | Free-text justification (required if CHANGE; optional if AGREE) |
| `reviewer_B_decision` | same |
| `reviewer_B_notes` | same |
| `reviewer_C_decision` | same |
| `reviewer_C_notes` | same |

## Consensus Rules

- `consensus_status` = `CONSENSUS_REACHED` **only** when all three reviewers chose `AGREE` for that case.
- If any reviewer chooses `CHANGE`, the case must go through one revision round before `CONSENSUS_REACHED` is allowed.
- `consensus_status` values permitted: empty string, `CONSENSUS_REACHED`, `NEEDS_REVISION`.
- `consensus_notes` is filled by the moderator after all three reviewers complete their pass.

## Strict Prohibitions

- Reviewers **must not** consult `task_gold_review_v2.csv` (the 552-row audit matrix) while filling this sheet; the 552-row matrix exists for the audit-only pass after consensus.
- Reviewers **must not** look at any Task Recommendation ranking output, BM25/Vector/Hybrid/qwen3-rerank result, LangGraph/Agentic RAG output, qwen-plus output, or Personal RAG ranking.
- Reviewers **must not** auto-fill `agree`, `approved`, `consensus`, or `all reviewers agree`. These terms only appear in the sheet after real human review.
- Reviewers **must not** mark `CONSENSUS_REACHED` until they have actually finished their own row and seen all three reviewer decisions for that case.

## What "AGREE" Means

The reviewer believes:

- The Preferred set correctly solves the user's current need with the lowest-burden task(s) that pass all hard constraints.
- The Acceptable set contains only tasks that genuinely fit the same need, possibly with slightly more burden or generality.
- No task that should be Preferred or Acceptable was incorrectly pushed into Invalid.

## What "CHANGE" Means

At least one of:

- A task is missing from Preferred / Acceptable that should be there.
- A task is in Preferred / Acceptable that should be Invalid.
- The Preferred / Acceptable split does not reflect the user's expressed constraint or preference.

## Files Referenced

- `evaluation/datasets/task_recommendation_gold_draft_v2.jsonl` — full draft with rationale per case.
- `evaluation/reviews/task_gold_case_summary_v2.csv` — per-case counts (Preferred / Acceptable / Invalid).
- `evaluation/reviews/task_gold_consensus_review_v2.csv` — the sheet to fill.
- `evaluation/reviews/task_gold_review_v2.csv` — 552-row audit matrix; **not** consulted during this pass.
- `data/metadata/micro_tasks_v1.jsonl` — frozen formal MicroTask metadata; **only** consulted for trigger / execution_context / safety_capability verification.