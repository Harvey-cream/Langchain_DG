"""Review execution order. No database transactions or document extraction here."""

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from . import nodes
from .state import ReviewState, ReviewRuntime
from .tools import REVIEW_TOOLS


def after_decision(state: ReviewState):
    return "tools" if state["tools_pending"] else "generate_findings"


def after_generation(state: ReviewState):
    return (
        "retrieve_baseline"
        if state["window_index"] < len(state["windows"])
        else "quality_gate"
    )


def build_review_graph():
    graph = StateGraph(ReviewState, context_schema=ReviewRuntime)
    graph.add_node("prepare_windows", nodes.prepare_windows)
    graph.add_node("retrieve_baseline", nodes.retrieve_baseline)
    graph.add_node("agent_decide", nodes.agent_decide)
    graph.add_node("tools", ToolNode(REVIEW_TOOLS, handle_tool_errors=False))
    graph.add_node("generate_findings", nodes.generate_findings)
    graph.add_node("quality_gate", nodes.quality_gate)
    graph.add_edge(START, "prepare_windows")
    graph.add_edge("prepare_windows", "retrieve_baseline")
    graph.add_edge("retrieve_baseline", "agent_decide")
    graph.add_conditional_edges(
        "agent_decide", after_decision, ["tools", "generate_findings"]
    )
    graph.add_edge("tools", "agent_decide")
    graph.add_conditional_edges(
        "generate_findings", after_generation, ["retrieve_baseline", "quality_gate"]
    )
    graph.add_edge("quality_gate", END)
    return graph.compile()
