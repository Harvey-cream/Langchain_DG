from __future__ import annotations

import json
import os
import re
from typing import Optional, Any, Callable
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


# --- 自然语言优先 + <tool> 隐式调用：流式剥标签，不透出 Thought/Action/Observation ---
_TOOL_BLOCK_RE = re.compile(
    r"<tool\s+name\s*=\s*[\"']([^\"']+)[\"']\s*>(.*?)</tool>",
    re.DOTALL | re.IGNORECASE,
)
_REACT_LINE_ONLY_RE = re.compile(
    r"(?m)^\s*(?:Question|Thought|Action|Action Input|Observation)\s*(?::|：).*$",
    re.IGNORECASE,
)
_INLINE_FA_STRIP_RE = re.compile(
    r"(?:^|\n)\s*\*{0,2}Final Answer\*{0,2}\s*(?::|：)\s*",
    re.IGNORECASE | re.MULTILINE,
)


def _strip_tool_blocks_and_incomplete(raw: str) -> str:
    """去掉完整 <tool>...</tool>；尾部未闭合的 <tool… 与孤悬的 `<` 不输出。"""
    s = _TOOL_BLOCK_RE.sub("", raw)
    m = re.search(r"<tool[^>]*$", s, re.IGNORECASE)
    if m:
        s = s[: m.start()]
    s = re.sub(r"<\s*$", "", s)
    return s


def _inline_visible_clean(raw: str) -> str:
    s = _strip_tool_blocks_and_incomplete(raw)
    s = _REACT_LINE_ONLY_RE.sub("", s)
    s = _INLINE_FA_STRIP_RE.sub("", s)
    return s


def user_visible_reply_inline(full_agent_output: str) -> str:
    """落库用：与流式 handler 规则一致，剥工具标签与 ReAct 行。"""
    s = (full_agent_output or "").strip()
    if not s:
        return ""
    return _inline_visible_clean(s).strip()


class _NaturalLanguageToolFilterHandler(BaseCallbackHandler):
    """
    自然语言先流式可见；<tool>...</tool> 与 Thought/Action/Observation 行不进入队列。
    多轮工具：每轮 on_llm_start 重置本轮缓冲，on_llm_end 将本轮可见正文拼入 _session_visible。
    """

    _DELTA_CHUNK_CHARS = _int_env(
        "SSE_DELTA_CHUNK_CHARS",
        164,
        minimum=12,
        maximum=256,
    )
    _DELTA_MIN_EMIT_CHARS = _int_env(
        "SSE_DELTA_MIN_EMIT_CHARS",
        12,
        minimum=4,
        maximum=128,
    )

    def __init__(self, q: Queue, trace_cb: Optional[Callable[[str], None]] = None) -> None:
        self._q = q
        self._trace_cb = trace_cb
        self._round_raw = ""
        self._vis_consumed = ""
        self._emit_buf = ""
        self._session_visible = ""
        self._first_token_traced = False
        self._first_delta_traced = False

    def final_user_visible(self) -> str:
        return (self._session_visible or "").strip()

    def _trace(self, event: str) -> None:
        if not self._trace_cb:
            return
        try:
            self._trace_cb(event)
        except Exception:
            return

    def _flush_emit_buffer(self, *, force: bool = False) -> None:
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
            for i in range(self._DELTA_CHUNK_CHARS - 1, self._DELTA_MIN_EMIT_CHARS - 1, -1):
                if self._emit_buf[i] in split_chars:
                    cut = i + 1
                    break
            chunk = self._emit_buf[:cut]
            self._q.put(chunk)
            self._emit_buf = self._emit_buf[cut:]

    def on_llm_start(self, serialized: Any, prompts: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._round_raw = ""
        self._vis_consumed = ""
        self._emit_buf = ""

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        vis = _inline_visible_clean(self._round_raw)
        if not vis.startswith(self._vis_consumed):
            self._vis_consumed = ""
        delta = vis[len(self._vis_consumed) :]
        if delta:
            if not self._first_delta_traced:
                self._first_delta_traced = True
                self._trace("first_delta")
            self._emit_buf += delta
        self._vis_consumed = vis
        self._flush_emit_buffer(force=True)
        if vis.strip():
            if self._session_visible.strip():
                self._session_visible += "\n\n"
            self._session_visible += vis

    def on_llm_new_token(self, token: str, *, run_id: UUID, **kwargs: Any) -> None:
        if not token:
            return
        if not self._first_token_traced:
            self._first_token_traced = True
            self._trace("first_token")
        self._round_raw += token
        vis = _inline_visible_clean(self._round_raw)
        if not vis.startswith(self._vis_consumed):
            self._vis_consumed = ""
        delta = vis[len(self._vis_consumed) :]
        if not delta:
            return
        if not self._first_delta_traced:
            self._first_delta_traced = True
            self._trace("first_delta")
        self._vis_consumed = vis
        self._emit_buf += delta
        self._flush_emit_buffer(force=False)


