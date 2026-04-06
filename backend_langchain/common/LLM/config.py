import os
from typing import Any, Optional

os.environ.setdefault("CHROMA_TELEMETRY", "0")

from dotenv import load_dotenv

# OpenAI 兼容 API：用 langchain_openai（与 openai 1.x SDK 一致），勿再用 langchain_community 里已弃用的 ChatOpenAI
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.messages import BaseMessage

# from langchain_community.chat_models import ChatOllama
# from langchain_community.chat_models import ChatTongyi

load_dotenv()

# # ---------- 阿里云 DashScope 千问（备用）----------
# # DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
# # QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-math-turbo")
# # ---------------------------------------------------------------------------

# # ---------- 本地 Ollama（备用）----------
# # OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
# # OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
# # ---------------------------------------------------------------------------

# OpenAI 兼容网关；base_url 需含 /v1（与官方 OpenAI 客户端约定一致）
LLM_AGENT_BASE_URL = os.getenv("LLM_AGENT_BASE_URL", "https://gpt-agent.cc/v1")
LLM_AGENT_API_KEY = os.getenv("LLM_AGENT_API_KEY", "sk-dpsaFmP9J9PHpe75yyJdvQ1xkgmfIF1oPru31peFWuzPrZ6B")
LLM_AGENT_MODEL = os.getenv("LLM_AGENT_MODEL", "gpt-5.4")


class _AgentStreamChatOpenAI(ChatOpenAI):
    """
    ReAct 的 LLMChain 调用 generate_prompt 时不会传入 stream=True；
    langchain_core 只有在 kwargs['stream'] 为 True 时才走 _stream + on_llm_new_token，
    否则整段 _generate 一次返回，前端 SSE 会像「非流式」只收到一块。
    在 streaming=True 时强制把 stream 传入 _generate_with_cache。
    """

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
    当前使用 OpenAI 兼容 HTTP API（默认 LLM_AGENT_BASE_URL，如 gpt-agent.cc）；Langchain_Agent 经此函数接入。
    """
    common = dict(
        model=LLM_AGENT_MODEL,
        api_key=LLM_AGENT_API_KEY,
        base_url=LLM_AGENT_BASE_URL,
        temperature=temperature,
        streaming=streaming,
    )
    if streaming:
        return _AgentStreamChatOpenAI(**common)
    return ChatOpenAI(**common)


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage

    llm = get_qwen_chat_model()
    print("模型加载成功，正在回答...")
    response = llm.invoke([HumanMessage(content="你是哪个模型")])
    # print(response)
    print(getattr(response, "content", response))

# 原 DashScope 千问（取消注释并改 get_qwen_chat_model 的 return）：
# return ChatTongyi(
#     model=QWEN_MODEL,
#     dashscope_api_key=DASHSCOPE_API_KEY,
#     temperature=temperature,
#     streaming=streaming,
# )

# 原 Ollama：
# return ChatOllama(
#     model=OLLAMA_MODEL,
#     base_url=OLLAMA_BASE_URL,
#     temperature=temperature,
#     streaming=streaming,
# )
