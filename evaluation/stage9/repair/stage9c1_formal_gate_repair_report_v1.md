# Stage 9C.1 — Formal Gate Wiring Repair Report

Status: **NARROW PRE-RESULT EVALUATOR WIRING REPAIR — COMPLETE**

## 1. Background

Formal Attempt #1 of the frozen Stage 9 external CF evaluator failed **before any
CF computation**:

- Command (attempt 1): `$env:PYTHONPATH=<repo root>; .venv\Scripts\python.exe evaluation/stage9/run_stage9_external_cf.py --formal --no-download`
- Exit code: `1`
- Integrity gates at launch (all visible fields PASS): `heartsteps_hashes=PASS, duplicates=0, users=37, raw_rows=8274, final_rows=5905`
- Error: `RuntimeError: FORMAL run blocked by integrity gates: {...}` raised by `run_formal()`
- No run directory was created; no Delta_V / CI / CR-CF-001 was computed or persisted.
- Failure log preserved: `evaluation/stage9/formal/stage9_formal_attempt1_failure_log_v1.json`
- Execution record (attempt 0 + attempt 1): `evaluation/stage9/formal/stage9_formal_execution_record_v1.json`

## 2. Root cause (independently verified)

In `evaluation/stage9/run_stage9_external_cf.py`:

- `check_integrity_gates()` returns a dict WITHOUT a `schema_ok` key.
- `run_formal()` requires `integrity_gates.get("schema_ok") is True` before writing any run.
- `_cli()` passed `check_integrity_gates()` output directly to `run_formal()`.
- Consequence: the FORMAL path **always** raised at the integrity-gate check.
- `check_schema(analysis_rows)` already exists and is already used by PRECHECK.
- The frozen test suite (`tests/test_stage9_external_cf.py`) never exercised `run_formal()`,
  so this wiring gap was not covered by tests.

## 3. Repair (minimal, pre-result)

Single narrow change in `_cli()` of `run_stage9_external_cf.py`, placed AFTER the
PRECHECK branch (so PRECHECK behavior is byte-for-byte unchanged):

```python
    # Stage 9C.1 wiring repair: the real schema result (computed over the
    # constructed analysis table) must reach the FORMAL integrity gate.
    # PRECHECK recomputes schema internally, so its behavior is unchanged.
    # Fail-closed semantics are unchanged: run_formal blocks whenever
    # schema_ok is not True (including a failing schema check).
    schema = check_schema(analysis_rows)
    integrity_gates["schema_ok"] = schema["schema_ok"]
```

- No hardcoded `True`; the value is the real `check_schema()` result.
- A failing schema check yields `schema_ok=False`, and `run_formal()` still fails closed.
- Nothing else changed: no CF model, LOPO, SNIPS, outcome, eligibility, bootstrap,
  temporal censoring, or methodology change.

## 4. Regression tests added

`tests/test_stage9_external_cf.py` (new section "Stage 9C.1 formal integrity-gate
wiring repair"):

1. `test_formal_cli_passes_real_check_schema_result_to_run_formal` — drives the real
   `_cli()` FORMAL path with a synthetic analysis table; `run_formal` is stubbed and
   captures the gates dict; asserts `schema_ok` is present and equals the real
   `check_schema()` result over the rows the CLI constructed.
2. `test_valid_schema_schema_ok_true_reaches_formal_gate` — valid schema →
   `schema_ok is True` reaches the formal gate.
3. `test_invalid_schema_schema_ok_false_blocks_formal` — schema broken (study_day=99);
   the REAL `run_formal()` raises `FORMAL run blocked by integrity gates` and no
   `*_stage9_formal` run directory is created.
4. `test_formal_gate_wiring_tests_never_run_real_computation` — `run_formal` and
   `evaluate_all_folds` are stubbed/forbidden; asserts no formal run directory and no
   real model execution.
5. `test_precheck_cli_gates_unchanged_by_wiring_repair` — the PRECHECK CLI path
   receives the gates dict exactly as before the repair (no `schema_ok` key added).

## 5. Verification

- Stage 9 tests (3 files): **79 passed** (`test_stage9_heartsteps_preprocessing.py`,
  `test_stage9_external_cf.py`, `test_collaborative_ranking.py`).
- Full unit regression `pytest tests/ --ignore=tests/integration`: **334 passed, 0 failed**.
- Full `pytest tests/`: 346 passed, 1 failed —
  `tests/integration/test_feedback_flow_integration.py::...` fails with
  `elastic_transport.ConnectionTimeout` because the local Elasticsearch
  (`http://127.0.0.1:9200`) is not running. Pre-existing environmental
  (ES-dependent integration) failure, unrelated to this repair.
- Unrelated frozen semantics: all other 12 manifest-v2 files byte-identical; source
  data 4/4 PASS; targeted audit ZIP SHA unchanged. See
  `evaluation/stage9/repair/stage9c1_sha_verification_v1.json`.

## 6. Refreeze

- `evaluation/stage9/preformal/stage9_evaluator_freeze_manifest_v3.json` created
  (v2 untouched).
- Reason: "Stage 9C.1 formal integrity-gate wiring repair after Formal Attempt #1
  pre-computation failure".
- `formal_attempt_1 = FAILED_PRE_COMPUTATION`
- `formal_results_computed = false`
- Attempt #1 DID invoke `--formal` (hence `formal_mode_executed = true` in v3) but
  produced no formal computation/result.

## 7. Status

**READY_FOR_TARGETED_REAUDIT**
