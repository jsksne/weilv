# Stage 9B implementation self-audit checklist v1

Machine-generated checklist against the frozen Stage 9A v1.1 spec.  Status per
point: PASS / FAIL with evidence.  This document is engineering evidence; the
final gate also requires the independent audit report.

| # | Spec point | Status | Evidence |
|---|---|---|---|
| 1 | `is.randomized == True` is NOT an inclusion filter (operational field; action space none/walking/antisedentary p 0.4/0.3/0.3) | PASS | `preprocess_heartsteps_v1.py` R1 requires nonblank operational fields only; regression test `test_is_randomized_false_rows_are_retained` fails under a hypothetical `is.randomized==True` filter |
| 2 | Exact action reconstruction; inconsistent rows excluded AND counted | PASS | `reconstruct_action` (exact 3 encodings, else None); R6 excludes + `flow["invalid_action_rows"]`; `test_action_reconstruction_invalid_encodings_are_none` |
| 3 | y = ln(jbsteps30.zero + 0.5); raw jbsteps30 not a primary eligibility condition | PASS | `build_analysis_rows`; R8 requires finite nonnegative `jbsteps30.zero` only; `test_raw_jbsteps30_missing_is_not_an_eligibility_condition` |
| 4 | Exclusion-rules JSON (exact order, source fields, counts, remaining, FROZEN_PREREG vs PUBLIC_RELEASE_OPERATIONALIZATION; paper denominators comparison-only) | PASS | `emit_flow_manifests` -> `stage9_public_release_exclusion_rules_v1.json`; R1-R8 fixed order; `paper_comparison_only` block; `NOT_EXACTLY_RECONSTRUCTABLE_FROM_PUBLIC_FIELDS` path |
| 5 | Temporal leakage: 37-fold LOPO; held-out user never in source; target history strictly before t; source strictly earlier relative time; per-t censoring of base means/residuals/neighbor vectors/similarity/clipping; no post-response features | PASS | `evaluate_all_folds` + `predict_at_time` (mask `rel_time < t`, history `utime < t`); per-t `_base_components` and percentile clip; `record_leakage_violations`; tests `test_driver_runs_with_zero_leakage_violations`, `test_held_out_user_never_in_source`, `test_record_leakage_violations_detects_future_leaks`; per-t base verified empirically |
| 6 | Context model: slot, activity, location, weather, prior-step bucket, study week only | PASS | `CONTEXT_FEATURES` whitelist; `CONTEXT_WHITELIST`; `verify_temporal_structure` rejects extra columns |
| 7 | Model: shrinkage n/(n+10); personal fallback action-slot -> action -> overall; cosine on co-observed, shrunk n_common/(n_common+10); >=3 common cells; positive only; max 5 neighbors; >=3 contributors else 0; clip 5/95 at t; hybrid=base+personal+cf; comparator=base+personal; no alpha | PASS | `_base_components`, `personal_signal`, `compute_cf_signal`, `predict_at_time`; constants SHRINKAGE_DENOM=10, MIN_COMMON_CELLS=3, MAX_NEIGHBORS=5, MIN_CONTRIBUTORS=3; tests `test_personal_signal_fallback_chain`, `test_cf_signal_requires_three_contributors_and_clips` |
| 8 | SNIPS w=I/p; V=sum(w y)/sum(w); ESS=(sum w)^2/sum(w^2); Delta_V=mean over participants; paired participant bootstrap 10000 seed 20260818 percentile 95% CI | PASS | `snips_metrics`, `participant_bootstrap_ci`; constants BOOTSTRAP_REPLICATES=10000, BOOTSTRAP_SEED=20260818; `test_snips_exact_weights_value_ess`, `test_bootstrap_seed_determinism_and_replicates` |
| 9 | Zero support: retain + report; aggregate NOT_EVALUABLE; CR-CF-001 CANNOT_BE_SUPPORTED | PASS | `zero_support_reason`, `evaluate_claim`; `test_zero_support_makes_primary_not_evaluable` |
| 10 | EXTERNAL labels + interpretation label | PASS | `POLICY_PERSONAL`/`POLICY_PLUS_CF` = EXTERNAL_*; `METHOD_INTERPRETATION`; run manifest + claim_evaluation + freeze manifest |
| 11 | Modes: default PRECHECK; FORMAL only with --formal; PRECHECK computes no real result and executes no model on real data | PASS | `build_parser` default `formal=False`; `run_precheck` uses `verify_temporal_structure` (no model) + synthetic fixtures; `test_default_invocation_is_precheck`, `test_precheck_never_computes_formal_result` |
| 12 | Product adapter invariants; terminal-state bypass; no HeartSteps transfer; neutral provider; Basic RAG/API unchanged | PASS | `apply_cf_tiebreak`/`apply_cf_to_ranking` fail-closed matrix; `test_agentic_non_allowed_terminal_states_never_call_cf`; `neutral_cf_provider`; personal/agentic integration default no-op; `test_agentic_default_no_cf_diagnostics`; no API schema change |

