"""LangGraph Agent 核心：图工厂、流式事件；面试线仍用 `build_agent_graph`。

知识库线子 Agent 已迁至 `Langchain_Agent/agents/*`。
Checkpointer 见 `common.checkpointer`（此处再导出以兼容旧 import）。
"""
from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command
from typing_extensions import TypedDict

from Agent_memory.memory import maybe_compress_history
from Agent_memory.memory_persist import MemoryTurnContext
from human_in_the_loop.human_loop import interrupt_payload_from_updates
from backend_langchain.logger_func import log_warning_event

# 兼容直接以脚本方式运行（cwd=backend_langchain）时的包路径。
if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from common.checkpointer import (
    agent_checkpoint_thread_id,
    close_checkpointer,
    get_checkpointer,
    init_checkpointer,
    interview_checkpoint_thread_id,
)
from common.document_pipeline import extract_pdf_text_from_data_url
from common.skill_router import SkillSpec, prepare_turn_context
from config.config import QUERY_REWRITE_CONTEXT_TURNS, get_qwen_chat_model

RecallModeParam = Literal["main", "interview"]

logger = logging.getLogger(__name__)


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


_MAX_ATTACHMENT_TEXT_CHARS = 20_000


def _attachment_prompt_text(attachments: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for i, item in enumerate(attachments, start=1):
        kind = str(item.get("kind") or "").lower()
        name = str(item.get("name") or f"attachment-{i}").strip()
        mime = str(item.get("mime_type") or "").strip()
        if kind == "text":
            text = str(item.get("text") or "").strip()
            if text:
                parts.append(
                    f"附件 {i}: {name} ({mime or 'text/plain'})\n"
                    f"```text\n{text[:_MAX_ATTACHMENT_TEXT_CHARS]}\n```"
                )
        elif kind == "pdf":
            data_url = str(item.get("data_url") or "").strip()
            text = extract_pdf_text_from_data_url(data_url) if data_url else ""
            if text:
                parts.append(
                    f"附件 {i}: {name} ({mime or 'application/pdf'})\n"
                    f"```text\n{text[:_MAX_ATTACHMENT_TEXT_CHARS]}\n```"
                )
            elif data_url:
                parts.append(
                    f"附件 {i}: {name} ({mime or 'application/pdf'})"
                    " — 未能抽取到可读文本（可能为扫描件或空文档）。"
                )
        elif kind == "image":
            parts.append(f"附件 {i}: {name} ({mime or 'image/*'})，图片内容见随消息附带的 image_url。")
    if not parts:
        return ""
    return "【用户上传的附件，仅用于理解本轮问题】\n" + "\n\n".join(parts)


def _image_blocks(attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for item in attachments:
        if str(item.get("kind") or "").lower() != "image":
            continue
        url = str(item.get("data_url") or "").strip()
        if not url.startswith("data:image/"):
            continue
        blocks.append({"type": "image_url", "image_url": {"url": url}})
    return blocks


def _messages_with_transient_attachments(
    messages: list[BaseMessage],
    attachments: list[dict[str, Any]] | None,
) -> list[BaseMessage]:
    if not attachments:
        return messages
    attach_text = _attachment_prompt_text(attachments)
    image_blocks = _image_blocks(attachments)
    if not attach_text and not image_blocks:
        return messages

    out = list(messages)
    for idx in range(len(out) - 1, -1, -1):
        msg = out[idx]
        if not isinstance(msg, HumanMessage):
            continue
        text = message_content_to_text(msg.content).strip()
        merged_text = f"{text}\n\n{attach_text}".strip() if attach_text else text
        if image_blocks:
            out[idx] = HumanMessage(
                content=[{"type": "text", "text": merged_text or "请理解这些附件。"}, *image_blocks]
            )
        else:
            out[idx] = HumanMessage(content=merged_text)
        return out
    return messages


# =============================================================================
# Workflow + Agent 图：skill_recall → agent ↔ tools
# =============================================================================


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    skill_name: str
    skill_context: str
    retrieved_context: str
    web_context: str  # 用户开启联网搜索时强制检索注入；否则空
    next_agent: str  # 知识库总控写入；子图/面试可置空


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
    skills: tuple[SkillSpec, ...] | None = None,
    use_checkpointer: bool = True,
) -> CompiledStateGraph:
    """编译 LangGraph：START 后固定 skill_recall，再 agent ↔ tools（MCP/PDF）。

    use_checkpointer=False：作为总控图子节点挂载时由父图统一 checkpoint。
    """
    tools_list = list(tools)
    model = get_qwen_chat_model(temperature=temperature, streaming=streaming)
    if tools_list:
        model = model.bind_tools(tools_list)
    system_message = SystemMessage(content=system_prompt)
    skill_catalog = skills

    async def skill_recall_node(state: AgentState, config: RunnableConfig) -> dict[str, str]:
        user_text = _latest_user_text(state["messages"])
        if not user_text:
            return {"skill_name": "", "skill_context": "", "retrieved_context": ""}

        writer = get_stream_writer()

        def _on_search() -> None:
            writer({"type": "status", "text": "正在搜索..."})

        uid: int | None = None
        cfg = config.get("configurable") or {}
        tid = str(cfg.get("thread_id") or "")
        # thread_id = agent:{user_id}:{conversation_id}
        parts = tid.split(":")
        if len(parts) >= 2 and parts[0] == "agent":
            try:
                uid = int(parts[1])
            except ValueError:
                uid = None

        spec, skill_context, retrieved = await prepare_turn_context(
            user_text,
            mode=recall_mode,  # type: ignore[arg-type]
            recent_dialogue=format_recent_dialogue(state["messages"]),
            on_search=_on_search,
            user_id=uid if recall_mode == "main" else None,
            skills=skill_catalog,
        )
        return {
            "skill_name": spec.name if spec else "",
            "skill_context": skill_context,
            "retrieved_context": retrieved,
        }

    async def agent_node(state: AgentState, config: RunnableConfig) -> dict[str, list[BaseMessage]]:
        prefix: list[BaseMessage] = [system_message]
        if sc := (state.get("skill_context") or "").strip():
            prefix.append(SystemMessage(content=sc))
        if rc := (state.get("retrieved_context") or "").strip():
            prefix.append(
                SystemMessage(content=f"【检索参考（内部，勿照抄原文）】\n{rc}")
            )
        gathered: BaseMessage | None = None
        cfg = config.get("configurable") or {}
        messages = _messages_with_transient_attachments(
            state["messages"],
            cfg.get("attachments") if isinstance(cfg.get("attachments"), list) else None,
        )
        async for chunk in model.astream(prefix + messages):
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
    if use_checkpointer:
        return builder.compile(checkpointer=get_checkpointer())
    return builder.compile()


# =============================================================================
# 异步流式：custom（节点/工具 writer）+ updates（interrupt）
# =============================================================================


def _split_astream_item(item: Any) -> tuple[Any, Any]:
    """统一解包 astream 项。

    - stream_mode 为列表且 subgraphs=False → (mode, data)
    - stream_mode 为列表且 subgraphs=True  → (namespace, mode, data)
    """
    if isinstance(item, tuple) and len(item) == 3:
        return item[1], item[2]
    if isinstance(item, tuple) and len(item) == 2:
        return item[0], item[1]
    return None, item


async def _compress_history_safely(
    agent: CompiledStateGraph,
    thread_id: str,
    *,
    memory: MemoryTurnContext | None = None,
) -> None:
    try:
        await maybe_compress_history(agent, thread_id=thread_id, memory=memory)
    except Exception as e:  # noqa: BLE001
        log_warning_event(logger, "memory_compress_skipped", thread_id=thread_id, error=str(e))


async def stream_graph_chat_model_events(
    agent: CompiledStateGraph,
    *,
    prompt_text: str = "",
    thread_id: str,
    resume_pdf: bool | None = None,
    attachments: list[dict] | None = None,
    memory: MemoryTurnContext | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """流式产出事件：delta / status / web_sources / interrupt / pdf_ready（custom + updates）。

    总控挂载子图时必须 subgraphs=True，否则子图内 get_stream_writer 的 delta 到不了前端。
    """
    if resume_pdf is not None:
        graph_input: Any = Command(resume=resume_pdf)
    else:
        await _compress_history_safely(agent, thread_id, memory=memory)
        graph_input = {
            "messages": [HumanMessage(content=prompt_text)],
            "skill_name": "",
            "skill_context": "",
            "retrieved_context": "",
            "web_context": "",
            "next_agent": "",
        }

    seen_pdf: set[tuple[str, str]] = set()

    config = _graph_config(thread_id)
    if attachments:
        config["configurable"]["attachments"] = attachments

    async for item in agent.astream(
        graph_input,
        config,
        stream_mode=["custom", "updates"],
        subgraphs=True,
    ):
        mode, payload = _split_astream_item(item)
        if mode == "custom" and isinstance(payload, dict):
            t = payload.get("type")
            if t in ("status", "delta") and payload.get("text") is not None:
                yield {"type": t, "text": str(payload["text"])}
            elif t == "web_sources" and isinstance(payload.get("sources"), list):
                yield {"type": "web_sources", "sources": payload["sources"]}
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
    """进程启动时预热知识库总控（本地/联网）与面试图，避免首请求冷启动。"""
    from Langchain_Agent.runtime_interview import (
        get_stream_interview_executor,
        reset_interview_agent_cache,
    )
    from Langchain_Agent.runtime_knowledge import (
        get_knowledge_supervisor,
        reset_knowledge_agent_cache,
    )

    reset_knowledge_agent_cache()
    reset_interview_agent_cache()
    get_knowledge_supervisor(temperature=temperature, enable_web_search=False)
    get_knowledge_supervisor(temperature=temperature, enable_web_search=True)
    get_stream_interview_executor(temperature=temperature)
