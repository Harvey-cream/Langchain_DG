from __future__ import annotations

import os
import threading

from langchain_core.embeddings import Embeddings

from common.hf_mirror import apply_hf_mirror_default

# 私有仓库可写默认 Key；环境变量 DASHSCOPE_API_KEY 优先。
_DEFAULT_DASHSCOPE_API_KEY = "sk-4e2f0a91dd2a4f36b7be88ffdcc0b294"

_embedding_cache: dict[str, Embeddings] = {}
_embedding_lock = threading.Lock()

# 与 env/provider.py 中选用 settings_pro.yaml 的环境一致时才走向量 API；
# 未设置 DJANGO_ENV、debug、dev、local 等均走本地 HuggingFace（与本地开发一致）。
_PRODUCTION_DJANGO_ENVS = frozenset({"production", "pro", "prod"})


def _is_production_embedding_env() -> bool:
    env = os.environ.get("DJANGO_ENV", "").strip().lower()
    return env in _PRODUCTION_DJANGO_ENVS


def _embedding_cache_key(model_name: str) -> str:
    if _is_production_embedding_env():
        api_model = os.environ.get(
            "DASHSCOPE_EMBEDDING_MODEL", "text-embedding-async-v2"
        ).strip()
        return f"dashscope:{api_model}"
    return f"hf:{model_name}"


def get_embedding_model(
    model_name: str,
    *,
    device: str = "cpu",
    normalize_embeddings: bool = True,
    batch_size: int = 32,
) -> Embeddings:
    """
    嵌入单例：仅当 DJANGO_ENV ∈ {production, pro, prod} 时用 DashScope 向量 API；其余一律 HuggingFace 本地模型。

    生产环境下 ``model_name`` 仅用于缓存键分区；实际模型名由 ``DASHSCOPE_EMBEDDING_MODEL`` 决定。
    注意：若 Chroma 库由本地模型构建，向量维度可能与 API 不一致，生产需用 API 重新建库或单独目录。
    """
    key = _embedding_cache_key(model_name)
    if key not in _embedding_cache:
        with _embedding_lock:
            if key not in _embedding_cache:
                if _is_production_embedding_env():
                    from langchain_community.embeddings import DashScopeEmbeddings

                    api_key = (
                        os.environ.get("DASHSCOPE_API_KEY", "").strip()
                        or _DEFAULT_DASHSCOPE_API_KEY
                    )
                    api_model = os.environ.get(
                        "DASHSCOPE_EMBEDDING_MODEL", "text-embedding-async-v2"
                    ).strip()
                    _embedding_cache[key] = DashScopeEmbeddings(
                        model=api_model,
                        dashscope_api_key=api_key,
                    )
                else:
                    apply_hf_mirror_default()
                    from langchain_community.embeddings import HuggingFaceEmbeddings

                    _embedding_cache[key] = HuggingFaceEmbeddings(
                        model_name=model_name,
                        model_kwargs={"device": device},
                        encode_kwargs={
                            "normalize_embeddings": normalize_embeddings,
                            "batch_size": batch_size,
                        },
                    )
    return _embedding_cache[key]
