# Frozen Knowledge Retrieval Ablation Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run one frozen 24-case Knowledge Retrieval ablation comparing BM25, Vector, evaluation-only Hybrid-RRF, and production-compatible Hybrid+Reranker without changing Gold, corpus, or production semantics.

**Architecture:** Add one evaluation-only runner that imports production BM25, Vector, Knowledge filters, candidate merge/dedup, embedding, and reranker boundaries. The runner validates frozen hashes before calls, executes each query with exactly one query embedding and one reranker call, computes per-case then macro metrics, and writes immutable raw results plus paper/provenance/claim artifacts. RRF and metric/bootstrap utilities remain in the evaluation runner only.

**Tech Stack:** Python 3.12, pytest, Elasticsearch 8.x client, existing DashScope wrappers, standard-library CSV/JSON/statistics/random/hashlib.

## Global Constraints

- Gold SHA-256 must remain `2fb07424641826c98f2c722e3e13dedf5a95c12fccad726fa32ddb9f3f9599b0`.
- Corpus SHA-256 must remain `e04e27a27175211d32c57f36b715bc19faf45ca6be7ccd8e993a86a668392938` with 27 eligible chunks.
- `BM25_RECALL_K = 10`, `VECTOR_RECALL_K = 10`, `RRF_K = 60`; no tuning.
- Use `text-embedding-v4`, 1024 dimensions, cosine similarity, and `qwen3-rerank` from production sources.
- One query embedding and at most one reranker call per case; qwen-plus calls are always zero.
- RRF is evaluation-only and must not be imported by or added to `src/`.
- Do not modify production code, Knowledge, MicroTasks, Safety, Personal RAG, API, UI, Gold, or corpus.
- No Git worktree is available because this workspace is not a Git repository; changes are restricted to the explicitly allowed evaluation runner, targeted test, plan, claim registry, and run artifacts.

---

### Task 1: Evaluation contracts and metric utilities

**Files:**
- Create: `tests/test_retrieval_ablation_evaluation.py`
- Create: `evaluation/runners/run_retrieval_ablation_evaluation.py`

**Interfaces:**
- Consumes: frozen Gold JSONL, corpus manifest, formal corpus JSONL.
- Produces: `load_frozen_inputs`, `reciprocal_rank_fusion`, `calculate_ranking_metrics`, `hybrid_candidate_pool_recall`, `bootstrap_paired_ci`.

- [ ] **Step 1: Write failing tests for frozen loading, RRF, and metrics**

  Add literal fixtures that require 24 loaded cases, exact frozen hashes, deterministic RRF ordering with `RRF_K=60`, graded nDCG gains `3/1/0`, ordinary Recall over relevance `>=1`, DirectRecall over relevance `==2`, and deduplicated candidate pool recall.

- [ ] **Step 2: Run tests to verify RED**

  Run: `uv run python -m pytest tests/test_retrieval_ablation_evaluation.py -q`

  Expected: collection failure because `evaluation.runners.run_retrieval_ablation_evaluation` does not exist.

- [ ] **Step 3: Implement minimal contract and metric functions**

  The loader must recompute exact Gold file SHA and canonical eligible-corpus SHA before returning cases. RRF must use `1/(60+rank)` per available route and sort by score descending, best source rank ascending, then `chunk_id` ascending. Metrics must return per-case Recall@1/3/5/10, DirectRecall@1/3/5/10, MRR@10, and nDCG@3/5/10.

- [ ] **Step 4: Run tests to verify GREEN**

  Run: `uv run python -m pytest tests/test_retrieval_ablation_evaluation.py -q`

  Expected: contract and metric tests pass.

### Task 2: Production-compatible case execution and call budget

**Files:**
- Modify: `tests/test_retrieval_ablation_evaluation.py`
- Modify: `evaluation/runners/run_retrieval_ablation_evaluation.py`

**Interfaces:**
- Consumes: one Gold case, Elasticsearch client, API key, injected production-compatible callables for tests.
- Produces: `execute_case` raw record containing route rankings, full deduplicated pool, RRF and rerank rankings, per-method metrics, latency, and call counts.

- [ ] **Step 1: Write failing execution test**

  Use complete fake BM25/Vector hits and external-call fakes. Assert exactly one query embedding, one rerank, zero qwen-plus, Top-K sizes no greater than 10, production Knowledge filters passed to both routes, production merge order/dedup used, and all required raw fields present.

- [ ] **Step 2: Run the focused test to verify RED**

  Run: `uv run python -m pytest tests/test_retrieval_ablation_evaluation.py -q`

  Expected: failure because `execute_case` is missing.

