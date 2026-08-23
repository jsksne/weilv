# Stage 9B.2 Targeted Re-audit — Test Result Summary v1

Generated: 2026-08-19. All commands run with `.venv\Scripts\python.exe`
(Python 3.12) from the repository root. Actual current results reported; no
historical numbers substituted.

| # | Suite | Command | Result | Repaired baseline | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Product CF adapter (narrow) | `pytest tests/test_collaborative_ranking.py -q` | 32 passed in 1.70s | 32 passed | PASS |
| 2 | Stage 9 combined | `pytest tests/test_stage9_heartsteps_preprocessing.py tests/test_stage9_external_cf.py tests/test_collaborative_ranking.py -q` | 74 passed in 4.28s | 74 passed | PASS |
| 3 | Full unit regression | `pytest -m "not integration and not live_model" -q` | 329 passed, 13 deselected, 1 warning in 8.00s | 329 passed, 13 deselected | PASS |
| 4 | Integration (live ES) | `pytest -m integration -q` | 13 passed, 329 deselected, 1 warning in 53.61s | 13 passed | PASS |
| 5 | Lint | `ruff check src/weilv/collaborative_ranking.py tests/test_collaborative_ranking.py` | All checks passed | clean | PASS |

The single warning in suites 3–4 is a pre-existing
`StarletteDeprecationWarning` from `fastapi.testclient` (httpx deprecation
notice), unrelated to the Stage 9B.1 repair.

Regression coverage for the repair (inside suite 1):
`test_cf_signal_none_fails_closed_without_exception` (F-001 A),
`test_malformed_mixed_type_version_metadata_fails_closed` (F-001 B),
`test_non_numeric_neighbor_count_degrades_safely` (F-002, parametrized
`"unknown"` / `None` / `{"x": 1}`), plus the pre-existing NaN / ±inf /
out-of-range / unknown-task / duplicate-task / missing-rank / candidate-
invariance / blocked-forgery / terminal-state matrix.

Independent mechanical reproduction (not via pytest):
`stage9b2_repro_f001_f002.py` -> `stage9b2_repro_results_v1.json`:
18/18 cases PASS (`all_pass: true`), covering F-001 scenarios A/B/C
(including list/dict/bool/NaN/+inf/-inf as cf_signal and as metadata),
F-002 (`"unknown"`/None/dict/NaN/+inf neighbor_count), the exact sort
contract, no-clamping semantics, and blocked-resurrection guard.
