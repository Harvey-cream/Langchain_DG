"""文档摘要子图：本 Agent 自有节点与边（结构先独立，业务可再演进）。

当前流程：START → skill_recall → agent → END（无工具节点）。
"""
from __future__ import annotations

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.graph_factory import (
    AgentState,
    _messages_with_transient_attachments,
    format_recent_dialogue,
    message_content_to_text,
)
from agent.rag.skill_router import DOC_SUMMARY_SKILLS, prepare_turn_context
from config.config import get_qwen_chat_model
from agent.runtime.prompts_knowledge import SUMMARY_SYSTEM_PREFIX


def _latest_user_text(messages: list[BaseMessage]) -> str:
    from langchain_core.messages import HumanMessage

    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return message_content_to_text(msg.content).strip()
    return ""


def _user_id_from_config(config: RunnableConfig) -> int | None:
    cfg = config.get("configurable") or {}
    tid = str(cfg.get("thread_id") or "")
    parts = tid.split(":")
    if len(parts) >= 2 and parts[0] == "agent":
        try:
            return int(parts[1])
        except ValueError:
            return None
    return None


def build_doc_summary_graph(*, temperature: float = 0.45) -> CompiledStateGraph:
    """编译文档摘要子图（由总控挂载，不自带 checkpointer）。"""
    model = get_qwen_chat_model(temperature=temperature, streaming=True)
    system_message = SystemMessage(content=SUMMARY_SYSTEM_PREFIX)

    async def skill_recall(state: AgentState, config: RunnableConfig) -> dict[str, str]:
        user_text = _latest_user_text(state["messages"])
        if not user_text:
            return {"skill_name": "", "skill_context": "", "retrieved_context": ""}

        writer = get_stream_writer()

        def _on_search() -> None:
            writer({"type": "status", "text": "正在搜索..."})

        spec, skill_context, retrieved = await prepare_turn_context(
            user_text,
            mode="main",
            recent_dialogue=format_recent_dialogue(state["messages"]),
            on_search=_on_search,
            user_id=_user_id_from_config(config),
            skills=DOC_SUMMARY_SKILLS,
        )
        return {
            "skill_name": spec.name if spec else "",
            "skill_context": skill_context,
            "retrieved_context": retrieved,
        }

    async def agent(state: AgentState, config: RunnableConfig) -> dict[str, list[BaseMessage]]:
        prefix: list[BaseMessage] = [system_message]
        if sc := (state.get("skill_context") or "").strip():
            prefix.append(SystemMessage(content=sc))
        if rc := (state.get("retrieved_context") or "").strip():
            prefix.append(SystemMessage(content=f"【检索参考（内部，勿照抄原文）】\n{rc}"))

        cfg = config.get("configurable") or {}
        messages = _messages_with_transient_attachments(
            state["messages"],
            cfg.get("attachments") if isinstance(cfg.get("attachments"), list) else None,
        )
        gathered: BaseMessage | None = None
        async for chunk in model.astream(prefix + messages):
            if text := message_content_to_text(getattr(chunk, "content", None)):
                get_stream_writer()({"type": "delta", "text": text})
            gathered = chunk if gathered is None else gathered + chunk  # type: ignore[operator]
        if gathered is None:
            return {"messages": []}
        return {"messages": [gathered]}

    builder = StateGraph(AgentState)
    builder.add_node("skill_recall", skill_recall)
    builder.add_node("agent", agent)
    builder.add_edge(START, "skill_recall")
    builder.add_edge("skill_recall", "agent")
    builder.add_edge("agent", END)
    return builder.compile()
