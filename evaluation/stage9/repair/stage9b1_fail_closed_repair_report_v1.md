# Stage 9B.1 Fail-Closed Product CF Adapter Repair Report v1

Generated: 2026-08-19

Repair ticket: 微律 Stage 9B.1 — Product CF Fail-Closed Repair (narrow scope).
This is a repair-only change. No Stage 9 methodology, preprocessing, external
evaluator, SNIPS, LOPO, temporal censoring, Personal/Agentic RAG ranking
semantics, or public API schema was modified. `--formal` was never run.

## 1. Findings and root causes

### F-001 — MAJOR (product_cf_adapter)

- Component: `src/weilv/collaborative_ranking.py`, function
  `apply_cf_tiebreak` -> `_diagnostics` (module-level helpers + diagnostics build).
- Root cause: the diagnostics builder performed **raw, unguarded** coercions on
  provider artifact values:
  - `float(_entry(task_id).get("cf_signal", NEUTRAL_CF_SIGNAL))` raised
    `TypeError: float() argument must be a string or a real number, not
    'NoneType'` when `cf_signal` was `None`.
  - `sorted({_entry(task_id).get("model_version", ...) ...})` raised
    `TypeError: '<' not supported between instances of 'str' and 'int'` when
    version metadata was mixed-type (e.g. `5` vs `"v1"`).
- Why it crashed previously: `validate_signals` correctly rejected the
  malformed artifact and the code then entered the **fail-closed branch**
  (`_diagnostics(False, reason)`); but `_diagnostics` itself crashed on the same
  malformed values, so the caller received an exception instead of the
  contractually guaranteed original safe ordering. This violates the audit
  contract section 15 ("No crash" for corrupt artifacts).
- Confirmed synthetic repro (from audit): `signals={'t1': {'cf_signal': None}}`
  -> `TypeError`; two tasks with `model_version` `5` vs `'v1'` -> `TypeError`.

### F-002 — MINOR (product_cf_adapter)

- Component: same file, `_diagnostics` (`cf_neighbor_count_by_task`).
- Root cause: `int(_entry(task_id).get("neighbor_count", 0))` raised
  `ValueError: invalid literal for int() with base 10: 'many'` for non-numeric
  `neighbor_count` (e.g. `"many"`, `None`, object-like values).
- Why it crashed previously: `neighbor_count` is diagnostics-only metadata (never
  a ranking input, never validated), so a malformed value reached `int()` and
  crashed the whole adapter instead of degrading safely.

## 2. Files changed

| File | Change |
| --- | --- |
| `src/weilv/collaborative_ranking.py` | Production repair (only allowed production file) |
| `tests/test_collaborative_ranking.py` | Regression tests added (Stage 9 product CF adapter tests) |

## 3. Functions changed (`src/weilv/collaborative_ranking.py`)

- `_coerce_float(value, default)` — **new** exception-safe finite-float coercion
  for diagnostics metadata. Rejects booleans and non-numeric types; non-finite
  values degrade to `default`. Never raises.
- `_coerce_int(value, default)` — **new** exception-safe finite-int coercion for
  diagnostics metadata. Guards `int(float('nan'))` / `int(float('inf'))` via
  `ValueError`/`OverflowError`. Never raises.
- `_coerce_str(value, default)` — **new** exception-safe non-empty-string
  coercion for version metadata. Never raises.
- `validate_signals(...)` — hardened the candidate `task_id` check to require a
  non-empty `str` (prevents `set(task_ids)` crashing on unhashable /
  non-string candidate ids); directly-related coercion path.
- `apply_cf_tiebreak(...)` — `_entry` now returns `{}` for non-`str` keys;
  `_diagnostics` rebuilt on the coercion helpers above (all values, including
  keys, are made safe); the `validate_signals` call is wrapped in a fail-closed
  `try/except` so validation can never crash the caller.

## 4. New fail-closed semantics

- Malformed / corrupt / non-finite / unexpected provider diagnostics **fail
  closed**: `validate_signals` rejects the artifact, the adapter returns the
  **original safe candidate ordering** with `cf_applied=False` and a reason, and
  `_diagnostics` reports safe fallback values (`NEUTRAL_CF_SIGNAL = 0.0`,
  `neighbor_count = 0`, `NEUTRAL_MODEL_VERSION`, `NEUTRAL_DATA_VERSION`).
