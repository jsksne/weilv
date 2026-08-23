# Stage 7A Test Summary

- New deterministic tests: 12 passed (`tests/test_agentic_rag.py`, `tests/test_agentic_api.py`).
- Frozen-core focused regression: 95 passed.
- Full repository suite: 247 passed, 0 failed, 0 errors.
- Warning: one pre-existing Starlette `TestClient` deprecation warning about the `httpx` compatibility shim.
- Static check: Ruff passed for all changed Python source and tests.
- Dependency lock: `uv lock --check` passed.
- Test command: `uv run python -m pytest -q`.

The direct `uv run pytest` executable was not used for the final count because it omits the workspace root from `sys.path` in this environment; the canonical module entrypoint imports the existing top-level `evaluation` and `scripts` packages correctly.

