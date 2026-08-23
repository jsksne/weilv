# Stage 7A Agentic RAG Design

## Goal

Add one production-compatible, loop-free LangGraph recommendation path that handles up to four explicit user factors while preserving the frozen Stage 6 retrieval, personalization, safety, evidence, and output-guard semantics.

## Architecture

- `weilv.agentic_rag` owns typed factor validation and the node implementations. It calls the existing production helpers from `basic_rag`, `retrieval`, `safety_rules`, `personal_memory_retrieval`, `personal_rag`, and `output_guard`; it does not copy their algorithms or change their constants.
- `weilv.agent_graph` owns a real compiled `langgraph.graph.StateGraph`. Runtime dependencies are captured by node closures, so API keys, clients, and raw memory values never enter graph state or diagnostics.
- `weilv.dashscope_models` gains exactly two qwen-plus boundaries: one structured decomposition call and one constrained Agentic explanation call. Both remain single-call operations.
- `weilv.api` gains `POST /api/v1/recommend/agentic`; the existing recommendation endpoint and response contract remain unchanged.

## Data flow and failure closure

Safety is the first node and conditionally routes terminal cases directly to the existing terminal-result semantics. Invalid decomposition becomes exactly one fallback factor without retry. Factor knowledge and task recall use the frozen BM25/vector/rerank functions and sizes. Metadata and Safety filter the union before one deterministic composite task rerank. Personalization can only reorder that eligible list, with set equality checked before continuing. Evidence must exactly match the selected task IDs or the graph returns the existing `no_safe_task` evidence-invalid result without explanation. The existing Output Guard validates the generated explanation and selects the existing safe fallback on rejection.

## Privacy and observability

State contains IDs, rankings, selected formal records, and transient retrieval content needed by downstream nodes. Public diagnostics contain only IDs, counts, statuses, factor domains, and model-call counts. Raw query, factor subqueries, raw memory values, API keys, prompts, and hidden reasoning are excluded from diagnostics and interaction logs.

## Verification

Deterministic tests cover Ticket A-L with external model and Elasticsearch boundaries mocked. Existing tests run unchanged. Stage 6 Safety Gold raw SHA-256 and the canonical task-corpus SHA-256 are checked before and after implementation. Live smoke runs exactly three cases only when both Elasticsearch and DashScope are healthy, and temporary evaluation memory is removed afterward.

