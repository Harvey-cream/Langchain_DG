from __future__ import annotations

from typing import Any, Iterator

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from common.agent import (
    _invoke_agent_sync,
    _message_content_to_text,
    build_react_rag_agent,
    stream_graph_chat_model_events,
)
from common.extend import quick_interview_greeting_prompt
from common.skill_router import build_interview_skill_context
from config.config import get_qwen_chat_model

# 面试大师：三套 rag 工具 + 统一 prompt，与非流式/流式各一份缓存
_interview_agent_graph_cache: CompiledStateGraph | None = None
_interview_agent_graph_stream_cache: CompiledStateGraph | None = None


def get_interview_agent_executor(
    *,
    temperature: float = 0.45,
    streaming: bool = False,
) -> CompiledStateGraph:
    """面试大师：工具调用 + 三套面试向量库工具，由模型自行选用。"""
    global _interview_agent_graph_cache, _interview_agent_graph_stream_cache
    from Langchain_Agent1.tools import INTERVIEW_RAG_TOOLS

    if streaming:
        if _interview_agent_graph_stream_cache is None:
            _interview_agent_graph_stream_cache = build_react_rag_agent(
                tools=list(INTERVIEW_RAG_TOOLS), temperature=temperature, streaming=True
            )
        return _interview_agent_graph_stream_cache
    if _interview_agent_graph_cache is None:
        _interview_agent_graph_cache = build_react_rag_agent(
            tools=list(INTERVIEW_RAG_TOOLS), temperature=temperature, streaming=False
        )
    return _interview_agent_graph_cache


def stream_interview_agent(
    *,
    prompt_text: str,
    thread_id: str,
    temperature: float = 0.45,
) -> Iterator[dict[str, Any]]:
    """面试大师：与主 agent 一致的同步流式语义。"""
    agent = get_interview_agent_executor(temperature=temperature, streaming=True)
    yield from stream_graph_chat_model_events(
        agent, prompt_text=prompt_text, thread_id=thread_id
    )


def chat_interview(
    user_input: str,
    *,
    thread_id: str,
    memory_context: str = "",
    temperature: float = 0.45,
) -> str:
    """面试大师：见 Langchain_Agent1.utils.prompt。"""
    from Langchain_Agent1.utils.prompt import wrap_interview_user_message

    if not user_input.strip():
        raise ValueError("user_input is empty")

    quick_prompt = quick_interview_greeting_prompt(user_input)
    if quick_prompt:
        llm = get_qwen_chat_model(temperature=temperature, streaming=False)
        resp = llm.invoke([HumanMessage(content=quick_prompt)])
        return _message_content_to_text(getattr(resp, "content", resp)).strip()

    agent = get_interview_agent_executor(temperature=temperature, streaming=False)
    skill_context = build_interview_skill_context(user_input)
    prompt = wrap_interview_user_message(
        user_input,
        memory_context=memory_context,
        skill_context=skill_context,
    )
    out = _invoke_agent_sync(agent, prompt, thread_id=thread_id)
    return out.get("output") if isinstance(out, dict) else str(out)
