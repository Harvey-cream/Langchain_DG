from __future__ import annotations
import asyncio
import logging
import os
import time
import re
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, Sequence

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from Agent_memory.memory import maybe_compress_history
from human_in_the_loop.human_loop import (
    interrupt_payload_from_updates,
    pdf_ready_payload_from_updates,
    strip_pdf_internal_markers,
)
from backend_langchain.logger_func import log_info_event, log_warning_event

# 兼容两种运行方式：
# 1) python -m backend_langchain.common.agent
# 2) python common/agent.py  (cwd=backend_langchain)
if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from config.config import get_qwen_chat_model
from Langchain_Agent.prompts import wrap_agent_user_message
from Langchain_Agent.tools import get_all_agent_tools

logger = logging.getLogger(__name__)

CHECKPOINT_SQLITE_PATH = (
    Path(__file__).resolve().parent / "data" / "langgraph_checkpoints.sqlite3"
)
_sqlite_checkpointer: SqliteSaver | None = None
_sqlite_checkpointer_lock = threading.Lock()


# =============================================================================
# 公共：检查点、线程 id、消息解析、invoke 结果规整、图配置与步数上限
# （流式与非流式共用，不区分 stream / invoke）
# =============================================================================


def get_sqlite_checkpointer() -> SqliteSaver:
    """LangGraph 会话状态持久化（与 Django 会话的 conversation_id 通过 thread_id 对应）。"""
    global _sqlite_checkpointer
    with _sqlite_checkpointer_lock:
        if _sqlite_checkpointer is None:
            CHECKPOINT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(CHECKPOINT_SQLITE_PATH),
                check_same_thread=False,
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA synchronous=NORMAL")
            _sqlite_checkpointer = SqliteSaver(conn)
        return _sqlite_checkpointer


def agent_checkpoint_thread_id(user_id: int, conversation_id: int) -> str:
    return f"agent:{user_id}:{conversation_id}"


def interview_checkpoint_thread_id(user_id: int, conversation_id: int) -> str:
    return f"interview:{user_id}:{conversation_id}"


def _message_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    parts.append(str(block["text"]))
                elif "text" in block:
                    parts.append(str(block["text"]))
        return "".join(parts)
    return str(content)


def _last_ai_text_from_agent_result(result: Any) -> str:
    """create_agent（LangGraph）invoke 结果为 state，取最后一条 AI 正文。"""
    if not isinstance(result, dict):
        return str(result)
    messages = result.get("messages")
    if not messages:
        return str(result)
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            text = _message_content_to_text(msg.content).strip()
            if text:
                return text
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return _message_content_to_text(msg.content).strip()
    return ""


def _normalize_agent_result(result: Any) -> dict[str, Any]:
    return {"output": _last_ai_text_from_agent_result(result)}


def _agent_max_iterations() -> int:
    """语义上的「工具/推理轮次」习惯上限，仅用于换算 recursion_limit；默认偏紧，可调环境变量。"""
    raw = os.getenv("AGENT_MAX_ITERATIONS", "6")
    try:
        n = int(raw.strip())
    except ValueError:
        return 6
    return max(1, min(n, 8))


def _graph_recursion_limit() -> int:
    """封顶 LangGraph 图步数；默认由 AGENT_MAX_ITERATIONS 推导（每轮约 model + tool，系数保守）。"""
    raw = os.getenv("AGENT_RECURSION_LIMIT", "").strip()
    if raw:
        try:
            return max(4, int(raw))
        except ValueError:
            pass
    n = _agent_max_iterations()
    # 系数略小于「每轮 4 步」：避免默认 n 较大时总步数体感过长；需更长可设 AGENT_RECURSION_LIMIT
    return max(14, n * 3 + 4)


def _merge_graph_config(
    base: dict[str, Any] | None,
    *,
    thread_id: str | None = None,
) -> dict[str, Any]:
    cfg: dict[str, Any] = dict(base or {})
    cfg.setdefault("recursion_limit", _graph_recursion_limit())
    if thread_id is not None:
        conf = dict(cfg.get("configurable") or {})
        conf["thread_id"] = thread_id
        cfg["configurable"] = conf
    return cfg


# =============================================================================
# 公共：LangGraph 构图（streaming 由参数区分；具体 chat/stream 在各自 app 模块）
# =============================================================================


