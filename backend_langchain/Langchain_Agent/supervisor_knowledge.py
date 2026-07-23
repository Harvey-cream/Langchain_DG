"""企业知识库线总控 Graph：LLM 分诊 → 挂载各子 Agent 自有子图。

不写长答案；子 Agent 说明书见 knowledge_subagents。与面试线隔离。
"""
from __future__ import annotations

import logging
from typing import Literal

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field

from backend_langchain.logger_func import log_info_event, log_warning_event
from common.agent import AgentState, message_content_to_text
from common.checkpointer import get_checkpointer
from config.config import get_qwen_chat_model
from Langchain_Agent.agents.doc_summary import build_doc_summary_graph
from Langchain_Agent.agents.knowledge_qa import build_knowledge_qa_graph
from Langchain_Agent.knowledge_subagents import (
    KNOWLEDGE_SUB_AGENTS,
    KnowledgeAgentId,
    render_sub_agents_for_router,
)

logger = logging.getLogger(__name__)

_ROUTER_SYSTEM = """你是「企业知识库AI助手」线的总控路由 Agent。
你的唯一任务：根据用户本轮意图，从下列子 Agent 中选择一个最合适的 id。
不要回答用户问题，不要解释，只做路由决策。

可选子 Agent：
{agents}
"""


class RouteDecision(BaseModel):
    agent_id: Literal["doc_summary", "knowledge_qa"] = Field(
        description="选中的子 Agent id"
    )


def _latest_user_text(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return message_content_to_text(msg.content).strip()
    return ""


def build_knowledge_supervisor_graph(
    *,
    temperature: float = 0.45,
    enable_web_search: bool = False,
) -> CompiledStateGraph:
    """编译知识库线总控：route(LLM) → doc_summary | knowledge_qa。"""
    summary_graph = build_doc_summary_graph(temperature=temperature)
    qa_graph = build_knowledge_qa_graph(
        temperature=temperature,
        enable_web_search=enable_web_search,
    )
    agents_block = render_sub_agents_for_router(KNOWLEDGE_SUB_AGENTS)
    router_system = _ROUTER_SYSTEM.format(agents=agents_block)
    valid_ids = {a.id for a in KNOWLEDGE_SUB_AGENTS}

    async def route_node(state: AgentState) -> Command:
        user_text = _latest_user_text(state["messages"])
        agent_id: KnowledgeAgentId = "knowledge_qa"
        if user_text:
            try:
                llm = get_qwen_chat_model(temperature=0.0, streaming=False)
                structured = llm.with_structured_output(RouteDecision)
                decision: RouteDecision = await structured.ainvoke(
                    [
                        SystemMessage(content=router_system),
                        HumanMessage(content=f"用户本轮消息：\n{user_text}"),
                    ]
                )
                picked = str(decision.agent_id or "").strip()
                if picked in valid_ids:
                    agent_id = picked  # type: ignore[assignment]
            except Exception as e:  # noqa: BLE001
                log_warning_event(
                    logger,
                    "knowledge_supervisor_route_failed",
                    error=str(e),
                    fallback="knowledge_qa",
                )
                agent_id = "knowledge_qa"

        preview = user_text.replace("\n", " ")[:120]
        log_info_event(
            logger,
            "knowledge_supervisor_route",
            agent=agent_id,
            input=preview,
        )
        return Command(goto=agent_id, update={"next_agent": agent_id})

    builder = StateGraph(AgentState)
    builder.add_node("route", route_node)
    builder.add_node("doc_summary", summary_graph)
    builder.add_node("knowledge_qa", qa_graph)
    builder.add_edge(START, "route")
    builder.add_edge("doc_summary", END)
    builder.add_edge("knowledge_qa", END)
    return builder.compile(checkpointer=get_checkpointer())
