"""
全局配置：知识库 / 嵌入 / LLM。
应用级配置（Postgres、LLM、DashScope、RAG）统一见 app.settings + env/settings_*.yaml。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from app.settings import dashscope_config, llm_config, rag_config
from config.failover import FailoverLLM

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR_NAME = "knowledge"

_rag = rag_config()
COLLECTION = _rag["collection"]
USER_COLLECTION = _rag.get("user_collection") or "user_knowledge"
RECALL_K = _rag["recall_k"]
RERANK_TOP_K = _rag["rerank_top_k"]
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
CORPUS_USER = "user"

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
        CORPUS_USER: frozenset({"uploads"}),
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


_chain_logged = False


def _resolve_model_chain(llm: dict[str, Any]) -> list[str]:
    """生效链 = [主模型] + 兜底模型（去空、去重、保序；主模型重复出现只保留一次）。"""
    primary = str(llm.get("model") or "").strip()
    if not primary:
        raise RuntimeError(
            "未配置对话 LLM 主模型：请设置 LLM_AGENT_MODEL（或 settings yaml llm.model）"
        )
    chain = [primary]
    for name in llm.get("fallback_models") or []:
        candidate = str(name).strip()
        if candidate and candidate not in chain:
            chain.append(candidate)
    return chain


def _log_chain_once(chain: list[str]) -> None:
    global _chain_logged
    if _chain_logged:
        return
    _chain_logged = True
    logger.info("[LLM] chain = %s", " -> ".join(chain))


def _build_chat_model(
    llm: dict[str, Any], model_name: str, *, temperature: float, streaming: bool
) -> Any:
    common = dict(
        model=model_name,
        api_key=llm["api_key"],
        base_url=llm["base_url"],
        temperature=temperature,
    )
    if streaming:
        return _AgentStreamChatOpenAI(**common, streaming=True)
    return ChatOpenAI(**common)


def get_qwen_chat_model(temperature: float = 0.7, *, streaming: bool = False) -> Any:
    """返回对话 LLM：链上每个模型各建一个原生实例，包成顺序兜底。

    调用方零改动——既可 invoke/astream，也可 bind_tools / with_structured_output。
    无兜底配置时返回原生实例，行为与改造前完全一致。
    """
    llm = llm_config()
    if not llm["api_key"]:
        raise RuntimeError(
            "未配置对话 LLM：请在 settings_*.yaml 的 llm.api_key 或环境变量 "
            "LLM_AGENT_API_KEY 中设置"
        )
    chain = _resolve_model_chain(llm)
    _log_chain_once(chain)

    instances = [
        _build_chat_model(llm, name, temperature=temperature, streaming=streaming)
        for name in chain
    ]
    if len(instances) == 1:
        return instances[0]
    return FailoverLLM(instances, labels=chain)


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage

    llm = get_qwen_chat_model()
    print("模型加载成功，正在回答...")
    response = llm.invoke([HumanMessage(content="你是哪个模型")])
    print(getattr(response, "content", response))
