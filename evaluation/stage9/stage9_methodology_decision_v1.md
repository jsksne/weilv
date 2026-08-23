# Stage 9A methodology decision v1

Status: **FROZEN FOR METHODOLOGY AUDIT; NO FORMAL RESULT**  
Date: 2026-08-18

## Decision gate

1. Is HeartSteps appropriate for Stage 9? **PARTIAL**.
2. Can HeartSteps directly validate all 23 微律 tasks? **NO**. It directly validates none of the exact tasks.
3. What can it validate? Whether cross-user, context-conditioned behavioral histories improve action ranking/prediction over a non-neighbor baseline within HeartSteps' own three-action space: no suggestion, walking suggestion, antisedentary suggestion.
4. Selected design: **DESIGN C — EXTERNAL MECHANISM VALIDATION**.
5. Is a separate 微律 real-user pilot required for product-level CF validation? **YES**.
6. Allowed claim: real adult longitudinal mHealth data were used to test collaborative signal within the external dataset's supported action space. No youth, health-effectiveness, eye-health, sleep, or 23-task effectiveness claim is allowed.
7. Stage 9B boundary: implement the frozen external evaluation and a neutral-by-default product CF ranking interface with invariance/safety tests. Do not import HeartSteps parameters as 微律 task preferences and do not run a product-effect claim without a real 微律 pilot.

## Why Designs A and B are not selected

### Design A — direct 23-task CF: REJECTED

No audited public dataset contains repeated interactions with semantically equivalent versions of 微律's 23 reviewed tasks. HeartSteps has two suggestion archetypes plus no suggestion, uses adults, and measures short-term steps. Treating its contextual message strings as 微律 items would manufacture item identity. Direct task-level transfer is scientifically invalid.

### Design B — domain/action-archetype CF: NOT THE OFFICIAL EVALUATION DESIGN

HeartSteps has coarse semantic overlap with antisedentary/movement concepts. Five 微律 tasks are marked `COARSE_DOMAIN_ONLY` in the mapping matrix. This is useful for defining an interface, but it cannot validate their exact trigger, duration, school/youth context, evidence, or outcome. Importing adult HeartSteps affinities into those product tasks would add domain-shift risk without product evidence. Design B is retained only as a semantic boundary, not as a Stage 9 formal effectiveness test.

### Design C — selected

Design C cleanly separates three evidence levels:

- public HeartSteps measured records: real external human data;
- HeartSteps-to-微律 compatibility labels: human-designed semantic mapping;
- synthetic adapter/invariance tests: engineering evidence only.

It has the lowest overclaiming risk and gives Stage 9B a falsifiable external question while preserving the frozen product architecture.

## Research question and estimand

External primary question:

> Among temporally held-out HeartSteps decision points for a held-out participant with seven days of prior personal history, does adding a cross-user neighborhood residual improve participant-balanced off-policy action value relative to the frozen context + personal-history policy?

This is a behavioral action-ranking estimand in HeartSteps, not a causal estimate for 微律 and not a latent "health preference".

## Interaction and signal definition

### Decision opportunity

A Stage 9B primary row must:

1. come from the pinned HeartSteps commit and `suggestions.csv` hash;
2. have nonmissing `user.index`, `decision.index`, `sugg.decision.utime`, `sugg.decision.slot`, `is.randomized`, `send`, `send.active`, and `send.sedentary`;
3. have `avail == True` and decision slot in 1–5;
4. encode exactly one consistent action:
   - `none`: `send=False`, active=False, sedentary=False;
   - `walking`: `send=True`, active=True, sedentary=False;
   - `antisedentary`: `send=True`, active=False, sedentary=True;
5. lie in derived study days 1–42, ordered within participant without duplicate `(user.index, decision.index)`;
6. have a measured, non-imputed `jbsteps30` primary outcome.

Any row failing action consistency is excluded and counted. Stage 9B must emit a flow table from 8,274 raw rows to the final cohort and explicitly compare it with, but not claim identity to, the paper's 7,540 included and 6,061 available decision points.

### Exposure, acceptance, completion, outcome

