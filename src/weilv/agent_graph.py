"""The fixed Stage 7A LangGraph topology."""

from langgraph.graph import END, START, StateGraph

from weilv.agentic_rag import AgenticRagRuntime, AgenticState


def _safety_route(state: AgenticState) -> str:
    return "terminal" if state["safety_status"] in {"blocked", "help_seeking"} else "continue"


def build_agent_graph(runtime: AgenticRagRuntime):
    graph = StateGraph(AgenticState)
    graph.add_node("input_safety", runtime.input_safety)
    graph.add_node("terminal_response", runtime.terminal_response)
    graph.add_node("analyze_problem", runtime.analyze_problem)
    graph.add_node("retrieve_factor_knowledge", runtime.retrieve_factor_knowledge)
    graph.add_node("retrieve_agentic_tasks", runtime.retrieve_agentic_tasks)
    graph.add_node("retrieve_user_memory", runtime.retrieve_user_memory)
    graph.add_node("apply_personalization", runtime.apply_personalization)
    graph.add_node("select_and_ground", runtime.select_and_ground)
    graph.add_node("compose_explanation", runtime.compose_explanation)
    graph.add_node("output_guard", runtime.output_guard)

    graph.add_edge(START, "input_safety")
    graph.add_conditional_edges(
        "input_safety",
        _safety_route,
        {"terminal": "terminal_response", "continue": "analyze_problem"},
    )
    graph.add_edge("terminal_response", END)
    graph.add_edge("analyze_problem", "retrieve_factor_knowledge")
    graph.add_edge("retrieve_factor_knowledge", "retrieve_agentic_tasks")
    graph.add_edge("retrieve_agentic_tasks", "retrieve_user_memory")
    graph.add_edge("retrieve_user_memory", "apply_personalization")
    graph.add_edge("apply_personalization", "select_and_ground")
    graph.add_edge("select_and_ground", "compose_explanation")
    graph.add_edge("compose_explanation", "output_guard")
    graph.add_edge("output_guard", END)
    return graph.compile()
