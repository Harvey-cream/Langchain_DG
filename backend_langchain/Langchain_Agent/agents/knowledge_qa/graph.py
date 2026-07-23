"""知识问答子图：本 Agent 自有节点与边（结构先独立，业务可再演进）。

当前流程：START → skill_recall → agent ↔ tools → END。
开启联网搜索时：skill_recall 内强制调百炼 WebSearch，注入 web_context，并推送来源事件。
"""
from __future__ import annotations

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from common.agent import (
    AgentState,
    _messages_with_transient_attachments,
    format_recent_dialogue,
    message_content_to_text,
)
from common.skill_router import KNOWLEDGE_QA_SKILLS, prepare_turn_context
from common.web_search import forced_web_search, format_web_context
from config.config import get_qwen_chat_model
from Langchain_Agent.prompts_knowledge import AGENT_SYSTEM_PREFIX
from Langchain_Agent.tools.knowledge import get_all_agent_tools


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


def build_knowledge_qa_graph(
    *,
    temperature: float = 0.45,
    enable_web_search: bool = False,
) -> CompiledStateGraph:
    """编译知识问答子图（由总控挂载，不自带 checkpointer）。"""
    tools_list = get_all_agent_tools(enable_web_search=False)
    model = get_qwen_chat_model(temperature=temperature, streaming=True)
    if tools_list:
        model = model.bind_tools(tools_list)
    system_message = SystemMessage(content=AGENT_SYSTEM_PREFIX)

    async def skill_recall(state: AgentState, config: RunnableConfig) -> dict[str, str]:
        user_text = _latest_user_text(state["messages"])
        if not user_text:
            return {
                "skill_name": "",
                "skill_context": "",
                "retrieved_context": "",
                "web_context": "",
            }

        writer = get_stream_writer()
        web_context = ""

        if enable_web_search:
            writer({"type": "status", "text": "正在联网搜索..."})
            raw, sources = await forced_web_search(user_text)
            web_context = format_web_context(raw, sources)
            if sources:
                writer(
                    {
                        "type": "web_sources",
                        "sources": [s.as_dict() for s in sources],
                    }
                )
                writer({"type": "status", "text": "联网搜索完成"})
            elif raw:
                writer({"type": "status", "text": "联网搜索完成"})
            else:
                writer({"type": "status", "text": "联网搜索暂无结果，将仅依据知识库作答"})

        def _on_search() -> None:
            writer({"type": "status", "text": "正在搜索文档..."})

        spec, skill_context, retrieved = await prepare_turn_context(
            user_text,
            mode="main",
            recent_dialogue=format_recent_dialogue(state["messages"]),
            on_search=_on_search,
            user_id=_user_id_from_config(config),
            skills=KNOWLEDGE_QA_SKILLS,
        )
        return {
            "skill_name": spec.name if spec else "",
            "skill_context": skill_context,
            "retrieved_context": retrieved,
            "web_context": web_context,
        }

    async def agent(state: AgentState, config: RunnableConfig) -> dict[str, list[BaseMessage]]:
        prefix: list[BaseMessage] = [system_message]
        if sc := (state.get("skill_context") or "").strip():
            prefix.append(SystemMessage(content=sc))
        if rc := (state.get("retrieved_context") or "").strip():
            prefix.append(SystemMessage(content=f"【检索参考（内部，勿照抄原文）】\n{rc}"))
        if wc := (state.get("web_context") or "").strip():
            prefix.append(SystemMessage(content=wc))

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
    builder.add_node("tools", ToolNode(tools_list))
    builder.add_edge(START, "skill_recall")
    builder.add_edge("skill_recall", "agent")
    builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile()
