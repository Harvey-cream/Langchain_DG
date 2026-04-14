from __future__ import annotations

import threading

from langchain_community.embeddings import HuggingFaceEmbeddings

from common.hf_mirror import apply_hf_mirror_default

_embedding_cache: dict[str, HuggingFaceEmbeddings] = {}
_embedding_lock = threading.Lock()


def get_embedding_model(
    model_name: str,
    *,
    device: str = "cpu",
    normalize_embeddings: bool = True,
    batch_size: int = 32,
) -> HuggingFaceEmbeddings:
    """
    统一管理 embedding 模型单例：
    - 相同 model_name 在同一进程只初始化一次
    - 便于全项目复用与集中配置
    """
    if model_name not in _embedding_cache:
        with _embedding_lock:
            if model_name not in _embedding_cache:
                apply_hf_mirror_default()
                _embedding_cache[model_name] = HuggingFaceEmbeddings(
                    model_name=model_name,
                    model_kwargs={"device": device},
                    encode_kwargs={
                        "normalize_embeddings": normalize_embeddings,
                        "batch_size": batch_size,
                    },
                )
    return _embedding_cache[model_name]
