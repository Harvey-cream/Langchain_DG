from __future__ import annotations

import json
import re
from typing import Optional, Any
from uuid import UUID
from queue import Queue

from langchain_core.callbacks import BaseCallbackHandler


def _sse_bytes(obj: dict) -> bytes:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")


def _extract_after_final_answer(raw: str) -> Optional[str]:
    """
    ReAct 完整输出里，仅「Final Answer:」之后是面向用户的正文。
    若无该标记（非标准 ReAct），返回 None，由调用方决定是否使用全文。
    """
    if not (raw or "").strip():
        return None
    s = raw
    m = re.search(r"\nFinal Answer:\s*", s, re.IGNORECASE)
    if m:
        return s[m.end() :]
    m2 = re.match(r"^Final Answer:\s*", s, re.IGNORECASE)
    if m2:
        return s[m2.end() :]
    return None


def _user_visible_reply(full_agent_output: str) -> str:
    """落库与 SSE 展示用：优先只保留 Final Answer 后内容。"""
    s = (full_agent_output or "").strip()
    if not s:
        return ""
    after = _extract_after_final_answer(s)
    if after is not None:
        return after.strip()
    return s


# 与 token 流结束区分（queue 里不能仅用 None：个别实现可能传空 token）
_TOKEN_STREAM_END = object()


class _FinalAnswerOnlyTokenHandler(BaseCallbackHandler):
    """
    ReAct 每轮 LLM（Thought/Action/Observation）都会触发 on_llm_new_token；
    缓冲全文，仅在检测到「Final Answer:」之后，才把后续增量写入队列，避免思考与工具行泄露。
    """

    def __init__(self, q: Queue) -> None:
        self._q = q
        self._buf = ""
        self._fa_end: Optional[int] = None
        self._sent_tail_len = 0

    def on_llm_new_token(self, token: str, *, run_id: UUID, **kwargs: Any) -> None:
        if not token:
            return
        self._buf += token
        if self._fa_end is None:
            m = re.search(r"\nFinal Answer:\s*", self._buf, re.IGNORECASE)
            if m:
                self._fa_end = m.end()
            else:
                m2 = re.match(r"^Final Answer:\s*", self._buf, re.IGNORECASE)
                if m2:
                    self._fa_end = m2.end()
                else:
                    return
        tail = self._buf[self._fa_end :]
        new_part = tail[self._sent_tail_len :]
        if new_part:
            self._q.put(new_part)
            self._sent_tail_len = len(tail)
