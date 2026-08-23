# Stage 7A.1 Deterministic Test Summary

## New tests (`tests/test_stage7a1_agentic_guard_compat.py`) — 9 passed

Prompt-contract proofs (mock `Generation.call`, assert prompt content):
- `test_prompt_forbids_repeating_user_query_quantities`
- `test_prompt_uses_qualitative_wording_for_user_time_constraints`
- `test_prompt_targets_120_chars_below_guard_limit`
- `test_prompt_forbids_new_task_and_prescription`
- `test_prompt_still_requires_factor_evidence_and_personalization_coverage`
- `test_prompt_reminds_user_message_numbers_are_for_understanding_only`

Frozen Guard compatibility (real `validate_explanation_output`):
- `test_compliant_explanation_passes_frozen_guard_with_5_minutes_in_query`
  — query/factor contain "5分钟", task+evidence do NOT support it, compliant
  explanation without the number → `passed=True`, `reason_codes=[]`.
- `test_explanation_repeating_unsupported_5_minutes_is_rejected_by_frozen_guard`
  — negative control: explanation repeating "5分钟" → `passed=False`,
  `adds_unsupported_quantity` present.
- `test_mocked_compliant_explanation_round_trips_through_real_guard`
  — mocked compliant explanation returned by `compose_agentic_explanation`
  passes the real frozen Guard end to end.

## Existing Agentic / Guard tests — unchanged and passing

`tests/test_agentic_rag.py`, `tests/test_agentic_api.py`,
`tests/test_dashscope_models.py`, `tests/test_output_guard.py`:
37 passed (includes the 9 new above).

Existing Guard tests in `tests/test_output_guard.py` were NOT modified.

## Full offline suite

`uv run python -m pytest -q` → **256 passed, 0 failed, 0 errors** (247 Stage 7A
baseline + 9 new). One pre-existing Starlette/httpx deprecation warning only.

## Static checks

- `uv run ruff check src/weilv/dashscope_models.py tests/test_stage7a1_agentic_guard_compat.py`
  → All checks passed!
- `uv lock --check` → Resolved 95 packages, OK.