def build_react_rag_agent(
    *,
    tools: Optional[Sequence[Any]] = None,
    temperature: float = 0.45,
    verbose: bool = False,
    streaming: bool = False,
) -> CompiledStateGraph:
    """
    LangChain 1.x：create_agent（内置 LangGraph）。
    多参数工具走模型原生 tool calling，与 MCP/RAG 兼容。
    检查点统一用同步 SqliteSaver；流式走 graph.stream(stream_mode=["messages","updates"]) 以透出 interrupt，勿用 astream_events（会要求异步 checkpointer）。
    """
    llm = get_qwen_chat_model(temperature=temperature, streaming=streaming)

    if tools is None:
        tools = list(get_all_agent_tools())

    tools_list = list(tools)
    checkpointer = get_sqlite_checkpointer()

    return create_agent(
        llm,
        tools_list,
        system_prompt=None,
        debug=verbose,
        checkpointer=checkpointer,
    )


# =============================================================================
# 流式：graph.stream(stream_mode="messages") 增量输出（SSE / Queue 使用 app 内 stream_*）
# =============================================================================


# 旧版工具曾返回 [n] knowledge_base=… 行；流式里再剥一层，防模型照抄或历史 checkpoint
_RAG_LEGACY_LINE = re.compile(r"\[\d+\]\s*knowledge_base=[^\n]*\n?", re.MULTILINE)
_SOURCE_LINE = re.compile(r"^\s*#?\s*Source:\s*.+$", re.MULTILINE)


def _strip_rag_echo_for_stream(text: str) -> str:
    if not (text or "").strip():
        return text
    s = _RAG_LEGACY_LINE.sub("", text)
    s = _SOURCE_LINE.sub("", s)
    return s


def _chunk_has_tool_calls(chunk: Any) -> bool:
    tc = getattr(chunk, "tool_calls", None)
    if tc:
        return True
    tcc = getattr(chunk, "tool_call_chunks", None)
    if tcc:
        return True
    add = getattr(chunk, "additional_kwargs", None) or {}
    return bool(add.get("tool_calls"))


def _tool_names_from_model_chunk(chunk: Any) -> list[str]:
    """从流式 AI chunk 里尽量取出本轮 tool_call 名（流式下可能晚几帧才齐）。"""
    out: list[str] = []
    for tc in getattr(chunk, "tool_calls", None) or []:
        if isinstance(tc, dict):
            n = tc.get("name")
        else:
            n = getattr(tc, "name", None)
        if n:
            out.append(str(n))
    for tcc in getattr(chunk, "tool_call_chunks", None) or []:
        if isinstance(tcc, dict) and tcc.get("name"):
            out.append(str(tcc["name"]))
    for item in (getattr(chunk, "additional_kwargs", None) or {}).get("tool_calls") or []:
        if isinstance(item, dict) and item.get("function", {}).get("name"):
            out.append(str(item["function"]["name"]))
    seen: set[str] = set()
    dedup: list[str] = []
    for n in out:
        if n not in seen:
            seen.add(n)
            dedup.append(n)
    return dedup


def _tool_call_ids_from_model_chunk(chunk: Any) -> list[str]:
    """从流式 AI chunk 里尽量提取 tool_call_id（不同 provider 字段形态兼容）。"""
    out: list[str] = []
    for tc in getattr(chunk, "tool_calls", None) or []:
        if isinstance(tc, dict):
            cid = tc.get("id")
        else:
            cid = getattr(tc, "id", None)
        if cid:
            out.append(str(cid))
    for tcc in getattr(chunk, "tool_call_chunks", None) or []:
        if isinstance(tcc, dict) and tcc.get("id"):
            out.append(str(tcc["id"]))
    for item in (getattr(chunk, "additional_kwargs", None) or {}).get("tool_calls") or []:
        if isinstance(item, dict) and item.get("id"):
            out.append(str(item["id"]))
    seen: set[str] = set()
    dedup: list[str] = []
    for cid in out:
        if cid not in seen:
            seen.add(cid)
            dedup.append(cid)
    return dedup


def _agent_tool_log_enabled() -> bool:
    return (os.getenv("AGENT_LOG_TOOLS", "1").strip() or "1") not in {
        "0",
        "false",
        "no",
        "off",
    }


