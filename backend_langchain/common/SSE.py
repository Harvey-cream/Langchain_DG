from __future__ import annotations

import json
import os
import re
from typing import Optional, Any
from uuid import UUID
from queue import Queue

from langchain_core.callbacks import BaseCallbackHandler


def _sse_bytes(obj: dict) -> bytes:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")


# 模型常把「Final Answer」写成全角冒号、或加 **；与流式 handler 必须一致，否则会走补发全文。
# 注意：不能写 [:：] —— 在正则里 [: 会触发 POSIX 类解析，须用 (?::|：)。
_FINAL_ANSWER_SPLIT_RE = re.compile(
    r"(?:^|\n)\s*\*{0,2}Final Answer\*{0,2}\s*(?::|：)\s*",
    re.IGNORECASE | re.MULTILINE,
)
_FINAL_ANSWER_START_RE = re.compile(
    r"^\s*\*{0,2}Final Answer\*{0,2}\s*(?::|：)\s*",
    re.IGNORECASE,
)

# Final Answer 已结束后，模型仍续写一整轮 Question/Thought/…（同一条 completion 内），需截断。
# 除换行开头外，还有「**。」后直接 Thought:」等同行续写（无 \n），仅 \n 匹配会漏。
_REACT_RESTART_AFTER_FINAL_RE = re.compile(
    r"(?:"
    r"\n\s*(?:\*\*)?(?:Question|Thought|Action Input|Action|Observation)\s*(?::|：)\s*"
    r"|"
    r"\*\*\s*[。！？]\s*\*{0,2}Thought\s*(?::|：)\s*"
    r"|"
    r"(?<=[。！？])\s*Thought\s*(?::|：)\s*"
    r")",
    re.IGNORECASE,
)

# 已是「首段 Final Answer:」之后的正文时，去掉模型误重复写的第二处 Final Answer（提示词里词频过高易被模仿）。
# 冒号常被拆成下一个 token；若要求必须有 :，流会停在「Final」「 Answer」处，invoke 迟迟不返回 → SSE 只能一直 ping。
# 除换行外，还有「句末标点后同行」的 Final Answer:（如 。Final Answer:），无前导 \n 时原正则漏匹配。
_INLINE_DUP_FINAL_ANSWER_LABEL = re.compile(
    r"(?:"
    r"(?:\n[\t ]*){1,2}\*{0,2}Final Answer\*{0,2}\s*(?::|：)?\s*"
    r"|"
    r"(?<=[。！？,，、.])\s*\*{0,2}Final Answer\*{0,2}\s*(?::|：)?\s*"
    r")",
    re.IGNORECASE,
)


def _strip_duplicate_final_answer_labels_in_body(body: str) -> str:
    """去掉用户可见正文中重复出现的 Final Answer: 字面量。"""
    if not (body or "").strip():
        return body
    return _INLINE_DUP_FINAL_ANSWER_LABEL.sub("", body)


def _strip_repeated_react_after_final(body: str) -> str:
    """去掉 Final Answer 正文里再次出现的 ReAct 抬头（模型未停笔导致重复）。"""
    if not (body or "").strip():
        return body
    m = _REACT_RESTART_AFTER_FINAL_RE.search(body)
    if m:
        return body[: m.start()].rstrip()
    return re.sub(
        r"(?:\s+|^)(?:\*\*)?Thought\s*(?::|：)[^\n]*$",
        "",
        body,
        flags=re.IGNORECASE,
    ).rstrip()


def _extract_after_final_answer(raw: str) -> Optional[str]:
    """
    ReAct 完整输出里，仅「Final Answer」标记之后是面向用户的正文。
    若无该标记（非标准 ReAct），返回 None，由调用方决定是否使用全文。
    """
    if not (raw or "").strip():
        return None
    s = raw
    m = _FINAL_ANSWER_SPLIT_RE.search(s)
    if m:
        return s[m.end() :]
    m2 = _FINAL_ANSWER_START_RE.match(s)
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
        cleaned = _strip_repeated_react_after_final(after)
        cleaned = _strip_duplicate_final_answer_labels_in_body(cleaned)
        return cleaned.strip()
    return s


# 与 token 流结束区分（queue 里不能仅用 None：个别实现可能传空 token）
_TOKEN_STREAM_END = object()


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw.strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


