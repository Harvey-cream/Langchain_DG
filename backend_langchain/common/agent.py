from __future__ import annotations
import asyncio
import os
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Callable, Optional, Sequence, Any

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
from common.skill_router import build_agent_skill_context, build_interview_skill_context

_agent_graph_cache: CompiledStateGraph | None = None
_agent_graph_stream_cache: CompiledStateGraph | None = None

# 面试大师：三套 rag 工具 + 统一 prompt，与非流式/流式各一份缓存
_interview_agent_graph_cache: CompiledStateGraph | None = None
_interview_agent_graph_stream_cache: CompiledStateGraph | None = None

CHECKPOINT_SQLITE_PATH = (
    Path(__file__).resolve().parent / "data" / "langgraph_checkpoints.sqlite3"
)
_sqlite_checkpointer: SqliteSaver | None = None
_sqlite_checkpointer_lock = threading.Lock()


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


def _agent_max_iterations() -> int:
    """语义上的「工具/推理轮次」习惯上限，仅用于换算 recursion_limit；默认偏紧，可调环境变量。"""
    raw = os.getenv("AGENT_MAX_ITERATIONS", "6")
    try:
        n = int(raw.strip())
    except ValueError:
        return 6
    return max(1, min(n, 8))


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
    """
    llm = get_qwen_chat_model(temperature=temperature, streaming=streaming)

    if tools is None:
        tools = list(get_all_agent_tools())

    tools_list = list(tools)
    return create_agent(
        llm,
        tools_list,
        system_prompt=None,
        debug=verbose,
        checkpointer=get_sqlite_checkpointer(),
    )


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


def get_cached_agent_executor(*, temperature: float = 0.45, streaming: bool = False) -> CompiledStateGraph:
    """非流式用于普通 chat；streaming=True 使用独立缓存，千问以 token 流式输出。"""
    global _agent_graph_cache, _agent_graph_stream_cache
    if streaming:
        if _agent_graph_stream_cache is None:
            all_tools = list(get_all_agent_tools())
            _agent_graph_stream_cache = build_react_rag_agent(
                temperature=temperature, streaming=True, tools=all_tools
            )
        return _agent_graph_stream_cache
    if _agent_graph_cache is None:
        all_tools = list(get_all_agent_tools())
        _agent_graph_cache = build_react_rag_agent(
            temperature=temperature, streaming=False, tools=all_tools
        )
    return _agent_graph_cache


def warmup_agent_executors(*, temperature: float = 0.45) -> None:
    """
    进程启动时构建四套 CompiledStateGraph 单例（普通/面试 × 流式/非流式），
    避免首个用户请求才加载 LLM 客户端与图。
    """
    get_cached_agent_executor(temperature=temperature, streaming=False)
    get_cached_agent_executor(temperature=temperature, streaming=True)
    get_interview_agent_executor(temperature=temperature, streaming=False)
    get_interview_agent_executor(temperature=temperature, streaming=True)


def invoke_agent_with_stream_callbacks(
    user_input: str,
    callbacks: Sequence[Any],
    *,
    thread_id: str,
    memory_context: str = "",
    temperature: float = 0.45,
) -> str:
    """RAG + 工具；LLM 侧开启流式；callbacks 可接收 on_llm_new_token。多轮记忆由 LangGraph checkpoint + thread_id 承载。"""
    agent = get_cached_agent_executor(temperature=temperature, streaming=True)
    skill_context = build_agent_skill_context(user_input)
    prompt = wrap_user_message_for_agent(
        user_input,
        memory_context=memory_context,
        skill_context=skill_context,
    )
    out = _invoke_agent_sync(
        agent,
        prompt,
        config={"callbacks": list(callbacks)},
        thread_id=thread_id,
    )
    return out.get("output") if isinstance(out, dict) else str(out)


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

    agent = get_interview_agent_executor(temperature=temperature, streaming=False)
    skill_context = build_interview_skill_context(user_input)
    prompt = wrap_interview_user_message(
        user_input,
        memory_context=memory_context,
        skill_context=skill_context,
    )
    out = _invoke_agent_sync(agent, prompt, thread_id=thread_id)
    return out.get("output") if isinstance(out, dict) else str(out)


def invoke_interview_agent_with_stream_callbacks(
    user_input: str,
    callbacks: Sequence[Any],
    *,
    thread_id: str,
    memory_context: str = "",
    temperature: float = 0.45,
) -> str:
    from Langchain_Agent1.utils.prompt import wrap_interview_user_message

    agent = get_interview_agent_executor(temperature=temperature, streaming=True)
    skill_context = build_interview_skill_context(user_input)
    prompt = wrap_interview_user_message(
        user_input,
        memory_context=memory_context,
        skill_context=skill_context,
    )
    out = _invoke_agent_sync(
        agent,
        prompt,
        config={"callbacks": list(callbacks)},
        thread_id=thread_id,
    )
    return out.get("output") if isinstance(out, dict) else str(out)


def chat(
    user_input: str,
    *,
    thread_id: str,
    mcp_input_reader: Optional[Callable[[], str]] = None,
    memory_context: str = "",
    temperature: float = 0.45,
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

    agent = get_cached_agent_executor(temperature=temperature)
    skill_context = build_agent_skill_context(user_input)
    prompt = wrap_user_message_for_agent(
        user_input,
        memory_context=memory_context,
        skill_context=skill_context,
    )
    out = _invoke_agent_sync(agent, prompt, thread_id=thread_id)
    return out.get("output") if isinstance(out, dict) else str(out)


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
