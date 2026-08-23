# Stage 9B implementation contract v1

Stage 9B is not started by this ticket. This document is the complete allowed boundary.

## Minimal file plan

| File | Responsibility |
|---|---|
| `evaluation/stage9/preprocess_heartsteps_v1.py` | download/verify pinned files, enforce schema and row-flow audit, emit analysis table without committing raw data |
| `evaluation/stage9/run_stage9_external_cf.py` | LOPO temporal evaluation, frozen baselines/model/metrics/bootstrap, immutable run artifacts |
| `src/weilv/collaborative_ranking.py` | pure, side-effect-free exact-tie product reorder and neutral fallback |
| `tests/test_collaborative_ranking.py` | smallest complete invariance/safety/fallback contract suite |

No new service, database, model dependency, matrix-factorization package, or public API endpoint is authorized. Reuse Python standard library and already-installed numerical/data libraries only if present.

## External preprocessing

Inputs are the six pinned HeartSteps files/metadata in `stage9_data_source_audit_v1.md`. The preprocessor must:

1. download to a temporary/cache directory outside versioned artifacts;
2. verify repository commit, byte length, SHA-256, column names, row counts, and 37 unique users before analysis;
3. create the deterministic eligible cohort defined in `stage9_methodology_decision_v1.md`;
4. derive action, relative study day/week, frozen context buckets, outcome, and missingness flags;
5. never interpret blank/`no_response` as negative and never use post-response fields as prediction features;
6. emit a JSON row-flow manifest with every exclusion reason and per-user counts;
7. block the run on hash/schema mismatch, duplicate `(user, decision)` keys, action inconsistency after filtering, or future-time ordering violations.

Raw external data must not be added to the acceptance bundle or production indices.

## External training/evaluation

Implement exactly:

- 37-fold leave-one-participant-out evaluation;
- days 1–7 target adaptation, days 8—2 test;
- strict pre-prediction temporal censoring for target and source histories;
- frozen additive context means, personal residual, user-neighbor residual, `k<=5`, minimum three neighbors, and shrinkage denominator 10;
- frozen baselines and deterministic tie order;
- participant-balanced SNIPS primary metric;
- participant-level paired bootstrap, 10,000 replicates, seed 20260818;
- all secondary/sensitivity metrics labeled secondary.

Do not tune against outer test users. Any implementation choice not fully specified must be decided and versioned before the first formal run, using source-training data only, then added as a preregistration amendment rather than silently changed.

## Product interaction schema

Reuse `interaction_logs_v1` or an equivalent existing structured store. Minimum fields:

| Field | Rule |
|---|---|
| `anonymous_user_key` | internal pseudonymous key; never returned as neighbor identity |
| `task_id` / `domain` | exact reviewed formal identifiers |
| `event_type` | one of exposed, accepted, started, completed, partially_completed, replaced, skipped |
| `structured_outcome` | enum/numeric value derived from explicit UI event; no inferred free-text sentiment |
| `event_timestamp` | UTC plus approved coarse time bucket |
| `context_bucket` | minimum necessary structured bucket; no raw query/location text |
| `consent_scope` | proves CF use is allowed |
| `source_version` | task corpus, schema, and interaction version |

Do not store raw chat, raw memory text, health free text, GPS, another user's identifier, or neighbor explanations for CF.

## Product training and inference

Stage 9B product code may expose a provider interface returning, for candidate IDs only:

`{task_id: {cf_signal: float[-1,1], neighbor_count: int, model_version: str}}`

Until a separately approved real 微律 pilot produces sufficient consented interactions, the production provider must return neutral scores. HeartSteps-trained scores/embeddings/parameters cannot populate this interface.

`apply_cf_tiebreak(tasks, signals)` must be pure and must:

1. copy no task content and mutate no task;
2. reject unknown/duplicate IDs and nonfinite/out-of-range scores;
3. preserve the exact candidate multiset/cardinality;
4. reorder only exact `adjusted_rank` ties;
5. return the original order plus a reason on any failure.

Integration points after implementation review:

- `run_personal_rag`: after `personalize_task_candidates`, before `_selected_task`;
- Agentic runtime: after `apply_personalization`, before `select_and_ground`;
- Basic RAG remains unchanged.

No request/response API change is required. Additive diagnostics may be internal or optional; selected task, evidence, explanation, and guard schemas remain compatible.

## Required Stage 9B tests

- unit tests for tie/no-tie ordering, neutral behavior, invalid signals, candidate expansion/duplication, and deterministic ordering;
- integration tests for Personal and Agentic paths with the existing Safety, exact evidence check, and Output Guard;
- forged maximal-score blocked-task resurrection test;
- no-data/new-user/unknown-context/unsupported-domain/corrupt-model fallback tests;
- privacy test asserting diagnostics contain only aggregate fields;
- external evaluator leakage tests proving no held-out user in source fitting and no timestamp >= prediction time in histories;
- reproducibility test from pinned hashes and seed;
- synthetic adapter tests labeled `synthetic_engineering_evidence`, never real-user efficacy.

## Run artifacts

Each Stage 9B run must create a timestamped directory containing:

- `run_manifest.json` with git/project revision if available, source hashes, configuration, seed, runtime versions;
- `preprocessing_flow.json` and per-user counts;
- `fold_assignments.csv` (anonymous public user indices only);
- `per_participant_metrics.csv` and aggregate metrics;
- bootstrap distribution summary/CI;
- neighbor/coverage diagnostics with no raw health text;
- claim evaluation file;
- safety/candidate/evidence/guard audits;
- SHA-256 manifest and acceptance ZIP.

Formal output must be immutable. Any rerun gets a new run ID.

## Exit gates

Stage 9B is ready for a formal run only after:

- all source/schema hashes pass;
- all leakage tests pass;
- product candidate invariance and safety tests are zero-violation;
- frozen metric code is reviewed before results are examined;
- HeartSteps external results and product engineering results are reported under separate provenance labels.

A 微律 real-user pilot remains a separate authorization, ethics/privacy, consent, and evaluation stage.
