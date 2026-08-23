# Stage 7A Agentic RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development. This workspace is not a Git repository, so no worktree or commit steps are possible.

**Goal:** Implement the fixed Stage 7A LangGraph Agentic RAG path without changing frozen Stage 6 behavior or formal data.

**Architecture:** Keep Basic and Personal production paths byte-untouched. Add focused Agentic orchestration and graph modules, two narrow qwen-plus model calls, and a separate FastAPI endpoint.

**Tech Stack:** Python 3.12, LangGraph `StateGraph`, FastAPI, Pydantic, Elasticsearch, DashScope, pytest, uv.

## Global Constraints

- No loops, replanning, checkpointer, web browsing, arbitrary tools, or task generation.
- Maximum four factors and one decomposition call.
- Only the 23 reviewed `micro_tasks_v1` tasks may be selected.
- Frozen retrieval sizes, models, personalization scoring, evidence validation, Safety, and Output Guard remain unchanged.
- Diagnostics and logs exclude raw health text, raw memory values, secrets, and internal prompts.

---

### Task 1: Dependency and frozen baseline

**Files:** Modify `pyproject.toml`, `uv.lock` only through `uv add langgraph`.

- [ ] Record Safety Gold raw SHA and canonical task-corpus SHA using the existing Stage 6 verifier.
- [ ] Add the current compatible stable LangGraph package with uv.
- [ ] Verify `uv lock --check` and print the installed LangGraph version.

### Task 2: Agentic core tests and implementation

**Files:** Create `tests/test_agentic_rag.py`, `src/weilv/agentic_rag.py`, `src/weilv/agent_graph.py`; modify `src/weilv/dashscope_models.py`.

**Interfaces:** `run_agentic_rag(request, user_id, client, api_key) -> dict`; `build_agent_graph(runtime) -> CompiledStateGraph`.

- [ ] Write tests for safety terminal call counts, valid/invalid decomposition, ordered factor knowledge, task union dedupe/filter/rerank, memory disabled, candidate invariance/personal ranking, exact evidence failure, and guard fallback.
- [ ] Run `uv run pytest tests/test_agentic_rag.py -q` and verify failures are missing Agentic symbols.
- [ ] Implement only the fixed nodes and conditional edge required by those tests.
- [ ] Re-run the Agentic tests until green, then run Basic/Personal/Safety/Guard regression tests.

### Task 3: API test and endpoint

**Files:** Create `tests/test_agentic_api.py`; modify `src/weilv/api/schemas.py`, `src/weilv/api/app.py`.

**Interfaces:** `POST /api/v1/recommend/agentic` accepts `RecommendationRequest` and returns the compatible recommendation fields plus optional Agentic diagnostics.

- [ ] Write a failing API test proving the separate route calls only the Agentic core and preserves diagnostics.
- [ ] Run the test and verify the route is absent.
- [ ] Add the smallest schema and route implementation, reusing the existing safe interaction-log shape.
- [ ] Run Agentic API and existing API tests until green.

### Task 4: Regression, smoke, and acceptance bundle

**Files:** Create acceptance summaries under `evaluation/stage7a_acceptance/` and `evaluation/stage7a_acceptance_bundle.zip`.

- [ ] Run all deterministic tests and store the concise pass/fail summary.
- [ ] Recompute both frozen hashes and record exact results.
- [ ] Health-check Elasticsearch and DashScope without exposing secrets; if healthy, run exactly three specified smoke cases and delete the isolated evaluation memory.
- [ ] Record graph nodes/version, max observed model-call counts, implementation summary, and smoke result or `NOT_RUN` reason.
- [ ] Zip only Ticket-listed acceptance files and compute SHA-256.