- Exposure: the action actually encoded by `send` + action flags.
- Acceptance/explicit reaction: `response in {good,bad}` only, used as a secondary acceptability endpoint.
- `no_response`, snooze, or blank: not positive and not negative preference.
- Completion: not observed; HeartSteps does not provide a 微律-style task-completion field.
- Behavioral outcome: `y = log1p(jbsteps30)` in the 30 minutes after the decision.
- Prior behavior: `jbsteps30pre`, bucketed as missing / 0 / 1–199 / >=200 using only prediction-time data.
- `.zero` fields: sensitivity analysis only.
- Google Fit outcome: sensor sensitivity analysis only.

Notification delivery is never labeled as positive feedback. Step response is a proximal behavioral outcome under randomized exposure; it is not renamed "preference" and does not prove health benefit.

### External collaborative signal

The frozen external method is an explainable, context-aware user-neighborhood residual model.

1. Actions are the three archetypes above, not 258 message strings.
2. Context uses only released prediction-time fields: decision slot; recognized activity collapsed to `STILL`/`ON_FOOT`/`IN_VEHICLE`/other/unknown; location collapsed to home/work/other/unknown; weather collapsed to precipitation-or-snow/other/unknown; prior-30-minute step bucket; and study week.
3. A training-only additive smoothed context mean gives `base_score(a,c)`. Each categorical adjustment uses fixed shrinkage `n/(n+10)` around the action mean.
4. The target user's prior residual mean supplies `personal_signal(u,a,slot)` with fallback to prior action residual, then overall prior residual; the same fixed shrinkage is used.
5. A user's neighbor vector contains prior residual means for action x slot cells. Similarity is cosine similarity on co-observed cells, shrunk by `n_common/(n_common+10)`. Only positive similarities with at least three co-observed cells qualify.
6. Use at most five neighbors and require at least three contributors for the requested action x slot cell; otherwise the collaborative signal is zero.
7. `cf_signal(u,a,c,t)` is the shrinkage-weighted mean of qualifying neighbors' pre-`t` residuals for the same action x slot cell, clipped to the source-training 5th/95th residual percentiles.
8. `hybrid_score = base_score + personal_signal + cf_signal`. The comparator is `personal_score = base_score + personal_signal`.

All constants are preregistered. No alpha is tuned on outer-test results.

## Why not classical matrix factorization

The stable item cardinality is three actions (or 15 action x decision-slot cells), not 258 independent items. With 37 participants, user-item matrix factorization, BPR, implicit ALS, and LightFM are weakly identified and add complexity without semantic gain. Item-kNN is similarly uninformative with two intervention types. User-kNN on context-conditioned residual profiles is the smallest method that actually represents the intended cross-user mechanism.

## Context-aware rather than plain CF

Plain CF is rejected. HeartSteps interventions were deliberately tailored and delivered at context-specific decision points; availability, recent activity, time, location, and weather affect both delivery and post-decision steps. Ignoring context would let baseline activity and opportunity masquerade as collaboration. Only fields in the released data dictionary are allowed; post-response fields are excluded from predictors.

## Leakage-free split

### Outer evaluation: leave-one-participant-out

- Repeat for each of the 37 public users.
- The held-out participant contributes no rows to source-user model fitting or neighbor construction.
- Target study days 1–7 are adaptation history only.
- Target days 8—2 are evaluation decisions.
- For a prediction at relative time `t`, target history must be strictly earlier than `t`. Source-user histories are censored to source relative study time strictly earlier than `t`; no future interaction is used.
- Context-bucket statistics, residual clipping thresholds, and all fallbacks are computed within the outer training users only.
- No random row split is permitted.

This evaluates warm-start collaborative increment beyond target personal history while keeping target identity out of training. A secondary cold-start report covers days 1–7 with `cf_signal=0` until the minimum history/neighbor conditions are met; cold start is a fallback audit, not an improvement claim.

## Frozen baselines

1. `GLOBAL_ACTION`: source-training participant-balanced mean by action.
2. `CONTEXT_ONLY`: frozen additive context score; no target personal history and no neighbors.
3. `PERSONAL_ONLY` (primary comparator): context score plus target's strictly prior residual history; no user-neighborhood term.
4. `CF_ONLY`: context score plus cross-user neighborhood residual; reported descriptively.
5. `PERSONAL_PLUS_CF` (primary method): primary comparator plus `cf_signal`.

The primary comparison is 5 versus 3. This directly isolates the neighbor contribution.

