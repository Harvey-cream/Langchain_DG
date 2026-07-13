"""LangGraph Agent 核心：Workflow（skill_recall）+ Agent（model ↔ tools）、checkpoint、流式事件。

START → skill_recall（Skill 向量路由 + RAG 门控 LLM + 按需检索）→ agent → tools → agent …
两个 Agent 共用 `build_agent_graph`，差异在 tools、system_prompt、recall_mode。
"""
from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command
from typing_extensions import TypedDict

from Agent_memory.memory import maybe_compress_history
from human_in_the_loop.human_loop import interrupt_payload_from_updates
from backend_langchain.logger_func import log_warning_event

# 兼容直接以脚本方式运行（cwd=backend_langchain）时的包路径。
if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from common.skill_router import prepare_turn_context
from config.config import QUERY_REWRITE_CONTEXT_TURNS, get_qwen_chat_model

RecallModeParam = Literal["main", "interview"]

logger = logging.getLogger(__name__)


# =============================================================================
# Checkpointer（AsyncSqliteSaver，主/面试按 thread_id 分区共享一份）
# =============================================================================

CHECKPOINT_SQLITE_PATH = Path(__file__).resolve().parent / "data" / "langgraph_checkpoints.sqlite3"
_checkpointer: AsyncSqliteSaver | None = None
_checkpointer_ctx: Any = None


async def init_checkpointer() -> AsyncSqliteSaver:
    global _checkpointer, _checkpointer_ctx
    if _checkpointer is None:
        CHECKPOINT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _checkpointer_ctx = AsyncSqliteSaver.from_conn_string(str(CHECKPOINT_SQLITE_PATH))
        _checkpointer = await _checkpointer_ctx.__aenter__()
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer, _checkpointer_ctx
    if _checkpointer_ctx is not None:
        await _checkpointer_ctx.__aexit__(None, None, None)
    _checkpointer = None
    _checkpointer_ctx = None


def get_checkpointer() -> AsyncSqliteSaver:
    if _checkpointer is None:
        raise RuntimeError("checkpointer 未初始化，请在应用 lifespan 中调用 init_checkpointer()")
    return _checkpointer


def agent_checkpoint_thread_id(user_id: int, conversation_id: int) -> str:
    return f"agent:{user_id}:{conversation_id}"


def interview_checkpoint_thread_id(user_id: int, conversation_id: int) -> str:
    return f"interview:{user_id}:{conversation_id}"


# =============================================================================
# 工具函数
# =============================================================================


