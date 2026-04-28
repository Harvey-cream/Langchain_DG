from __future__ import annotations

import threading
from typing import Any, Callable, Iterator, Optional

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from common.agent import (
    _invoke_agent_sync,
    _message_content_to_text,
    build_react_rag_agent,
    stream_graph_chat_model_events,
)
from common.extend import quick_agent_greeting_prompt
from common.skill_router import build_agent_skill_context
from config.config import get_qwen_chat_model
from Langchain_Agent.tools import get_all_agent_tools
from Langchain_Agent.utils.answer_format_prompt import wrap_user_message_for_agent

_agent_graph_cache_local: CompiledStateGraph | None = None
_agent_graph_cache_web: CompiledStateGraph | None = None
_agent_graph_stream_cache_local: CompiledStateGraph | None = None
_agent_graph_stream_cache_web: CompiledStateGraph | None = None


def get_cached_agent_executor(
    *,
    temperature: float = 0.45,
    streaming: bool = False,
    enable_web_search: bool = False,
) -> CompiledStateGraph:
    """非流式用于普通 chat；streaming=True 使用独立缓存，千问以 token 流式输出。"""
    global _agent_graph_cache_local, _agent_graph_cache_web
    global _agent_graph_stream_cache_local, _agent_graph_stream_cache_web
    if streaming:
        target = _agent_graph_stream_cache_web if enable_web_search else _agent_graph_stream_cache_local
        if target is None:
            all_tools = list(get_all_agent_tools(enable_web_search=enable_web_search))
            target = build_react_rag_agent(
                temperature=temperature, streaming=True, tools=all_tools
            )
            if enable_web_search:
                _agent_graph_stream_cache_web = target
            else:
                _agent_graph_stream_cache_local = target
        return target
    target = _agent_graph_cache_web if enable_web_search else _agent_graph_cache_local
    if target is None:
        all_tools = list(get_all_agent_tools(enable_web_search=enable_web_search))
        target = build_react_rag_agent(
            temperature=temperature, streaming=False, tools=all_tools
        )
        if enable_web_search:
            _agent_graph_cache_web = target
        else:
            _agent_graph_cache_local = target
    return target


def stream_agent(
    *,
    prompt_text: str = "",
    thread_id: str,
    temperature: float = 0.45,
    resume_pdf: bool | None = None,
    enable_web_search: bool = False,
    cancel_event: Optional[threading.Event] = None,
) -> Iterator[dict[str, Any]]:
    """超级智能体：LangGraph 同步流；resume_pdf 用于 PDF 确认后继续图。"""
    agent = get_cached_agent_executor(
        temperature=temperature,
        streaming=True,
        enable_web_search=enable_web_search,
    )
    yield from stream_graph_chat_model_events(
        agent,
        prompt_text=prompt_text,
        thread_id=thread_id,
        resume_pdf=resume_pdf,
        cancel_event=cancel_event,
    )


def chat(
    user_input: str,
    *,
    thread_id: str,
    mcp_input_reader: Optional[Callable[[], str]] = None,
    memory_context: str = "",
    temperature: float = 0.45,
    enable_web_search: bool = False,
) -> str:
    """
    框架入口：create_agent + 工具（RAG / MCP）。

    参数说明：
    - `user_input`：最终喂给 agent 的文本
    - `thread_id`：与 Django 会话对齐的 LangGraph 线程 id（见 agent_checkpoint_thread_id）
    - `mcp_input_reader`：未来你可以传入 MCP 客户端来“读取用户输入”，此处默认不启用
    """

    # 如果你想严格遵循“先 MCP 读入，再给 ReAct/RAG”，可以把 user_input 设为空并传 reader
    if (not user_input or not user_input.strip()) and mcp_input_reader:
        user_input = mcp_input_reader()

    if not user_input.strip():
        raise ValueError("user_input is empty")

    quick_prompt = quick_agent_greeting_prompt(user_input)
    if quick_prompt:
        llm = get_qwen_chat_model(temperature=temperature, streaming=False)
        resp = llm.invoke([HumanMessage(content=quick_prompt)])
        return _message_content_to_text(getattr(resp, "content", resp)).strip()

    agent = get_cached_agent_executor(
        temperature=temperature,
        enable_web_search=enable_web_search,
    )
    skill_context = build_agent_skill_context(user_input)
    prompt = wrap_user_message_for_agent(
        user_input,
        memory_context=memory_context,
        skill_context=skill_context,
    )
    out = _invoke_agent_sync(agent, prompt, thread_id=thread_id)
    return out.get("output") if isinstance(out, dict) else str(out)
