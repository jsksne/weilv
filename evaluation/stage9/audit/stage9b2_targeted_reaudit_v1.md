# Stage 9B.2 Targeted Post-Repair Re-audit v1

- Generated: 2026-08-19
- Model used: GLM-5.3
- Audit type: NARROW TARGETED RE-AUDIT (no full forensic re-audit)
- Ticket scope: F-001 repair, F-002 repair, regression tests, new freeze
  integrity, external evaluator unchanged, Personal/Agentic CF integration
  continuity, formal lock.
- Production code modified during this audit: NONE. `--formal` NOT run.

## 1. Repair bundle verification

| Item | Expected | Actual | Status |
| --- | --- | --- | --- |
| `evaluation/stage9b1_fail_closed_repair_acceptance_bundle.zip` SHA-256 | `b2ef59bae11197f93e643530a0da685c2582f16d322130063b641cab3a6ec692` | `b2ef59bae11197f93e643530a0da685c2582f16d322130063b641cab3a6ec692` | PASS |
| Bundled `collaborative_ranking.py` SHA-256 | `bafbb13958f3d45ecc7b4269680375fe5e5ab754f6ac3ccd03f9f2a5f85281bf` | `bafbb13958f3d45ecc7b4269680375fe5e5ab754f6ac3ccd03f9f2a5f85281bf` | PASS |
| Bundled `test_collaborative_ranking.py` SHA-256 | `51411379f450ef1dc92046590aad913d42620c27a771938f7d24a828721df8c1` | `51411379f450ef1dc92046590aad913d42620c27a771938f7d24a828721df8c1` | PASS |

Both bundled files match freeze manifest v2 AND the current workspace files
(`src/weilv/collaborative_ranking.py`, `tests/test_collaborative_ranking.py`).

## 2. F-001 verification — CLOSED

Original crash paths (per `stage9b_audit_findings_v1.csv`):

1. `cf_signal=None` -> `float(None)` raised `TypeError` inside `_diagnostics`
   after `validate_signals` had already (correctly) rejected the artifact.
2. Mixed-type `model_version` / `data_version` -> `sorted()` raised
   `TypeError: '<' not supported between instances of 'str' and 'int'`.

### 2.1 Source inspection (old crash paths gone)

- `cf_signal` is read for diagnostics through `_coerce_float(value,
  NEUTRAL_CF_SIGNAL)` — None / non-numeric / bool / non-finite degrade to the
  neutral fallback; never raises.
- `model_version` / `data_version` are read through `_coerce_str(...)` before
  `sorted()`, so the sorted collection is homogeneous `str`; never raises.
- The `validate_signals` call is wrapped in a fail-closed `try/except`
  (`validation_failed_fail_closed`); the `sorted()` sort path is guarded
  (`sort_failed_fail_closed`).
- `_entry` returns `{}` for non-`str` keys and non-dict entries.

### 2.2 Mechanical reproduction (script:
`evaluation/stage9/audit/stage9b2_repro_f001_f002.py`, results:
`stage9b2_repro_results_v1.json`, run against the current workspace SHA
`bafbb139...`)

**Scenario A — `cf_signal = None`:**

- No exception.
- `cf_applied = False`, reason `nonfinite_or_out_of_range_signal`.
- Original ordering preserved; candidate multiset identical; cardinality
  identical.
- Diagnostics report the neutral fallback `0.0` per task; before/after
  candidate ID lists identical.
- Also reproduced with an exact `adjusted_rank` tie present: the tie is NOT
  reordered (fail-closed wins over tie-breaking).

**Scenario B — mixed-type metadata (`5`, `"v1"`, `20260818`, `"2026-08-18"`):**

- No exception.
- `cf_applied = True` (signals themselves are valid).
- Diagnostics degrade malformed versions to neutral fallbacks
  (`"neutral-v0.1"`, `"none"`); valid strings are kept.
- Ranking is byte-identical to a clean-metadata twin run with the same
  `cf_signal` values -> metadata fallback CANNOT affect ranking.

**Scenario C — malformed container/provider diagnostic values:**

- As ranking signal (`cf_signal` = list / dict / bool / NaN / +inf / -inf):
  no exception; every case fails closed with reason
  `nonfinite_or_out_of_range_signal`; original ordering, multiset, and
  cardinality preserved in every case.
