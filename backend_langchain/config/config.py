"""
全局配置：知识库 / 嵌入 / LLM。
应用级配置（MySQL、LLM、DashScope、RAG）统一见 app.settings + env/settings_*.yaml。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

os.environ.setdefault("CHROMA_TELEMETRY", "0")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from app.settings import dashscope_config, llm_config, rag_config

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR_NAME = "Langchain_knowledge"

_rag = rag_config()
COLLECTION = _rag["collection"]
RECALL_K = _rag["recall_k"]
RERANK_TOP_K = _rag["rerank_top_k"]
RAG_MAX_DISTANCE = _rag["max_distance"]
QUERY_REWRITE_MAX_QUESTIONS = _rag["query_rewrite_max_questions"]
QUERY_REWRITE_CONTEXT_TURNS = _rag["query_rewrite_context_turns"]
DOCS_AGENT = _rag["docs_agent"]
DOCS_INTERVIEW = _rag["docs_interview"]
DEFAULT_CHUNK_SIZE = _rag["chunk_size"]
DEFAULT_CHUNK_OVERLAP = _rag["chunk_overlap"]
DEFAULT_HF_MODEL = _rag["hf_embedding_model"]
HF_EMBEDDING_BATCH_SIZE = _rag["hf_embedding_batch_size"]

CORPUS_AGENT = "agent"
CORPUS_INTERVIEW = "interview"

DOMAIN_LABELS: dict[str, str] = {
    "ai_programming": "AI 编程",
    "openclaw": "OpenClaw",
    "vibe_coding": "Vibe Coding",
    "learn_programing": "学习路线与面试",
    "interview_llm": "AI 大模型面试",
    "interview_java": "Java 面试",
    "interview_vue": "Vue 面试",
}


def knowledge_root() -> Path:
    return BASE_DIR / KNOWLEDGE_DIR_NAME


def chroma_path() -> Path:
    return knowledge_root() / "chroma" / COLLECTION


def list_domains(corpus: str) -> frozenset[str]:
    root = knowledge_root()
    if corpus == CORPUS_AGENT:
        base = root / DOCS_AGENT
    elif corpus == CORPUS_INTERVIEW:
        base = root / DOCS_INTERVIEW
    else:
        return frozenset()
    if not base.is_dir():
        return frozenset()
    return frozenset(p.name for p in base.iterdir() if p.is_dir())


def get_domains() -> dict[str, frozenset[str]]:
    return {
        CORPUS_AGENT: list_domains(CORPUS_AGENT),
        CORPUS_INTERVIEW: list_domains(CORPUS_INTERVIEW),
    }


def dashscope_api_key() -> str:
    return dashscope_config()["api_key"]


def dashscope_model_name() -> str:
    return dashscope_config()["embedding_model"]


def dashscope_dimensions() -> int:
    return int(dashscope_config()["embedding_dimensions"])


def dashscope_embedding_batch_size() -> int:
    return int(dashscope_config()["embedding_batch_size"])


def dashscope_rerank_model() -> str:
    return str(dashscope_config()["rerank_model"])


DASHSCOPE_EMBEDDING_BASE_URL = dashscope_config()["embedding_base_url"]


class _AgentStreamChatOpenAI(ChatOpenAI):
    """流式场景强制 stream=True，保证 LangGraph SSE 逐 token 输出。"""

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
    llm = llm_config()
    if not llm["api_key"]:
        raise RuntimeError(
            "未配置对话 LLM：请在 settings_*.yaml 的 llm.api_key 或环境变量 OPENAI_API_KEY 中设置"
        )
    common = dict(
        model=llm["model"],
        api_key=llm["api_key"],
        base_url=llm["base_url"],
        temperature=temperature,
    )
    if streaming:
        return _AgentStreamChatOpenAI(**common, streaming=True)
    return ChatOpenAI(**common)


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage

    llm = get_qwen_chat_model()
    print("模型加载成功，正在回答...")
    response = llm.invoke([HumanMessage(content="你是哪个模型")])
    print(getattr(response, "content", response))
