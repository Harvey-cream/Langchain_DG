from __future__ import annotations
import os
from typing import Callable, Optional, Sequence, Any
from langchain.agents import AgentExecutor, AgentType, initialize_agent
from common.LLM.config import get_qwen_chat_model
from Langchain_Agent.utils.answer_format_prompt import wrap_user_message_for_agent
from Langchain_Agent.tools import RAG_TOOLS

_agent_executor_cache: AgentExecutor | None = None
_agent_executor_stream_cache: AgentExecutor | None = None


def _agent_max_iterations() -> int:
    """ReAct 每步一轮 Thought/Action/Observation；步数过大易拖时长、像死循环。默认 10，上限 10，可用 AGENT_MAX_ITERATIONS 在 1～10 间微调。"""
    raw = os.getenv("AGENT_MAX_ITERATIONS", "10")
    try:
        n = int(raw.strip())
    except ValueError:
        return 10
    return max(1, min(n, 10))


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
) -> AgentExecutor:
    llm = get_qwen_chat_model(temperature=temperature, streaming=streaming)

    if tools is None:
        tools = list(RAG_TOOLS)

    # ZERO_SHOT_REACT_DESCRIPTION：让模型按 ReAct 方式描述思考与调用工具
    # max_iterations：见 _agent_max_iterations()（默认 10，防长时间空转）
    max_iter = _agent_max_iterations()
    agent_kwargs: dict = {}
    t_raw = os.getenv("AGENT_MAX_EXECUTION_TIME", "").strip()
    if t_raw:
        try:
            agent_kwargs["max_execution_time"] = float(t_raw)
        except ValueError:
            pass

    # handle_parsing_errors：False 时任意一次格式不合规（如闲聊只输出一句无 Thought/Final Answer）会直接抛错给用户。
    # True 时把解析错误当 Observation 让模型重试；配合 max_iterations + early_stopping_method=force 可封顶，避免无限循环。
    # ReAct 的「Final Answer:」是 LLM 须输出的格式前缀（给解析器用），不是「说完就停」的隐藏指令；正文里重复写由 prompt + common.SSE 后处理去掉。
    agent_executor = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=verbose,
        handle_parsing_errors=True,
        early_stopping_method="force",
        max_iterations=max_iter,
        **agent_kwargs,
    )

    return agent_executor


def get_cached_agent_executor(*, temperature: float = 0.45, streaming: bool = False) -> AgentExecutor:
    """非流式用于普通 chat；streaming=True 使用独立缓存，千问以 token 流式输出。"""
    global _agent_executor_cache, _agent_executor_stream_cache
    if streaming:
        if _agent_executor_stream_cache is None:
            _agent_executor_stream_cache = build_react_rag_agent(temperature=temperature, streaming=True)
        return _agent_executor_stream_cache
    if _agent_executor_cache is None:
        _agent_executor_cache = build_react_rag_agent(temperature=temperature, streaming=False)
    return _agent_executor_cache


def invoke_agent_with_stream_callbacks(
    user_input: str,
    callbacks: Sequence[Any],
    *,
    temperature: float = 0.45,
) -> str:
    """ReAct+RAG，LLM 侧开启流式；callbacks 可接收 on_llm_new_token（含多轮 Thought/Action/Final）。"""
    agent_executor = get_cached_agent_executor(temperature=temperature, streaming=True)
    prompt = wrap_user_message_for_agent(user_input)
    out = agent_executor.invoke({"input": prompt}, config={"callbacks": list(callbacks)})
    return out.get("output") if isinstance(out, dict) else str(out)


def chat(
    user_input: str,
    *,
    mcp_input_reader: Optional[Callable[[], str]] = None,
    temperature: float = 0.45,
) -> str:
    """
    框架入口：ReAct + RAG。

    参数说明：
    - `user_input`：最终喂给 agent 的文本
    - `mcp_input_reader`：未来你可以传入 MCP 客户端来“读取用户输入”，此处默认不启用
    """

    # 如果你想严格遵循“先 MCP 读入，再给 ReAct/RAG”，可以把 user_input 设为空并传 reader
    if (not user_input or not user_input.strip()) and mcp_input_reader:
        user_input = mcp_input_reader()

    if not user_input.strip():
        raise ValueError("user_input is empty")

    agent_executor = get_cached_agent_executor(temperature=temperature)
    prompt = wrap_user_message_for_agent(user_input)
    out = agent_executor.invoke({"input": prompt})
    return out.get("output") if isinstance(out, dict) else str(out)


def cli():
    agent_executor = build_react_rag_agent(verbose=True)

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

        # 直接复用同一个 executor，避免每次重建
        print(agent_executor.run(user_input))


if __name__ == "__main__":
    cli()