def stream_graph_chat_model_events(
    agent: CompiledStateGraph,
    *,
    prompt_text: str = "",
    thread_id: str,
    resume_pdf: bool | None = None,
    cancel_event: Optional[threading.Event] = None,
) -> Iterator[dict[str, Any]]:
    """
    同步 stream：messages + updates（捕获 interrupt）；与 SqliteSaver 兼容。
    resume_pdf 非空时用 Command(resume=...) 继续人机协同，勿再发 HumanMessage。
    """
    merged = _merge_graph_config(None, thread_id=thread_id)
    if resume_pdf is not None:
        input_or_cmd: Any = Command(resume=resume_pdf)
    else:
        # resume_pdf 阶段处于 interrupt 闭环中，禁止改写 state，否则会破坏 PDF 人机协同。
        try:
            maybe_compress_history(agent, thread_id=thread_id)
        except Exception as e:  # noqa: BLE001
            log_warning_event(
                logger,
                "memory_compress_skipped_due_to_error",
                thread_id=thread_id,
                error=str(e),
            )
        input_or_cmd = {"messages": [HumanMessage(content=prompt_text)]}
    in_tool = False
    # 从「模型发起 tool_call」到本条 ToolMessage 返回的墙钟时间（秒级内多工具则一段段累加）
    _tool_segment_t0: float | None = None
    pending_tool_calls: set[str] = set()
    completed_tool_calls: set[str] = set()
    cancelled = False
    seen_pdf_ready: set[tuple[str, str]] = set()
    try:
        stream_iter = agent.stream(
            input_or_cmd,
            merged,
            stream_mode=["messages", "updates"],
        )
        for item in stream_iter:
            # B：仅在非工具阶段且不存在未闭环 tool_call 时允许取消，避免截断闭环。
            if (
                cancel_event is not None
                and cancel_event.is_set()
                and not in_tool
                and not pending_tool_calls
            ):
                cancelled = True
                break
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            mode, payload = item[0], item[1]
            if mode not in ("messages", "updates"):
                continue
            if mode == "updates":
                intr = interrupt_payload_from_updates(payload)
                if intr:
                    yield {"type": "interrupt", **intr}
                pdf_evt = pdf_ready_payload_from_updates(payload)
                if pdf_evt:
                    key = (pdf_evt["url"], pdf_evt["filename"])
                    if key not in seen_pdf_ready:
                        seen_pdf_ready.add(key)
                        yield {
                            "type": "pdf_ready",
                            "url": pdf_evt["url"],
                            "filename": pdf_evt["filename"],
                        }
                continue
            if mode != "messages":
                continue
            msg_pair = payload
            if not isinstance(msg_pair, tuple) or not msg_pair:
                continue
            chunk = msg_pair[0]
            if isinstance(chunk, ToolMessage):
                tname = getattr(chunk, "name", None)
                tid = getattr(chunk, "tool_call_id", None)
                tid_s = str(tid) if tid else None
                if tid_s:
                    completed_tool_calls.add(tid_s)
                    pending_tool_calls.discard(tid_s)
                if _agent_tool_log_enabled():
                    if _tool_segment_t0 is not None:
                        duration_ms = (time.perf_counter() - _tool_segment_t0) * 1000
                    else:
                        duration_ms = -1.0
                    # 下一段计时：连续多条 ToolMessage（同轮多工具）从本条结束再起表
                    _tool_segment_t0 = time.perf_counter()
                    log_info_event(
                        logger,
                        "agent_tool_executed",
                        thread_id=thread_id,
                        tool=tname,
                        duration_ms=round(duration_ms, 1),
                        tool_call_id=tid,
                    )
                pdf_evt = pdf_ready_payload_from_updates({"_tool": chunk})
                if pdf_evt:
                    key = (pdf_evt["url"], pdf_evt["filename"])
                    if key not in seen_pdf_ready:
                        seen_pdf_ready.add(key)
                        yield {
                            "type": "pdf_ready",
                            "url": pdf_evt["url"],
                            "filename": pdf_evt["filename"],
                        }
                continue
            if _chunk_has_tool_calls(chunk):
                ids = _tool_call_ids_from_model_chunk(chunk)
                for cid in ids:
                    if cid not in completed_tool_calls:
                        pending_tool_calls.add(cid)
                if not in_tool:
                    yield {"type": "status", "text": "🔍 查询中"}
                    in_tool = True
                    _tool_segment_t0 = time.perf_counter()
                    if _agent_tool_log_enabled():
                        names = _tool_names_from_model_chunk(chunk)
                        log_info_event(
                            logger,
                            "agent_tool_invoke",
                            thread_id=thread_id,
                            requested_tools=names if names else "(name pending in stream)",
                            requested_tool_call_ids=ids if ids else "(id pending in stream)",
                        )
                continue
            in_tool = False
            _tool_segment_t0 = None
            piece = _message_content_to_text(getattr(chunk, "content", None))
            if piece:
                cleaned = strip_pdf_internal_markers(_strip_rag_echo_for_stream(piece))
                if cleaned:
                    yield {"type": "delta", "text": cleaned}
    except Exception:
        # C：工具异常时输出闭环诊断，确保定位到未回填的 tool_call_id。
        if pending_tool_calls:
            log_warning_event(
                logger,
                "agent_tool_call_unresolved_on_exception",
                thread_id=thread_id,
                pending_tool_call_ids=sorted(pending_tool_calls),
                completed_tool_call_ids=sorted(completed_tool_calls),
            )
        raise
    if pending_tool_calls and _agent_tool_log_enabled():
        log_warning_event(
            logger,
            "agent_tool_call_unresolved_on_stream_end",
            thread_id=thread_id,
            pending_tool_call_ids=sorted(pending_tool_calls),
            completed_tool_call_ids=sorted(completed_tool_calls),
            cancelled=cancelled,
        )


