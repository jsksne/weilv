# Stage 9B test report v1

Generated: 2026-08-18T14:16:03.881542+00:00

## New Stage 9 tests

- `tests/test_stage9_heartsteps_preprocessing.py`: 18 tests (hash verification, action reconstruction, no-is.randomized-filter regression, eligibility rule order, primary outcome, flow manifests, CSV round-trip).
- `tests/test_stage9_external_cf.py`: 24 tests (frozen model math, SNIPS, bootstrap seed, claim mechanics, temporal leakage checks, PRECHECK never computing the formal result, determinism).
- `tests/test_collaborative_ranking.py`: 27 tests (product CF contract safety matrix, absolute invariants, privacy, Personal/Agentic integration, terminal-state bypass).

## Existing regression suite

- Unit suite (`not integration and not live_model`): **324 passed, 0 failed** (13 integration/live_model deselected).
- Integration suite against live Elasticsearch: **5 passed, 0 failed** (332 live_model deselected).

## Result

- No existing frozen behavior regressed.
- All new Stage 9 tests pass.
- Formal CF result: NOT computed (PRECHECK only).

