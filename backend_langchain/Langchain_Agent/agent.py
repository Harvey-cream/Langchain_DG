from __future__ import annotations
import os
from typing import Callable, Optional
from langchain.agents import AgentExecutor, AgentType, initialize_agent
from common.LLM.config import get_qwen_chat_model
from .tools import chroma_rag_search


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
    chroma_tool=chroma_rag_search,
    temperature: float = 0.2,
    verbose: bool = False,
) -> AgentExecutor:
    llm = get_qwen_chat_model(temperature=temperature)

    tools = [chroma_tool]

    # ZERO_SHOT_REACT_DESCRIPTION：让模型按 ReAct 方式描述思考与调用工具
    agent_executor = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=verbose,
        handle_parsing_errors=True,
    )

    return agent_executor


def chat(
    user_input: str,
    *,
    mcp_input_reader: Optional[Callable[[], str]] = None,
    temperature: float = 0.2,
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

    agent_executor = build_react_rag_agent(temperature=temperature, verbose=False)
    # initialize_agent 的 AgentExecutor 提供 run 方法
    return agent_executor.run(user_input)


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

