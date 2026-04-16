from __future__ import annotations

import os
import threading
import logging

from langchain_core.embeddings import Embeddings

from common.extend import apply_hf_mirror_default

# 私有仓库可写默认 Key；环境变量 DASHSCOPE_API_KEY 优先。
_DEFAULT_DASHSCOPE_API_KEY = "sk-4e2f0a91dd2a4f36b7be88ffdcc0b294"

_embedding_cache: dict[str, Embeddings] = {}
_embedding_lock = threading.Lock()

# 与 env/provider.py 中选用 settings_pro.yaml 的环境一致时才走向量 API；
# 未设置 DJANGO_ENV、debug、dev、local 等均走本地 HuggingFace（与本地开发一致）。
_PRODUCTION_DJANGO_ENVS = frozenset({"production", "pro", "prod"})
logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _use_hf_offline_mode() -> bool:
    # 默认离线优先；如需联网探测可设 HF_LOCAL_FILES_ONLY=0
    return _env_flag("HF_LOCAL_FILES_ONLY", True)


def _is_production_embedding_env() -> bool:
    env = os.environ.get("DJANGO_ENV", "").strip().lower()
    return env in _PRODUCTION_DJANGO_ENVS


def _embedding_cache_key(model_name: str) -> str:
    if _is_production_embedding_env():
        api_model = os.environ.get(
            "DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v3"
        ).strip()
        return f"dashscope:{api_model}"
    return f"hf:{model_name}"


def _dashscope_openai_compatible_embeddings(api_key: str, model: str) -> Embeddings:
    """
    百炼 text-embedding-v3/v4 等须走 OpenAI 兼容 embeddings接口。
    langchain_community.DashScopeEmbeddings（旧 TextEmbedding.call + text_type）易触发
    InvalidParameter / input.url 等与同步向量接口不匹配的错误。
    文档：https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api
    """
    from langchain_openai import OpenAIEmbeddings

    base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    kwargs: dict = {
        "model": model,
        "api_key": api_key,
        "base_url": base,
        "check_embedding_ctx_length": False,
    }
    if model in ("text-embedding-v3", "text-embedding-v4"):
        dim = os.environ.get("DASHSCOPE_EMBEDDING_DIMENSIONS", "1024").strip()
        if dim.isdigit():
            kwargs["dimensions"] = int(dim)
    return OpenAIEmbeddings(**kwargs)


def get_embedding_model(
    model_name: str,
    *,
    device: str = "cpu",
    normalize_embeddings: bool = True,
    batch_size: int = 32,
) -> Embeddings:
    """
    嵌入单例：仅当 DJANGO_ENV ∈ {production, pro, prod} 时用 DashScope 向量 API；其余一律 HuggingFace 本地模型。

    生产环境下 ``model_name`` 仅用于缓存键分区；实际模型名由 ``DASHSCOPE_EMBEDDING_MODEL`` 决定
    （默认 text-embedding-v3，经百炼 OpenAI 兼容 ``/v1/embeddings``；v3/v4 可配 ``DASHSCOPE_EMBEDDING_DIMENSIONS``）。
    注意：若 Chroma 库由本地模型构建，向量维度可能与 API 不一致，生产需用 API 重新建库或单独目录。
    """
    key = _embedding_cache_key(model_name)
    if key not in _embedding_cache:
        with _embedding_lock:
            if key not in _embedding_cache:
                if _is_production_embedding_env():
                    api_key = (
                        os.environ.get("DASHSCOPE_API_KEY", "").strip()
                        or _DEFAULT_DASHSCOPE_API_KEY
                    )
                    api_model = os.environ.get(
                        "DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v3"
                    ).strip()
                    _embedding_cache[key] = _dashscope_openai_compatible_embeddings(
                        api_key, api_model
                    )
                else:
                    apply_hf_mirror_default()
                    from langchain_community.embeddings import HuggingFaceEmbeddings

                    offline_mode = _use_hf_offline_mode()
                    if offline_mode:
                        # 让底层 huggingface_hub/transformers 进入离线模式，避免网络探测重试拖慢请求。
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
                            "batch_size": batch_size,
                        },
                    )
    return _embedding_cache[key]