## Metric and statistics freeze

### Primary metric

Participant-balanced incremental self-normalized inverse-propensity-weighted (SNIPS) policy value:

`Delta_V = mean_user[V_SNIPS(PERSONAL_PLUS_CF) - V_SNIPS(PERSONAL_ONLY)]`

where outcome is `log1p(jbsteps30)`, the policy selects the top-scored action, and known trial assignment probabilities are 0.4 none, 0.3 walking, 0.3 antisedentary. Deterministic external score ties resolve `none`, then `antisedentary`, then `walking` to avoid manufacturing an intervention preference.

SNIPS is chosen because the question is action ranking and only the randomized action's outcome is observed. Precision@K is not meaningful with two intervention categories, and RMSE is not the primary ranking metric.

### Secondary metrics

- participant-balanced MAE of `log1p(jbsteps30)` for observed actions;
- participant-balanced action-selection coverage and neighbor coverage;
- participant-balanced explicit `good` vs `bad` AUC or balanced accuracy only where both labels exist; `no_response` is excluded;
- cold-start fallback rate;
- sensitivity using Google Fit and separately the documented `.zero` imputation fields;
- descriptive action-frequency and effective sample-size diagnostics for SNIPS.

### Inference

- Participant is the independent unit.
- Compute each user's paired difference first.
- Bootstrap participants with replacement, 10,000 replicates, seed `20260818`; percentile 95% CI.
- Do not report row-level p-values treating decision points as independent people.
- Report all 37 participant contributions, missingness, neighbor coverage, and the small-N limitation.

### CR-CF-001 support criterion

`SUPPORTED` only if `Delta_V > 0`, the participant-bootstrap 95% CI lower bound is `> 0`, both policies have positive effective sample size for every included participant, and no preregistered data-integrity gate fails. Otherwise `UNSUPPORTED` or `NOT_EVALUABLE` with the failing reason. No result is computed in Stage 9A.

## Product integration freeze

The product does not ingest HeartSteps task scores. Future 微律 real-user interactions may produce a separate normalized `cf_signal(task) in [-1,1]`.

Pipeline:

`input safety -> retrieval -> metadata/safety filtering -> Personal/Agentic candidate ranking -> CF tie-break -> final selection -> evidence -> explanation -> Output Guard`

The product mechanism is an exact-tie break only:

1. Preserve the frozen Personal RAG `personalization_delta` and `adjusted_rank` unchanged.
2. Group candidates by identical `adjusted_rank`.
3. Within a tie only, sort by descending `cf_signal`; then preserve existing `base_task_rank`, then `task_id`.
4. If there is no exact tie, CF cannot change the order.
5. Before/after task-ID multisets and cardinality must be identical or recommendation fails closed to the pre-CF order with an audit violation.

No alpha is used. CF is neutral when data, context, domain support, or neighbors are insufficient.

## Cold start and privacy

- New user / no memory / fewer than 10 eligible structured interactions: neutral.
- Fewer than three qualifying neighbors or unsupported task/domain: neutral.
- Unknown context: use context-agnostic aggregate only if the same real 微律 task has sufficient aggregate data; otherwise neutral.
- CF failure never blocks recommendation; use the unchanged Personal/Agentic order.
- Store only anonymous internal user key, formal task ID/domain, structured event/outcome, timestamp/context bucket, consent/provenance, and model/data version.
- Do not store or expose raw chat, another user's memory/query/identity/health text, or raw neighbor records. Runtime diagnostics expose only counts, bounded scores, and version IDs.

## Claim boundary

Allowed wording:

> A real-world longitudinal adult mHealth dataset was used to evaluate whether cross-user behavioral signals add useful action-ranking information within the external dataset's walking and antisedentary action space. Product integration remains limited to reviewed 微律 tasks and is subordinate to Safety, evidence, and Output Guard.

Forbidden wording includes: adolescent effectiveness; 微律 health outcomes; eye-health or sleep validation; all-23-task validation; clinical safety; or direct transfer of adult HeartSteps response as youth preference.

## Stage 9A no-code gate

- Project runtime model calls: 0.
- Production CF code: 0.
- Production behavior changes: 0.
- Formal Stage 9 results: 0.
- Status after artifact validation: `READY_FOR_METHODOLOGY_AUDIT`.
