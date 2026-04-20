from __future__ import annotations
import asyncio
import logging
import os
import re
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, Sequence

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph

# 兼容两种运行方式：
# 1) python -m backend_langchain.common.agent
# 2) python common/agent.py  (cwd=backend_langchain)
if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from config.config import get_qwen_chat_model
from Langchain_Agent.utils.answer_format_prompt import wrap_user_message_for_agent
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
    检查点统一用同步 SqliteSaver；流式走 graph.stream(stream_mode="messages")，勿用 astream_events（会要求异步 checkpointer）。
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


def stream_graph_chat_model_events(
    agent: CompiledStateGraph,
    *,
    prompt_text: str,
    thread_id: str,
) -> Iterator[dict[str, Any]]:
    """
    同步 stream(messages)：与 SqliteSaver + SyncPregelLoop 兼容。
    astream_events 会走 checkpointer.aget_tuple，同步 SqliteSaver 未实现异步接口会报错。
    """
    input_state: dict[str, Any] = {"messages": [HumanMessage(content=prompt_text)]}
    merged = _merge_graph_config(None, thread_id=thread_id)
    in_tool = False
    for item in agent.stream(
        input_state,
        merged,
        stream_mode="messages",
    ):
        if not isinstance(item, tuple) or not item:
            continue
        chunk = item[0]
        if _chunk_has_tool_calls(chunk):
            if not in_tool:
                yield {"type": "status", "text": "🔍 查询中"}
                in_tool = True
            continue
        in_tool = False
        piece = _message_content_to_text(getattr(chunk, "content", None))
        if piece:
            cleaned = _strip_rag_echo_for_stream(piece)
            if cleaned:
                yield {"type": "delta", "text": cleaned}


# =============================================================================
# 非流式：同步 invoke 一整轮（返回最终 output；用于 chat / chat_interview / cli）
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


# =============================================================================
# 非流式：门面（委托 Langchain_Agent.main_agent / Langchain_Agent1.interview_agent）
# =============================================================================


def get_interview_agent_executor(
    *,
    temperature: float = 0.45,
    streaming: bool = False,
) -> CompiledStateGraph:
    """面试大师执行器缓存（实现见 Langchain_Agent1.interview_agent）。"""
    import Langchain_Agent1.interview_agent as interview_agent

    return interview_agent.get_interview_agent_executor(
        temperature=temperature, streaming=streaming
    )


def get_cached_agent_executor(
    *, temperature: float = 0.45, streaming: bool = False
) -> CompiledStateGraph:
    """主智能体执行器缓存（实现见 Langchain_Agent.main_agent）。"""
    import Langchain_Agent.main_agent as main_agent

    return main_agent.get_cached_agent_executor(
        temperature=temperature, streaming=streaming
    )


def warmup_agent_executors(*, temperature: float = 0.45) -> None:
    """
    进程启动时构建四套 CompiledStateGraph 单例（普通/面试 × 流式/非流式），
    避免首个用户请求才加载 LLM 客户端与图。
    """
    import Langchain_Agent.main_agent as main_agent
    import Langchain_Agent1.interview_agent as interview_agent

    main_agent.get_cached_agent_executor(temperature=temperature, streaming=False)
    main_agent.get_cached_agent_executor(temperature=temperature, streaming=True)
    interview_agent.get_interview_agent_executor(
        temperature=temperature, streaming=False
    )
    interview_agent.get_interview_agent_executor(
        temperature=temperature, streaming=True
    )


def chat_interview(
    user_input: str,
    *,
    thread_id: str,
    memory_context: str = "",
    temperature: float = 0.45,
) -> str:
    """面试大师：见 Langchain_Agent1.utils.prompt（实现见 Langchain_Agent1.interview_agent）。"""
    import Langchain_Agent1.interview_agent as interview_agent

    return interview_agent.chat_interview(
        user_input,
        thread_id=thread_id,
        memory_context=memory_context,
        temperature=temperature,
    )


def chat(
    user_input: str,
    *,
    thread_id: str,
    mcp_input_reader: Optional[Callable[[], str]] = None,
    memory_context: str = "",
    temperature: float = 0.45,
) -> str:
    """
    框架入口：create_agent + 工具（RAG / MCP）（实现见 Langchain_Agent.main_agent）。

    参数说明：
    - `user_input`：最终喂给 agent 的文本
    - `thread_id`：与 Django 会话对齐的 LangGraph 线程 id（见 agent_checkpoint_thread_id）
    - `mcp_input_reader`：未来你可以传入 MCP 客户端来“读取用户输入”，此处默认不启用
    """
    import Langchain_Agent.main_agent as main_agent

    return main_agent.chat(
        user_input,
        thread_id=thread_id,
        mcp_input_reader=mcp_input_reader,
        memory_context=memory_context,
        temperature=temperature,
    )


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
        prompt = wrap_user_message_for_agent(user_input)
        out = _invoke_agent_sync(agent, prompt, thread_id=cli_thread)
        print(out.get("output") if isinstance(out, dict) else out)


if __name__ == "__main__":
    cli()
