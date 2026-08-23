# Stage 9 CF safety integration contract v1

## Frozen position in the pipeline

`input safety -> retrieval -> metadata/safety filtering -> Personal/Agentic ranking -> CF tie-break -> final selection -> evidence -> explanation -> Output Guard`

CF executes only when the upstream status is `allowed` and only over the already safety-approved ranking.

## Absolute invariants

For every request:

1. `candidate_set_before_cf == candidate_set_after_cf` as an ordered-independent multiset of task IDs.
2. Candidate cardinality is unchanged.
3. CF cannot add, invent, substitute, or resurrect a task.
4. CF cannot change task instruction, duration, domain, evidence IDs, contraindications, stop conditions, or safety metadata.
5. CF cannot override input safety, context/applicability filtering, terminal help-seeking/blocked/no-safe-task behavior, evidence fail-closed behavior, or Output Guard.
6. A CF exception, missing model, stale version, unknown context, unsupported domain, insufficient history, or insufficient neighbors returns the exact pre-CF order.
7. HeartSteps-derived scores are never used as product task scores.

Required formal counters:

- CF blocked-task resurrection: 0.
- CF candidate-set expansion: 0.
- Unsafe Escape: 0.
- Evidence Contamination: 0.
- CF task-mutation count: 0.

## Ranking rule

CF is an exact-tie break after frozen Personal RAG ranking:

- primary key: existing `personalization.adjusted_rank` (unchanged);
- secondary key within an exact tie: descending bounded `cf_signal`;
- tertiary keys: existing `base_task_rank`, then `task_id`.

No exact tie means no order change. CF cannot compensate for or negate a Personal RAG delta. No alpha or unconstrained weighted sum is permitted.

## Runtime preconditions and fallback

Apply a nonzero product `cf_signal` only when all are true:

- explicit CF consent and anonymous internal user key are present;
- at least 10 eligible structured interactions exist for the target user;
- at least three qualifying aggregate neighbors contribute;
- the formal task ID is supported by the product CF model version;
- context bucket and model/data version are known and current;
- score is finite and in `[-1,1]`.

Otherwise set the task signal to zero. CF absence never blocks a recommendation.

## Evidence and Output Guard

After CF selection, use the selected formal task's unchanged `evidence_chunk_ids`. The existing exact evidence-ID equality check remains mandatory. The LLM still explains only the selected frozen task; CF never supplies free text to the explanation prompt. Existing Output Guard validates the final explanation and uses the existing safe fallback on rejection.

## Required diagnostics

Record without raw user/neighbor data:

- `cf_applied`;
- `cf_fallback_reason`;
- `cf_signal_by_task` (bounded aggregate only);
- `cf_neighbor_count_by_task`;
- `candidate_task_ids_before_cf`;
- `candidate_task_ids_after_cf`;
- `cf_model_version` and `cf_data_version`;
- invariant pass/fail flags;
- selected task ID before/after tie-break.

Any invariant failure must be visible in audit output and return the pre-CF order.

## Safety test matrix for Stage 9B

1. Non-allowed upstream states (`help_seeking`, `blocked`, `no_safe_task`) never call CF.
2. A blocked task with maximal forged CF score is not present after CF.
3. CF provider returning an extra task, duplicate task, NaN, infinity, or out-of-range score fails closed.
4. Empty/missing/corrupt CF artifact preserves pre-CF order.
5. Unsupported sleep/eye/outdoor domain returns neutral unless a later real 微律 model explicitly supports the exact task.
6. Selected evidence IDs remain exact after any permitted tie reorder.
7. Guard rejection behavior is identical with CF on/off.
8. Diagnostics contain no raw chat, memory, identity, health free text, or neighbor identifiers.

## Claim criteria

- CR-CF-002 is supported iff candidate expansion = 0 and blocked-task resurrection = 0 across all Stage 9B contract tests/formal product-compatible cases.
- CR-CF-003 is supported iff Unsafe Escape = 0, Evidence Contamination = 0, Output Guard contract violations = 0, task mutation = 0, and all non-allowed terminal states bypass CF.