# =============================================================================
# 同步 invoke（仅 CLI / 诊断脚本）
# =============================================================================


def _invoke_agent_sync(
    agent: CompiledStateGraph,
    prompt_text: str,
    *,
    config: dict[str, Any] | None = None,
    thread_id: str,
) -> dict[str, Any]:
    """
    使用同步 invoke：SqliteSaver 仅实现同步 checkpoint API，ainvoke 会走异步存储导致报错。
    可选 AGENT_MAX_EXECUTION_TIME：在无运行中 event loop 的线程里用线程池做超时（与原先 wait_for 语义相近）。
    """
    try:
        maybe_compress_history(agent, thread_id=thread_id)
    except Exception as e:  # noqa: BLE001
        log_warning_event(
            logger,
            "memory_compress_skipped_due_to_error",
            thread_id=thread_id,
            error=str(e),
        )

    input_state: dict[str, Any] = {"messages": [HumanMessage(content=prompt_text)]}
    merged = _merge_graph_config(config, thread_id=thread_id)
    t_raw = os.getenv("AGENT_MAX_EXECUTION_TIME", "").strip()

    def _call() -> dict[str, Any]:
        raw = agent.invoke(input_state, config=merged)
        return _normalize_agent_result(raw)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        if not t_raw:
            return _call()
        try:
            timeout = float(t_raw)
        except ValueError:
            return _call()
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_call)
            try:
                return fut.result(timeout=timeout)
            except FuturesTimeout as e:
                raise TimeoutError(f"agent invoke 超过 {timeout} 秒") from e
    raise RuntimeError(
        "当前线程已有 event loop，请在本路径改为 await agent.ainvoke(...) "
        "或使用同步 WSGI 线程调用超级智能体。"
    )


def warmup_agent_executors(*, temperature: float = 0.45) -> None:
    """进程启动时预热两个流式图，避免首请求冷启动。"""
    from Langchain_Agent import agents

    agents.get_stream_agent_executor(temperature=temperature, enable_web_search=False)
    agents.get_stream_agent_executor(temperature=temperature, enable_web_search=True)
    agents.get_stream_interview_executor(temperature=temperature)


def _default_mcp_input_reader(prompt: str = "User: ") -> str:
    """
    这里先提供一个“框架级”的 MCP 输入读取接口：
    - 你未来可以替换成真正的 MCP 客户端（例如通过 MCP server 工具获取输入）
    - 现在先回退到标准输入，保证框架能跑通 ReAct + RAG
    """
    # 兼容：允许外部通过环境变量注入用户输入（便于联调）
    injected = os.getenv("MCP_USER_INPUT")
    if injected:
        return injected
    return input(prompt)


def cli():
    agent = build_react_rag_agent(verbose=True)
    cli_thread = "cli-repl"

    mcp_reader = _default_mcp_input_reader
    while True:
        try:
            user_input = mcp_reader()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return

        if user_input.strip().lower() in {"exit", "quit", "q"}:
            print("bye")
            return
        prompt = wrap_agent_user_message(user_input)
        out = _invoke_agent_sync(agent, prompt, thread_id=cli_thread)
        print(out.get("output") if isinstance(out, dict) else out)


if __name__ == "__main__":
    cli()
