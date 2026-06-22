"""分层诊断 invalid_request：定位哪类请求结构触发 400。"""
from __future__ import annotations

import sys
import traceback
import uuid
from pathlib import Path
from typing import Any, Iterable

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root))

from langchain_core.messages import HumanMessage

from config.config import LLM_AGENT_BASE_URL, LLM_AGENT_MODEL, get_qwen_chat_model
from common.agent import _invoke_agent_sync, build_react_rag_agent, stream_graph_chat_model_events
from human_in_the_loop.human_loop import confirm_pdf_export, finalize_pdf_export
from Langchain_Agent.tools import RAG_TOOLS, get_all_agent_tools


def _print_case(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _run_sync_case(title: str, agent: Any, prompt: str) -> None:
    _print_case(f"[SYNC] {title}")
    thread_id = f"diag:{uuid.uuid4().hex[:12]}"
    try:
        out = _invoke_agent_sync(agent, prompt, thread_id=thread_id)
        text = (out.get("output") if isinstance(out, dict) else str(out)) or ""
        print("OK")
        print("thread_id:", thread_id)
        print("output_preview:", text[:200].replace("\n", " "))
    except Exception as e:  # noqa: BLE001
        print("FAILED")
        print("thread_id:", thread_id)
        print("error:", repr(e))
        traceback.print_exc()


def _run_stream_case(title: str, agent: Any, prompt: str, limit: int = 30) -> None:
    _print_case(f"[STREAM] {title}")
    thread_id = f"diag:{uuid.uuid4().hex[:12]}"
    count = 0
    try:
        for evt in stream_graph_chat_model_events(agent, prompt_text=prompt, thread_id=thread_id):
            count += 1
            if count <= limit:
                print("evt", count, evt)
            if count >= limit:
                print(f"... truncated at {limit} events")
                break
        print("OK")
        print("thread_id:", thread_id)
        print("events_seen:", count)
    except Exception as e:  # noqa: BLE001
        print("FAILED")
        print("thread_id:", thread_id)
        print("events_before_error:", count)
        print("error:", repr(e))
        traceback.print_exc()


def _build_agent(tools: Iterable[Any], *, streaming: bool) -> Any:
    return build_react_rag_agent(
        tools=list(tools),
        temperature=0.45,
        streaming=streaming,
    )


def main() -> None:
    print("LLM base_url:", LLM_AGENT_BASE_URL)
    print("LLM model:", LLM_AGENT_MODEL)

    simple_llm_prompt = "请用一句话回答：你是谁？"
    agent_prompt = "什么是openclaw？请用简洁中文回答。"
    pdf_prompt = "请帮我导出一份 PDF。"

    _print_case("[BASELINE] plain llm.invoke")
    try:
        llm = get_qwen_chat_model(temperature=0.45, streaming=False)
        resp = llm.invoke([HumanMessage(content=simple_llm_prompt)])
        text = str(getattr(resp, "content", resp))
        print("OK")
        print("output_preview:", text[:200].replace("\n", " "))
    except Exception as e:  # noqa: BLE001
        print("FAILED")
        print("error:", repr(e))
        traceback.print_exc()

    # 1) 无工具 agent（确认基础 chat 请求结构）
    agent_sync_no_tools = _build_agent([], streaming=False)
    _run_sync_case("agent no tools", agent_sync_no_tools, agent_prompt)

    agent_stream_no_tools = _build_agent([], streaming=True)
    _run_stream_case("agent no tools", agent_stream_no_tools, agent_prompt)

    # 2) 仅 RAG 工具
    agent_sync_rag = _build_agent(RAG_TOOLS, streaming=False)
    _run_sync_case("agent rag tools only", agent_sync_rag, agent_prompt)

    agent_stream_rag = _build_agent(RAG_TOOLS, streaming=True)
    _run_stream_case("agent rag tools only", agent_stream_rag, agent_prompt)

    # 3) 仅 PDF 人机协同工具
    pdf_tools = [confirm_pdf_export, finalize_pdf_export]
    agent_sync_pdf = _build_agent(pdf_tools, streaming=False)
    _run_sync_case("agent pdf tools only", agent_sync_pdf, pdf_prompt)

    agent_stream_pdf = _build_agent(pdf_tools, streaming=True)
    _run_stream_case("agent pdf tools only", agent_stream_pdf, pdf_prompt)

    # 4) 全量工具（与线上最接近）
    all_tools = get_all_agent_tools(enable_web_search=False)
    agent_sync_all = _build_agent(all_tools, streaming=False)
    _run_sync_case("agent all tools", agent_sync_all, agent_prompt)

    agent_stream_all = _build_agent(all_tools, streaming=True)
    _run_stream_case("agent all tools", agent_stream_all, agent_prompt)


if __name__ == "__main__":
    main()