- As metadata (`neighbor_count` = list/dict, `model_version` = list/bool,
  `data_version` = dict/bool): no exception; `cf_applied = True`; the valid
  `cf_signal` values still decide the exact tie; all metadata fall back to
  neutral values.

**F-001 status: CLOSED** (mechanically reproduced against the repaired SHA).

## 3. F-002 verification — CLOSED

`neighbor_count` values tested: `"unknown"` (str), `None`, `{"x": 1}` (dict),
`NaN`, `+inf`.

- No exception in any case.
- Diagnostic fallback = safe neutral value `0` in every case.
- Ranking unaffected: identical to a clean `neighbor_count=0` twin run.
- `cf_applied = True` when the signals themselves are valid.

**F-002 status: CLOSED** (mechanically reproduced against the repaired SHA).

## 4. Fail-closed semantics

- Malformed `cf_signal` is NOT clamped: `1.5` and `-2.0` both fail closed with
  `nonfinite_or_out_of_range_signal` and the original order (verified
  mechanically; no clamping into `[-1, 1]`).
- Malformed `cf_signal` is never treated as a valid learned score and cannot
  affect ordering; the adapter returns the original safe ordering.
- Valid `cf_signal` contract unchanged: numeric, finite, within `[-1, 1]`,
  non-boolean.
- Metadata fallbacks (model/data version, neighbor_count) are neutralized
  without invalidating an otherwise valid ranking signal; metadata cannot
  influence ranking because the sort key reads only values validated by
  `validate_signals`.

## 5. Ranking contract unchanged

- Sort semantics verified mechanically:
  `adjusted_rank` ascending -> `cf_signal` descending -> `base_task_rank`
  ascending -> `task_id` ascending (5-task case with two distinct exact ties
  ordered `B,D,C,A,E` exactly as the contract requires).
- CF still only affects exact `adjusted_rank` ties (no-tie no-op covered by the
  suite).
- Candidate multiset identical; candidate cardinality identical.
- No task mutation (object identity preserved); no evidence-ID mutation.
- Blocked resurrection = 0 (forged maximal signal for a non-candidate task
  fails closed `unknown_task_signal`; no blocked task enters the output).
- HeartSteps product score transfer = NONE (module contains no HeartSteps
  references beyond the prohibition docstring; preformal integrity report:
  `heartsteps_parameters_transferred_to_product: "NO"`).
- Provider remains neutral before a real 微律 pilot (production default
  `cf_provider=None` strict no-op; `neutral_cf_provider` emits `0.0`).

## 6. External evaluator SHA gate

| File | Expected | Actual | Status |
| --- | --- | --- | --- |
| `evaluation/stage9/preprocess_heartsteps_v1.py` | `69b1a08849dee8c7921a5661d2ce3dd6e00916be835d29db2d8260654f92cde4` | `69b1a08849dee8c7921a5661d2ce3dd6e00916be835d29db2d8260654f92cde4` | UNCHANGED |
| `evaluation/stage9/run_stage9_external_cf.py` | `99a11edd3e09521236cbf21893231eef15783d231898be3fae125bc67b03a714` | `99a11edd3e09521236cbf21893231eef15783d231898be3fae125bc67b03a714` | UNCHANGED |

## 7. Personal / Agentic integration snapshot

Snapshot (continuity check, not a full re-audit):

- `src/weilv/personal_rag.py` SHA-256:
  `6bb5b9eb2ec18e8491cd1034ebd4bb584f0d1ad80ab33d33c6759d71d74c6df9`
- `src/weilv/agentic_rag.py` SHA-256:
  `a96929252d6a47d734af7c85ebd0fafe0d546d85819f3c1baa3da1f349fd351c`

Source inspection confirms the integration semantics remain:

```
safe candidate set -> Personal/Agentic ranking -> CF exact-tie adapter -> final selection
```

- `personal_rag.py`: `_run_basic_pipeline` terminal results return before CF
  is ever consulted; `personalize_task_candidates` runs first;
  `apply_cf_to_ranking(personalized, cf_provider)` runs after; `personalized[0]`
  is the final selection; `cf` diagnostics attach only on `allowed`.