def message_content_to_text(content: Any) -> str:
    """LangChain 消息 content 可能是 str 或多模态 block 列表，统一抽成纯文本。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
        return "".join(parts)
    return str(content)


def _graph_recursion_limit() -> int:
    """封顶 LangGraph 步数：每轮约 model+tool 两步，默认够 6 轮工具调用，可用环境变量覆盖。"""
    raw = os.getenv("AGENT_RECURSION_LIMIT", "").strip()
    if raw.isdigit():
        return max(4, int(raw))
    return 16


def _graph_config(thread_id: str) -> dict[str, Any]:
    return {"recursion_limit": _graph_recursion_limit(), "configurable": {"thread_id": thread_id}}


# =============================================================================
# Workflow + Agent 图：skill_recall → agent ↔ tools
# =============================================================================


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    skill_name: str
    skill_context: str
    retrieved_context: str


def _latest_user_text(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return message_content_to_text(msg.content).strip()
    return ""


def format_recent_dialogue(
    messages: list[BaseMessage],
    *,
    max_turns: int | None = None,
) -> str:
    """最近若干轮用户/助手对话，供检索问句改写补全指代。"""
    cap = QUERY_REWRITE_CONTEXT_TURNS if max_turns is None else max(0, max_turns)
    if cap <= 0 or not messages:
        return ""

    trimmed = messages
    if trimmed and isinstance(trimmed[-1], HumanMessage):
        trimmed = trimmed[:-1]
    if not trimmed:
        return ""

    turns: list[tuple[str, str]] = []
    pending_user = ""
    for msg in trimmed:
        if isinstance(msg, HumanMessage):
            if pending_user:
                turns.append((pending_user, ""))
            pending_user = message_content_to_text(msg.content).strip()
        elif isinstance(msg, AIMessage):
            ai = message_content_to_text(msg.content).strip()
            if pending_user:
                turns.append((pending_user, ai))
                pending_user = ""
    if pending_user:
        turns.append((pending_user, ""))

    lines: list[str] = []
    for user, assistant in turns[-cap:]:
        if user:
            lines.append(f"用户：{user}")
        if assistant:
            lines.append(f"助手：{assistant[:600]}")
    return "\n".join(lines)


def build_agent_graph(
    *,
    tools: Sequence[Any],
    system_prompt: str,
    recall_mode: RecallModeParam,
    temperature: float = 0.45,
    streaming: bool = False,
) -> CompiledStateGraph:
    """编译 LangGraph：START 后固定 skill_recall，再 agent ↔ tools（MCP/PDF）。"""
    tools_list = list(tools)
    model = get_qwen_chat_model(temperature=temperature, streaming=streaming)
    if tools_list:
        model = model.bind_tools(tools_list)
    system_message = SystemMessage(content=system_prompt)

    async def skill_recall_node(state: AgentState) -> dict[str, str]:
        user_text = _latest_user_text(state["messages"])
        if not user_text:
            return {"skill_name": "", "skill_context": "", "retrieved_context": ""}

        writer = get_stream_writer()

        def _on_search() -> None:
            writer({"type": "status", "text": "正在搜索..."})

        spec, skill_context, retrieved = await prepare_turn_context(
            user_text,
            mode=recall_mode,  # type: ignore[arg-type]
            recent_dialogue=format_recent_dialogue(state["messages"]),
            on_search=_on_search,
        )
        return {
            "skill_name": spec.name if spec else "",
            "skill_context": skill_context,
            "retrieved_context": retrieved,
        }

    async def agent_node(state: AgentState) -> dict[str, list[BaseMessage]]:
        prefix: list[BaseMessage] = [system_message]
        if sc := (state.get("skill_context") or "").strip():
            prefix.append(SystemMessage(content=sc))
        if rc := (state.get("retrieved_context") or "").strip():
            prefix.append(
                SystemMessage(content=f"【检索参考（内部，勿照抄原文）】\n{rc}")
            )
        gathered: BaseMessage | None = None
        async for chunk in model.astream(prefix + state["messages"]):
            if text := message_content_to_text(getattr(chunk, "content", None)):
                get_stream_writer()({"type": "delta", "text": text})
            gathered = chunk if gathered is None else gathered + chunk  # type: ignore[operator]
        if gathered is None:
            return {"messages": []}
        return {"messages": [gathered]}

    builder = StateGraph(AgentState)
    builder.add_node("skill_recall", skill_recall_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools_list))
    builder.add_edge(START, "skill_recall")
    builder.add_edge("skill_recall", "agent")
    builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=get_checkpointer())


# =============================================================================
# 异步流式：custom（节点/工具 writer）+ updates（interrupt）
# =============================================================================


async def _compress_history_safely(agent: CompiledStateGraph, thread_id: str) -> None:
    try:
        await maybe_compress_history(agent, thread_id=thread_id)
    except Exception as e:  # noqa: BLE001
        log_warning_event(logger, "memory_compress_skipped", thread_id=thread_id, error=str(e))


async def stream_graph_chat_model_events(
    agent: CompiledStateGraph,
    *,
    prompt_text: str = "",
    thread_id: str,
    resume_pdf: bool | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """流式产出事件：delta / status / interrupt / pdf_ready（custom + updates）。"""
    if resume_pdf is not None:
        graph_input: Any = Command(resume=resume_pdf)
    else:
        await _compress_history_safely(agent, thread_id)
        graph_input = {
            "messages": [HumanMessage(content=prompt_text)],
            "skill_name": "",
            "skill_context": "",
            "retrieved_context": "",
        }

    seen_pdf: set[tuple[str, str]] = set()

    async for mode, payload in agent.astream(
        graph_input, _graph_config(thread_id), stream_mode=["custom", "updates"]
    ):
        if mode == "custom" and isinstance(payload, dict):
            t = payload.get("type")
            if t in ("status", "delta") and payload.get("text") is not None:
                yield {"type": t, "text": str(payload["text"])}
            elif t == "pdf_ready" and payload.get("url"):
                key = (str(payload["url"]), str(payload.get("filename") or "export.pdf"))
                if key in seen_pdf:
                    continue
                seen_pdf.add(key)
                yield {"type": "pdf_ready", "url": key[0], "filename": key[1]}
            continue

        if mode == "updates":
            intr = interrupt_payload_from_updates(payload)
            if intr:
                yield {"type": "interrupt", **intr}


def warmup_agent_executors(*, temperature: float = 0.45) -> None:
    """进程启动时预热三张流式图（主对话本地/联网 + 面试），避免首请求冷启动。"""
    from Langchain_Agent import runtime

    runtime.reset_stream_agent_cache()
    runtime.get_stream_agent_executor(temperature=temperature, enable_web_search=False)
    runtime.get_stream_agent_executor(temperature=temperature, enable_web_search=True)
    runtime.get_stream_interview_executor(temperature=temperature)
