# Safety Rules v0.1 Design

## Scope

Stage 1 adds a machine-executable, non-RAG safety rule set and a minimal pure-function evaluator. It does not implement recommendation retrieval, ranking, APIs, UI, or Stage 3.

## Data

`data/metadata/safety_rules_v0.1.json` has top-level `schema_version: "1.0"` and exactly 12 enabled rules. Every rule contains `rule_id`, `name`, `category`, `priority`, `conditions`, `actions`, `applicable_domains`, `evidence_chunk_ids`, `enabled`, and `version`. Rules execute deterministically by priority (`critical`, `high`, `normal`) then `rule_id`.

## Public interfaces

- `load_safety_rules(path=...)` validates and returns sorted enabled rules.
- `evaluate_input_risk(context, rules=None)` handles only structured input-level risks.
- `filter_task_by_safety(task, context, rules=None)` evaluates one task only.
- `select_safe_tasks(tasks, context, rules=None)` aggregates input risk and per-task filtering; it does not retrieve, rank, score, or create tasks.

Every evaluation returns `status`, `matched_rule_ids`, and `reason_codes`. Status is one of `allowed`, `blocked`, `help_seeking`, or `no_safe_task`.

## Input contract

The caller supplies explicit booleans/enums and already-matched contraindication or stop-condition task IDs. The module does not interpret natural language or make medical judgments. High-priority input risks run before task filtering or any downstream ranking.

## Verification

Targeted unit tests cover the 12 required scenarios, deterministic rule order, schema/evidence validation, and unchanged Elasticsearch counts. No model API is called.
