# Stage 9B.1 test result report v1

Generated: 2026-08-19

| Suite | Command | Result |
| --- | --- | --- |
| Narrow product CF adapter | `pytest tests/test_collaborative_ranking.py -q` | 32 passed in 1.78s (27 existing + 5 new regression cases) |
| Stage 9 | `pytest tests/test_stage9_heartsteps_preprocessing.py tests/test_stage9_external_cf.py tests/test_collaborative_ranking.py -q` | 74 passed in 4.41s (69 baseline + 5 new) |
| Full unit regression | `pytest -m "not integration and not live_model" -q` | 329 passed, 13 deselected, 1 warning (324 baseline + 5 new) |
| Safe integration (live ES) | `pytest -m integration -q` | 13 passed in 57.63s (13/342 collected; actual current executed count) |
| Lint | `ruff check src/weilv/collaborative_ranking.py tests/test_collaborative_ranking.py` | All checks passed |

Notes:
- No failing relevant test was hidden or deselected.
- The earlier Stage 9 PRECHECK report recorded 5 live-ES integration passes with
  a different command; the actual current executed command is
  `pytest -m integration` with 13 passed.
- `--formal` was never run; no Delta_V, no CI, no CR-CF-001 evaluation.
