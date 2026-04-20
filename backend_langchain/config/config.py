import os
from typing import Any, Optional

os.environ.setdefault("CHROMA_TELEMETRY", "0")

from dotenv import load_dotenv

# OpenAI 兼容 API：用 langchain_openai（与 openai 1.x SDK 一致），勿再用 langchain_community 里已弃用的 ChatOpenAI
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.messages import BaseMessage

load_dotenv()

# 本地与线上同一套：只认 LLM_AGENT_*。未设置环境变量时用下列默认值（私有仓库可接受）；
# 若设置了 LLM_AGENT_* / .env / yaml apply_llm_env，则优先用环境变量。
# base_url 需含 /v1。
LLM_AGENT_BASE_URL = os.getenv("LLM_AGENT_BASE_URL", "https://gpt-agent.cc/v1").strip()
LLM_AGENT_API_KEY = os.getenv("LLM_AGENT_API_KEY", "sk-dpsaFmP9J9PHpe75yyJdvQ1xkgmfIF1oPru31peFWuzPrZ6B").strip()
LLM_AGENT_MODEL = os.getenv("LLM_AGENT_MODEL", "gpt-5.4").strip()


class _AgentStreamChatOpenAI(ChatOpenAI):
    """
    流式输出必须走 OpenAI 的 stream=True，模型侧才有逐块输出（LangGraph 下由 graph.stream(stream_mode="messages") 消费）。

    - BaseChatModel._generate_with_cache：需在 kwargs 里带 stream=True 才会走 _stream 循环。
    - ChatOpenAI._generate：若上层显式传入 stream=False，会覆盖 self.streaming，整段返回、体感像非流式。
    构造时的 streaming=True 只设「默认」；AgentExecutor 仍可能传 stream=False，故仍需在 _generate / _agenerate / *_generate_with_cache 里强制 stream=True。
    （用户可见「格式」由 prompt + SSE 清洗负责，与这里无关。）
    """

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        stream: Optional[bool] = None,
        **kwargs: Any,
    ) -> Any:
        if self.streaming:
            stream = True
        return super()._generate(
            messages, stop=stop, run_manager=run_manager, stream=stream, **kwargs
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        stream: Optional[bool] = None,
        **kwargs: Any,
    ) -> Any:
        if self.streaming:
            stream = True
        return await super()._agenerate(
            messages, stop=stop, run_manager=run_manager, stream=stream, **kwargs
        )

    def _generate_with_cache(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Any:
        if self.streaming:
            kwargs = {**kwargs, "stream": True}
        return super()._generate_with_cache(
            messages, stop=stop, run_manager=run_manager, **kwargs
        )

    async def _agenerate_with_cache(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        if self.streaming:
            kwargs = {**kwargs, "stream": True}
        return await super()._agenerate_with_cache(
            messages, stop=stop, run_manager=run_manager, **kwargs
        )


def get_qwen_chat_model(temperature: float = 0.7, *, streaming: bool = False) -> Any:
    """
    获取 Chat 模型实例。
    当前使用 OpenAI 兼容 HTTP API（默认 LLM_AGENT_BASE_URL，如 gpt-agent.cc）；经此函数接入。
    streaming=True 时使用 _AgentStreamChatOpenAI，保证底层请求始终带 stream=True，便于 SSE 按 token 推送。
    """
    common = dict(
        model=LLM_AGENT_MODEL,
        api_key=LLM_AGENT_API_KEY,
        base_url=LLM_AGENT_BASE_URL,
        temperature=temperature,
    )
    if streaming:
        return _AgentStreamChatOpenAI(**common, streaming=True)
    # 仅非流式场景（如标题润色、同步 POST chat）：一次返回全文；与 SSE 无关
    return ChatOpenAI(**common)


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage

    llm = get_qwen_chat_model()
    print("模型加载成功，正在回答...")
    response = llm.invoke([HumanMessage(content="你在干什么呀，你会做什么？")])
    # print(response)
    print(getattr(response, "content", response))
