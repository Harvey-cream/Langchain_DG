"""Memory Agent：LLM 结构化输出的 Pydantic 校验模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MemoryCandidate(BaseModel):
    memory_key: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="稳定英文点分 slug，如 pref.language、goal.job、stack.primary",
    )
    memory_type: Literal["preference", "goal", "constraint", "fact", "project"] = Field(
        description="记忆类型"
    )
    content: str = Field(..., min_length=1, max_length=1000, description="可注入 Prompt 的事实句")
    importance: float = Field(0.5, ge=0.0, le=1.0, description="重要度 0~1")


class ExtractResult(BaseModel):
    candidates: list[MemoryCandidate] = Field(
        default_factory=list,
        max_length=5,
        description="值得跨会话记住的候选；无可记则空列表",
    )


class DecideResult(BaseModel):
    action: Literal["insert", "update", "ignore"] = Field(description="写入动作")
    memory_key: str = Field(..., min_length=1, max_length=128, description="目标 memory_key")
    reason: str = Field("", description="简短理由")
