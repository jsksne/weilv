# Stage 9B Test Quality Audit v1

Date: 2026-08-18
Auditor: independent preformal code audit (GLM-5.3)
Scope: semantic inspection of Stage 9 / product CF tests — not just counts.

## Reported vs verified counts

| Suite | Reported | Rerun 2026-08-18 | Result |
|---|---|---|---|
| Stage 9 preprocessing (`tests/test_stage9_heartsteps_preprocessing.py`) | 18 | 18 (within 69) | PASS |
| Stage 9 external CF (`tests/test_stage9_external_cf.py`) | 24 | 24 (within 69) | PASS |
| Product CF adapter (`tests/test_collaborative_ranking.py`) | 27 | 27 (within 69) | PASS |
| Full unit (`tests/` minus `tests/integration`) | 324 | 324 passed in 15.83s | PASS |
| Integration (`tests/integration`) | 5 (ticket) | 13 passed in 81.75s | PASS (superset of ticket figure; no failures) |

Exact rerun commands (all safe; no `--formal`):

```
.\.venv\Scripts\python.exe -m pytest tests/test_stage9_heartsteps_preprocessing.py tests/test_stage9_external_cf.py tests/test_collaborative_ranking.py -q
  -> 69 passed in 10.31s
.\.venv\Scripts\python.exe -m pytest tests/ --ignore=tests/integration -q
  -> 324 passed, 1 warning in 15.83s
.\.venv\Scripts\python.exe -m pytest tests/integration -q
  -> 13 passed, 1 warning in 81.75s
```

## Required-topic coverage matrix (contract §18)

| # | Required semantics | Covered by | Asserts semantics? |
|---|---|---|---|
| 1 | No `is.randomized == True` inclusion filter | preprocessing tests + AM-001 block in evaluator | YES — false rows remain eligible |
| 2 | Action reconstruction (NONE/WALKING/ANTISEDENTARY truth table, contradictions excluded) | preprocessing tests | YES — exhaustive encoding table, no heuristic repair |
| 3 | Primary outcome `ln(jbsteps30.zero + 0.5)`; raw jbsteps30 not required for eligibility | preprocessing tests | YES |
| 4 | Day boundaries 1–42 | preprocessing tests | YES — day 0 / day 43 excluded |
| 5 | Held-out user isolation per LOPO fold | external CF tests | YES — target absent from all source objects |
| 6 | Future target leakage (utime < t) | external CF tests (synthetic driver) | YES |
| 7 | Future source leakage (relative < t) | external CF tests (synthetic driver) | YES |
| 8 | Per-t base recomputation | external CF tests | YES — no full-period reuse |
| 9 | Per-t clipping percentile recomputation (source-history-only 5/95) | external CF tests | YES |
| 10 | Missing neighbor requested cell / weight alignment (previous bug §9) | external CF tests | YES — contributor filtered by cell presence; each residual keeps its own similarity weight |
| 11 | SNIPS formula (w, V, ESS exact values) | external CF tests (`snips_weight_value_ess_exact`) | YES — exact numeric assertion (V=1.5909…, ESS=2.9512…) |
| 12 | Participant bootstrap (paired, 10000, seed 20260818) | external CF tests (`bootstrap_seed_determinism`) | YES — deterministic CI fixture |
| 13 | Zero support (retain, NOT_EVALUABLE, claim blocked) | external CF tests (`zero_support_detected`) | YES — reason `zero_denominator_or_ess` |
| 14 | PRECHECK no-formal behavior | external CF / runner tests | YES — default PRECHECK; formal requires explicit `--formal` |
| 15 | Candidate invariance (multiset + cardinality before/after) | adapter tests | YES — invariant checks with rollback |
| 16 | Blocked-task resurrection impossible | adapter tests | YES — reorder-only over post-Safety candidates |
| 17 | NaN / infinity / out-of-range scores fail closed | adapter tests | YES — `nonfinite_or_out_of_range_signal` + original order |
| 18 | Terminal-state bypass impossible | adapter tests + safety contract tests | YES |
| 19 | Exact-tie-only reorder; no tie → no change | adapter tests | YES |

All 19 required topics covered with semantic assertions, not count-only.

## Gaps found (quality)

- No adapter test exercises the malformed-diagnostics shapes that crash
  `_diagnostics` (findings F-001 / F-002): `cf_signal=None` key-present,
  non-numeric `neighbor_count`, mixed-type `model_version`/`data_version`.
  The existing fail-closed tests cover the *listed* corrupt-artifact shapes
  (NaN, ±inf, out-of-range, non-dict, missing) but not these three.
  The repair ticket fixing F-001/F-002 must add regression tests for them.

## Verdict

PASS with noted gap — test suites are semantically strong; the only gap is
exactly the pair of defects reported in `stage9b_audit_findings_v1.csv`.
