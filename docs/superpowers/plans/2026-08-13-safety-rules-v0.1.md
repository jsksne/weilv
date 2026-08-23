# Safety Rules v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 12 deterministic machine-executable safety rules and minimal pure-function evaluation interfaces.

**Architecture:** A versioned JSON file is the auditable source of truth. One dependency-free Python module loads and sorts rules, evaluates structured input risks, filters one task, and aggregates safe tasks without retrieval or ranking.

**Tech Stack:** Python 3.12 standard library, JSON, pytest.

## Global Constraints

- No LLM, Embedding, Reranker, natural-language medical interpretation, retrieval, or recommendation scoring.
- Status values are exactly `allowed`, `blocked`, `help_seeking`, and `no_safe_task`.
- Rule order is priority then rule_id; high-priority safety runs before downstream ranking.
- Do not modify the 29 knowledge documents or 23 micro-task documents.

---

### Task 1: Versioned rule data

**Files:**
- Create: `data/metadata/safety_rules_v0.1.json`
- Test: `tests/test_safety_rules.py`

**Interfaces:**
- Produces: JSON object with `schema_version` and `rules`.

- [ ] Write a failing schema/count/priority/evidence test.
- [ ] Run the targeted test and confirm failure.
- [ ] Add exactly SR-001 through SR-012 with the approved fields and evidence IDs.
- [ ] Run the targeted test and confirm pass.

### Task 2: Pure evaluation functions

**Files:**
- Create: `src/weilv/safety_rules.py`
- Test: `tests/test_safety_rules.py`

**Interfaces:**
- Produces: `load_safety_rules`, `evaluate_input_risk`, `filter_task_by_safety`, `select_safe_tasks`.
- Returns: dictionaries containing `status`, `matched_rule_ids`, and `reason_codes`; selection also includes `tasks`.

- [ ] Add failing tests for deterministic ordering and the 12 required behaviors.
- [ ] Run the targeted tests and confirm failure.
- [ ] Implement the smallest structured-field-only evaluator.
- [ ] Run the targeted tests and confirm pass.

### Task 3: Completion gate

**Files:**
- Verify: `data/metadata/health_knowledge_v1.jsonl`
- Verify: `data/metadata/micro_tasks_v1.jsonl`

**Interfaces:**
- Consumes: the rule file and pure functions from Tasks 1-2.

- [ ] Run Ruff on changed Python files.
- [ ] Run only `tests/test_safety_rules.py`.
- [ ] Validate every evidence ID against formal knowledge metadata.
- [ ] Read Elasticsearch counts and confirm 29 knowledge / 23 tasks.
- [ ] Confirm no model API code path was invoked and Stage 3 files were not added.