- `agentic_rag.py`: `apply_personalization` short-circuits any
  `safety_status not in {None, "allowed"}` to `{}` (CF never runs on terminal
  states); a candidate-invariance check runs BEFORE CF
  (`personalization_candidate_invariance_failed` -> `no_safe_task`);
  `apply_cf_to_ranking` runs after personalization, before
  `select_and_ground` picks `ranking[0]`.
- Neither file introduces: HeartSteps scores, candidate expansion, safety
  bypass, terminal-state bypass, evidence mutation.
- Production default `cf_provider=None` -> strict no-op in both paths.
- Neither file was modified by this audit.

## 8. Test results (actual current results)

| Suite | Command | Result | Baseline | Status |
| --- | --- | --- | --- | --- |
| Product CF adapter | `pytest tests/test_collaborative_ranking.py -q` | 32 passed | 32 | PASS |
| Stage 9 | `pytest tests/test_stage9_heartsteps_preprocessing.py tests/test_stage9_external_cf.py tests/test_collaborative_ranking.py -q` | 74 passed | 74 | PASS |
| Full unit regression | `pytest -m "not integration and not live_model" -q` | 329 passed, 13 deselected | 329 passed, 13 deselected | PASS |
| Integration (live ES) | `pytest -m integration -q` | 13 passed, 329 deselected | 13 passed | PASS |
| Lint | `ruff check src/weilv/collaborative_ranking.py tests/test_collaborative_ranking.py` | All checks passed | clean | PASS |

All test commands were run with `.venv\Scripts\python.exe` (Python 3.12).

## 9. Freeze v2 verification

- Manifest: `evaluation/stage9/preformal/stage9_evaluator_freeze_manifest_v2.json`
- `reason_for_refreeze` = "Stage 9B.1 fail-closed product adapter repair after
  independent preformal audit" (matches the ticket).
- `formal_mode_executed = false`, `formal_results_computed = false`.
- All 14 files listed in v2 were re-hashed; **14/14 match; 0 mismatches**.
- Changed-vs-v1 files are EXACTLY:
  - `product/collaborative_ranking.py`
  - `product/tests/test_collaborative_ranking.py`
- The other 12 files (evaluators, runners, methodology docs, claim registry,
  Stage 9 tests, conftest) are unchanged vs v1 -> no methodology/evaluator
  changes.

## 10. Formal lock

- `--formal` was NOT run: the string `stage9_formal_run` appears only inside
  the evaluator source (the writer function), never in any output artifact;
  no `evaluation/runs/*stage9*` directory exists.
- Delta_V does NOT exist as a real Stage 9 result
  (`stage9_leakage_test_report_v1.json`: `delta_v_computed: false`).
- Real bootstrap CI does NOT exist.
- CR-CF-001 has NOT been formally evaluated
  (`stage9_preformal_integrity_v1.json`: `formal_cf_result_computed: false`).
- No formal driver was executed at any point during this audit.

## 11. Findings

| Severity | Count | Detail |
| --- | --- | --- |
| BLOCKER | 0 | — |
| MAJOR | 0 | — |
| MINOR | 0 | — |

No new findings. F-001 (MAJOR) and F-002 (MINOR) from the previous independent
audit are verified CLOSED by mechanical reproduction against the repaired SHA.

## 12. Verdict

READY_FOR_FORMAL_RUN

Conditions satisfied: F-001 CLOSED; F-002 CLOSED; 0 BLOCKER; 0 unresolved
MAJOR; repair ZIP SHA PASS; freeze v2 integrity PASS (14/14, expected diff
only); external evaluator SHAs unchanged; ranking contract unchanged; product
integration continuity PASS; formal mode still unexecuted.

## 13. Acceptance bundle

`evaluation/stage9b2_targeted_reaudit_acceptance_bundle.zip` contains only:
this audit report (md + json), the repro script and its results JSON, the test
result summary, freeze manifest v2, the repair finding closure CSV, and the
repair SHA comparison report. No raw HeartSteps CSV, no `.env` / API keys, no
formal results (none exist). ZIP SHA-256 is recorded in the JSON artifact and
in `stage9b2_targeted_reaudit_acceptance_bundle_sha256.txt` next to the bundle.