- [ ] **Step 3: Implement minimal execution adapter**

  Call production `bm25_search(..., size=10, raw_filters=_knowledge_filters())`, one `embed_texts([query], text_type="query")`, production `vector_search(..., size=10, raw_filters=...)`, production `merge_candidates`, evaluation-only RRF, then one `rerank_texts` over the complete union and production `apply_rerank`. Validate complete unique rerank indices and preserve full rankings/scores.

- [ ] **Step 4: Run the focused tests to verify GREEN**

  Run: `uv run python -m pytest tests/test_retrieval_ablation_evaluation.py -q`

  Expected: all targeted tests pass.

### Task 3: Run aggregation, artifacts, provenance, and claims

**Files:**
- Modify: `tests/test_retrieval_ablation_evaluation.py`
- Modify: `evaluation/runners/run_retrieval_ablation_evaluation.py`
- Create before live calls: `evaluation/claims/claim_registry_retrieval_v1.csv`

**Interfaces:**
- Consumes: 24 `execute_case` records.
- Produces: macro metrics, paired deltas, 10,000-resample paired bootstrap CIs, p50/p95 latency, paper table, provenance, and mechanically evaluated claims.

- [ ] **Step 1: Write failing aggregation/artifact tests**

  Assert macro averaging is over 24 case values, paired differences expose absolute and nullable relative differences, bootstrap uses case resampling with seed `20260816`, claims map actual metrics to `SUPPORTED`/`MIXED`/`NOT_SUPPORTED`, and `CR-RET-REAL-001` is always `UNSUPPORTED`.

- [ ] **Step 2: Run tests to verify RED**

  Run: `uv run python -m pytest tests/test_retrieval_ablation_evaluation.py -q`

  Expected: failures for missing aggregation and artifact functions.

- [ ] **Step 3: Implement aggregation and writers**

  Write `per_case_results.jsonl`, long `metrics.csv`, structured `metrics.json`, `paper_metrics.csv` with provenance `A+B+C`, `retrieval_ablation_table.csv`, `paired_improvements.csv`, `provenance.json`, and the final claim registry. Provenance hashes the production source tree, runner, `uv.lock`, Gold, and corpus; marks RRF evaluation-only and latency non-primary.

- [ ] **Step 4: Run tests to verify GREEN**

  Run: `uv run python -m pytest tests/test_retrieval_ablation_evaluation.py -q`

  Expected: all targeted tests pass with no warnings or unrelated tests.

### Task 4: Live frozen evaluation and final verification

**Files:**
- Create: `evaluation/runs/<run_id>/per_case_results.jsonl`
- Create: `evaluation/runs/<run_id>/metrics.csv`
- Create: `evaluation/runs/<run_id>/metrics.json`
- Create: `evaluation/runs/<run_id>/paper_metrics.csv`
- Create: `evaluation/runs/<run_id>/retrieval_ablation_table.csv`
- Create: `evaluation/runs/<run_id>/paired_improvements.csv`
- Create: `evaluation/runs/<run_id>/provenance.json`
- Update: `evaluation/claims/claim_registry_retrieval_v1.csv`

**Interfaces:**
- Consumes: live Elasticsearch formal index and configured DashScope key.
- Produces: one completed immutable run with 24 embedding calls, 24 reranker calls, and zero qwen-plus calls.

- [ ] **Step 1: Pre-register claim rows as PENDING**

  Create all four required claim IDs and exact claim text before any live query/model call.

- [ ] **Step 2: Run targeted tests once more**

  Run: `uv run python -m pytest tests/test_retrieval_ablation_evaluation.py -q`

  Expected: PASS.

- [ ] **Step 3: Execute the live runner exactly once**

  Run: `uv run python -m evaluation.runners.run_retrieval_ablation_evaluation`

  Expected: one new run directory, 24 successful cases, exactly 24 query embedding calls and 24 reranker calls.

- [ ] **Step 4: Verify artifacts without model calls**

  Run: `uv run python -m evaluation.runners.run_retrieval_ablation_evaluation --verify-run evaluation/runs/<run_id>`

  Expected: `validation_status=PASS`, zero failed cases, frozen hashes unchanged, all 24 cases included, metrics recomputed from raw rankings, claim statuses consistent, and no model calls during verification.

- [ ] **Step 5: Run formatting and targeted tests**

  Run: `uv run ruff check evaluation/runners/run_retrieval_ablation_evaluation.py tests/test_retrieval_ablation_evaluation.py`

  Run: `uv run pytest tests/test_retrieval_ablation_evaluation.py -q`

  Expected: both commands pass.

## Plan Self-Review

- Spec coverage: frozen hash gates, four methods, fixed constants, full raw rankings, all requested metrics, paired deltas, bootstrap CI, latency diagnostics, provenance, anti-cherry-picking, claims, call budgets, and output artifacts are assigned above.
- Placeholder scan: no TBD/TODO/implement-later placeholders.
- Type consistency: the same case/result/metric names flow from `execute_case` through aggregation, writers, and verification.
