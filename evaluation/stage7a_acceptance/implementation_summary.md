# Stage 7A Implementation Summary

- LangGraph: `1.2.11`, real compiled `StateGraph`, no checkpointer.
- Fixed nodes: `input_safety`, `terminal_response`, `analyze_problem`, `retrieve_factor_knowledge`, `retrieve_agentic_tasks`, `retrieve_user_memory`, `apply_personalization`, `select_and_ground`, `compose_explanation`, `output_guard`.
- API: `POST /api/v1/recommend/agentic`; existing `POST /api/v1/recommendations` remains unchanged.
- Runtime LLM: `qwen-plus`; embedding: `text-embedding-v4` at 1024 dimensions; reranker: `qwen3-rerank`.
- Safety: production `_safety_context`, `evaluate_input_risk`, and `select_safe_tasks` reused. Terminal input safety prevents all downstream retrieval/model calls.
- Retrieval: production BM25/vector merge and rerank helpers reused with frozen Top10/Top10/Top5 semantics. Agentic task recall unions original plus factor queries, limits IDs to the formal 23-task corpus, then applies metadata and Safety before one final rerank.
- Personal RAG: production memory retrieval and `personalize_task_candidates` reused. Candidate-set equality is fail-closed and frozen weights/clamp/tie order are unchanged.
- Evidence and Guard: production `load_task_evidence` exact-ID validation and `validate_explanation_output` reused. Invalid evidence prevents explanation; rejected explanation uses the existing safe terminal wording.
- Privacy: diagnostics contain IDs, counts, rankings, statuses, factor domains, and model-call counts only. Raw query, factor subqueries, raw memory values, prompts, and secrets are not logged.
- Formal data: no changes to Stage 6 Gold, formal tasks, knowledge corpus, or Safety metadata.