- Fallback values are diagnostics metadata only and **never influence task
  ranking** — ranking reads only values that passed `validate_signals`
  (numeric, finite, within [-1, 1], non-boolean).
- A valid `cf_signal` contract is unchanged and still strict: numeric, finite,
  within `[-1, 1]`; anything else is invalid -> neutral CF / original order.
  Malformed scores are never clamped into valid scores; `None` is never
  converted to `0.0` in a way that would make a corrupt artifact appear valid.
- The sort path remains guarded (`sort_failed_fail_closed`).

## 5. Regression tests added (`tests/test_collaborative_ranking.py`)

- `test_cf_signal_none_fails_closed_without_exception` — **Test A**: provider
  `cf_signal = None`. Expects no exception, candidate multiset unchanged,
  cardinality unchanged, original ordering preserved / neutral CF
  (`cf_applied=False`, reason `nonfinite_or_out_of_range_signal`).
- `test_malformed_mixed_type_version_metadata_fails_closed` — **Test B**:
  mixed-type `model_version` / `data_version` values that previously reached
  `sorted()` / `float()` coercion. Expects no exception, neutral fallback
  versions in diagnostics, ranking unaffected.
- `test_non_numeric_neighbor_count_degrades_safely` (parametrized: `"unknown"`,
  `None`, `{"x": 1}`) — **Test C**: non-numeric `neighbor_count`. Expects no
  exception, ranking unaffected, fallback count `0` in diagnostics.

Existing coverage verified to still pass: `NaN`, `+infinity`, `-infinity`,
`score < -1`, `score > 1`, unknown task, duplicate task signal
(`duplicate_candidate_task`; `duplicate_signal_task` guard is code-covered but
not triggerable with plain dicts because Python collapses duplicate literal
keys), missing `adjusted_rank`, missing `base_task_rank`, blocked task with
forged max score, terminal state bypass (Personal and Agentic), candidate-set
invariance.

## 6. Test commands and results

| Suite | Command | Result |
| --- | --- | --- |
| Narrow product CF adapter | `pytest tests/test_collaborative_ranking.py -q` | 32 passed (27 existing + 5 new) |
| Stage 9 | `pytest tests/test_stage9_heartsteps_preprocessing.py tests/test_stage9_external_cf.py tests/test_collaborative_ranking.py -q` | 74 passed (69 baseline + 5 new) |
| Full unit regression | `pytest -m "not integration and not live_model" -q` | 329 passed, 13 deselected (324 baseline + 5 new) |
| Safe integration (live ES) | `pytest -m integration -q` | 13 passed (actual current executed count; earlier PRECHECK report recorded 5 with a different command) |
| Lint | `ruff check src/weilv/collaborative_ranking.py tests/test_collaborative_ranking.py` | All checks passed |

No failing relevant test was hidden or deselected.

## 7. External evaluator SHA verification (unchanged)

| File | Frozen v1 SHA | Current SHA | Status |
| --- | --- | --- | --- |
| `evaluation/stage9/preprocess_heartsteps_v1.py` | `69b1a08849dee8c7921a5661d2ce3dd6e00916be835d29db2d8260654f92cde4` | `69b1a08849dee8c7921a5661d2ce3dd6e00916be835d29db2d8260654f92cde4` | UNCHANGED |
| `evaluation/stage9/run_stage9_external_cf.py` | `99a11edd3e09521236cbf21893231eef15783d231898be3fae125bc67b03a714` | `99a11edd3e09521236cbf21893231eef15783d231898be3fae125bc67b03a714` | UNCHANGED |

## 8. Refreeze

New freeze manifest: `evaluation/stage9/preformal/stage9_evaluator_freeze_manifest_v2.json`

- `reason_for_refreeze`: "Stage 9B.1 fail-closed product adapter repair after
  independent preformal audit"
- `formal_mode_executed`: false
- `formal_results_computed`: false
- No Delta_V, no CI, no CR-CF-001 evaluation.

## 9. Confirmation

- `--formal` was never run.
- No Delta_V computed, no CI computed, no CR-CF-001 evaluation.
- Product provider remains neutral before a real 微律 pilot; no HeartSteps
  weights / action scores / user embeddings / domain parameters enter product
  task ranking. The five COARSE_DOMAIN_ONLY mappings remain documentation-only.
- Status: READY_FOR_TARGETED_REAUDIT (not a formal-gate declaration).
