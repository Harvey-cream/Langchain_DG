from __future__ import annotations

import os
import threading
import logging

from langchain_core.embeddings import Embeddings

from app.settings import is_production
from app.services.extend import apply_hf_mirror_default
from config.config import (
    DEFAULT_HF_MODEL,
    HF_EMBEDDING_BATCH_SIZE,
    DASHSCOPE_EMBEDDING_BASE_URL,
    dashscope_api_key,
    dashscope_dimensions,
    dashscope_embedding_batch_size,
    dashscope_model_name,
)

_embedding_cache: dict[str, Embeddings] = {}
_embedding_lock = threading.Lock()

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _use_hf_offline_mode() -> bool:
    return _env_flag("HF_LOCAL_FILES_ONLY", True)


def _dashscope_cache_key() -> str:
    return f"dashscope:{dashscope_model_name()}:{dashscope_dimensions()}"


def _dashscope_openai_compatible_embeddings(api_key: str, model: str, *, dimensions: int) -> Embeddings:
    from langchain_openai import OpenAIEmbeddings

    kwargs: dict = {
        "model": model,
        "api_key": api_key,
        "base_url": DASHSCOPE_EMBEDDING_BASE_URL,
        "check_embedding_ctx_length": False,
        "chunk_size": dashscope_embedding_batch_size(),
    }
    if model in ("text-embedding-v3", "text-embedding-v4"):
        kwargs["dimensions"] = dimensions
    return OpenAIEmbeddings(**kwargs)


def get_rag_embedding_model() -> Embeddings:
    """RAG 建库与查询共用；必须与 build_rag_knowledge.py 一致（DashScope）。"""
    if not dashscope_api_key():
        raise RuntimeError(
            "RAG 需要 DashScope 嵌入：请在 settings_*.yaml 的 dashscope.api_key "
            "或环境变量 DASHSCOPE_API_KEY 中设置（与建库脚本相同）"
        )
    return get_dashscope_embedding_model()


def get_dashscope_embedding_model() -> Embeddings:
    """百炼向量 API（建库脚本与生产 RAG 统一使用）。"""
    key = _dashscope_cache_key()
    if key not in _embedding_cache:
        with _embedding_lock:
            if key not in _embedding_cache:
                model = dashscope_model_name()
                dim = dashscope_dimensions()
                batch = dashscope_embedding_batch_size()
                logger.info(
                    "embedding init: backend=dashscope model=%s dimensions=%s batch=%s",
                    model,
                    dim,
                    batch,
                )
                _embedding_cache[key] = _dashscope_openai_compatible_embeddings(
                    dashscope_api_key(), model, dimensions=dim
                )
    return _embedding_cache[key]


def get_embedding_model(
    model_name: str,
    *,
    device: str = "cpu",
    normalize_embeddings: bool = True,
    batch_size: int | None = None,
) -> Embeddings:
    """
    嵌入单例：已配置 DASHSCOPE_API_KEY 时（含本地 debug）走 DashScope；
    否则 debug 回退 HuggingFace 本地（另装 torch CPU 版）。
    """
    if is_production or dashscope_api_key():
        return get_dashscope_embedding_model()

    bs = batch_size if batch_size is not None else HF_EMBEDDING_BATCH_SIZE
    key = f"hf:{model_name}"
    if key not in _embedding_cache:
        with _embedding_lock:
            if key not in _embedding_cache:
                apply_hf_mirror_default()
                from langchain_community.embeddings import HuggingFaceEmbeddings

                offline_mode = _use_hf_offline_mode()
                if offline_mode:
                    os.environ.setdefault("HF_HUB_OFFLINE", "1")
                    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
                logger.info(
                    "embedding init: backend=huggingface model=%s offline_mode=%s",
                    model_name,
                    offline_mode,
                )
                _embedding_cache[key] = HuggingFaceEmbeddings(
                    model_name=model_name,
                    model_kwargs={
                        "device": device,
                        "local_files_only": offline_mode,
                    },
                    encode_kwargs={
                        "normalize_embeddings": normalize_embeddings,
                        "batch_size": bs,
                    },
                )
    return _embedding_cache[key]