## Test coverage present for required areas

- no-is.randomized-filter regression: `tests/test_stage9_heartsteps_preprocessing.py::test_is_randomized_false_rows_are_retained`
- held-out-user isolation: `tests/test_stage9_external_cf.py::test_held_out_user_never_in_source`
- future-target leakage: `test_record_leakage_violations_detects_future_leaks` (+ driver zero-violation test)
- future-source leakage: same
- post-response leakage: same + `test_temporal_structure_verifier_detects_real_violations`
- zero-support: `test_zero_support_makes_primary_not_evaluable`
- PRECHECK-no-formal: `test_precheck_never_computes_formal_result`
- bootstrap seed determinism: `test_bootstrap_seed_determinism_and_replicates`
- adapter safety matrix (neutral, tie reorder, no-tie no-op, extra/duplicate task, NaN/inf, out-of-range, missing/corrupt artifact, forged blocked-task score, terminal states, candidate invariance, blocked resurrection, task/evidence mutation, privacy): `tests/test_collaborative_ranking.py` (25 tests)

## Independent audit findings — resolution log (2026-08-18)

The independent spec audit returned 1 BLOCKER + 2 MAJOR + several MINOR/NIT
findings.  All were fixed, tested, and re-verified:

| Finding | Severity | Resolution | Regression test |
|---|---|---|---|
| cf_signal weighted mean misaligned when a top-5 neighbor lacks the requested cell | BLOCKER | contributor-aligned weights (own similarity per contributor) in `compute_cf_signal` | `test_cf_signal_weights_align_with_contributors` |
| adapter crashed (TypeError) on missing/None rank fields instead of failing closed | MAJOR | `validate_signals` requires numeric `adjusted_rank`/`base_task_rank`; `sort` wrapped in defensive fail-closed | `test_missing_rank_fields_fail_closed` |
| SNIPS applied to `is.randomized==False` rows without a documented decision | MAJOR | preregistration amendment AM-001 documented; secondary `is.randomized==True` sensitivity added (never affects primary) | `test_randtrue_secondary_sensitivity_present` |
| PRECHECK's model probe could touch real data | MAJOR (hardened) | PRECHECK now pure data-driven (`verify_temporal_structure`); no model execution on real data | `test_precheck_never_invokes_the_model` |
| base means / clip percentiles per-t censoring untested | MINOR (test gap) | added | `test_base_scores_and_clips_exclude_future_source_rows` |
| Personal-path terminal-state CF bypass untested | MINOR (test gap) | added | `test_personal_terminal_states_never_call_cf` |
| `BOOTSTRAP_REPLICATES == 10000` untested | NIT | added | `test_bootstrap_replicate_constant_is_frozen` |
| empty-cohort IndexError in analysis-table write | MINOR | explicit refusal with clear error | covered by guard |
| `_cli` FORMAL could persist results with failed gates | MINOR | `run_formal` refuses to write any run unless integrity + leakage gates pass | code gate |
| dead code (`_context_of`, `bucket_*_from_code`) | NIT | removed | ruff clean |
| CR-CF-002/003 claim evaluation absent | MINOR | added to product CF contract report | report content |

## Result

All 12 points PASS on self-audit; independent-audit findings resolved with
regression tests (69 new Stage 9 tests, 324 unit / 5 integration passing).
Pending: real-data preflight artifacts (flow/exclusion/leakage) once the pinned
HeartSteps CSVs are provided; final acceptance ZIP.
