"""
Hugging Face Hub 国内镜像：huggingface_hub / sentence_transformers 会读环境变量 HF_ENDPOINT。

未设置时默认走 https://hf-mirror.com ，减轻直连 huggingface.co 慢或失败的问题。
若需官方源，可在 .env 或系统环境中设置：
  HF_ENDPOINT=https://huggingface.co
或删除 HF_ENDPOINT 前先 export 覆盖（本模块用 setdefault，已有值不会被覆盖）。
"""
from __future__ import annotations

import os

_DEFAULT_MIRROR = "https://hf-mirror.com"


def apply_hf_mirror_default() -> None:
    """在首次下载/加载 HF 模型前调用；已设置 HF_ENDPOINT 时不修改。"""
    os.environ.setdefault("HF_ENDPOINT", _DEFAULT_MIRROR)