class _FinalAnswerOnlyTokenHandler(BaseCallbackHandler):
    """
    ReAct 每轮 LLM（Thought/Action/Observation）都会触发 on_llm_new_token；
    缓冲全文，仅在检测到「Final Answer:」之后，才把后续增量写入队列，避免思考与工具行泄露。

    正文内若再次出现「Final Answer:」字面量：硬截断（不再入队后续 token），并保留尾部 holdback，
    避免流式分片在凑齐正则前把「\\n\\nFinal」误发给前端。
    """

    # 过小易把「Final Answer」拆片误发；过大则正文会像「攒一大段才推」——体感像非流式
    _HOLDBACK = 16
    # 单次可见增量再切片后发送（控制 delta 粗细度）
    _DELTA_CHUNK_CHARS = _int_env(
        "SSE_DELTA_CHUNK_CHARS",
        164,
        minimum=12,
        maximum=256,
    )
    # 累积到该阈值才发送，避免 token 很碎时退化成单字 delta。
    _DELTA_MIN_EMIT_CHARS = _int_env(
        "SSE_DELTA_MIN_EMIT_CHARS",
        64,
        minimum=8,
        maximum=128,
    )

    def __init__(self, q: Queue) -> None:
        self._q = q
        self._buf = ""
        self._fa_end: Optional[int] = None
        self._sent_tail_len = 0
        self._stopped = False
        self._stream_closed = False
        self._emit_buf = ""

    def _flush_emit_buffer(self, *, force: bool = False) -> None:
        """
        将 _emit_buf 分块推送到队列：
        - 非 force：至少达到 _DELTA_MIN_EMIT_CHARS 才发，优先在标点/空白处断开
        - force：收尾阶段把剩余内容全部发完
        """
        if not self._emit_buf:
            return
        split_chars = set("，。！？；：,.!?;:\n\t ")
        while self._emit_buf:
            if not force and len(self._emit_buf) < self._DELTA_MIN_EMIT_CHARS:
                return
            if len(self._emit_buf) <= self._DELTA_CHUNK_CHARS:
                if force or len(self._emit_buf) >= self._DELTA_MIN_EMIT_CHARS:
                    self._q.put(self._emit_buf)
                    self._emit_buf = ""
                return

            cut = self._DELTA_CHUNK_CHARS
            # 让切分尽量自然：在 chunk 末尾附近优先寻找标点/空白
            for i in range(self._DELTA_CHUNK_CHARS - 1, self._DELTA_MIN_EMIT_CHARS - 1, -1):
                if self._emit_buf[i] in split_chars:
                    cut = i + 1
                    break
            chunk = self._emit_buf[:cut]
            self._q.put(chunk)
            self._emit_buf = self._emit_buf[cut:]

    def on_llm_start(self, serialized: Any, prompts: Any, *, run_id: UUID, **kwargs: Any) -> None:
        """每轮 LLM 完成（含 LangGraph create_agent 多轮 tool调用）单独流式；清空缓冲，只推本轮正文。"""
        self._stream_closed = False
        self._buf = ""
        self._fa_end = None
        self._sent_tail_len = 0
        self._stopped = False
        self._emit_buf = ""

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """单次 LLM 生成结束：刷出 holdback。无 Final Answer 标记时（原生 tool calling 末轮常见）按全文可见处理。"""
        self._stream_closed = True
        if self._fa_end is None and self._buf.strip():
            visible = _user_visible_reply(self._buf)
            if visible:
                self._fa_end = 0
                self._buf = visible
        self._flush_deltas()
        self._flush_emit_buffer(force=True)

    def on_llm_new_token(self, token: str, *, run_id: UUID, **kwargs: Any) -> None:
        if self._stopped:
            return
        if not token:
            return
        self._buf += token
        if self._fa_end is None:
            m = _FINAL_ANSWER_SPLIT_RE.search(self._buf)
            if m:
                self._fa_end = m.end()
            else:
                m2 = _FINAL_ANSWER_START_RE.match(self._buf)
                if m2:
                    self._fa_end = m2.end()
                else:
                    return
        self._flush_deltas()

    def _flush_deltas(self) -> None:
        if self._stopped:
            return
        if self._fa_end is None:
            return

        raw_tail = self._buf[self._fa_end :]
        m_dup = _INLINE_DUP_FINAL_ANSWER_LABEL.search(raw_tail)
        if m_dup:
            clipped = raw_tail[: m_dup.start()].rstrip()
            self._stopped = True
            self._buf = self._buf[: self._fa_end + len(clipped)]
            tail = clipped
        else:
            tail = _strip_duplicate_final_answer_labels_in_body(raw_tail)

        tail_before_react = tail
        tail = _strip_repeated_react_after_final(tail)
        if len(tail) < len(tail_before_react):
            self._buf = self._buf[: self._fa_end + len(tail)]

        if self._sent_tail_len > len(tail):
            self._sent_tail_len = len(tail)

        use_holdback = not self._stopped and not self._stream_closed
        if use_holdback and len(tail) > self._HOLDBACK:
            safe_len = len(tail) - self._HOLDBACK
        else:
            safe_len = len(tail)

        new_part = tail[self._sent_tail_len : safe_len]
        if new_part:
            self._emit_buf += new_part
            self._flush_emit_buffer(force=self._stream_closed or self._stopped)
        self._sent_tail_len = safe_len
        # 已硬截断：立即通知 SSE 消费端结束 delta 等待，不必等 invoke() 收尾（否则会长时间只有 ping）
        if self._stopped:
            self._q.put(_TOKEN_STREAM_END)
