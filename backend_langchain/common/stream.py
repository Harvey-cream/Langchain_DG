"""流式：事件编排 → SSE → 落库。"""
from __future__ import annotations

import json
import logging
import time
import traceback
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils import format_datetime
from backend_langchain.logger_func import log_exception_event
from common.agent import message_content_to_text
from common.extend import quick_agent_greeting_prompt, quick_interview_greeting_prompt
from common.skill_router import build_agent_skill_context, build_interview_skill_context
from config.config import get_qwen_chat_model
from Langchain_Agent.prompts import wrap_user_message

logger = logging.getLogger(__name__)

AgentKind = Literal["main", "interview"]
_MAX_ERR_LEN = 8000
_INTERRUPT_HINT = "（请在界面点击按钮确认或取消 PDF 导出。）"

_SKILL = {"main": build_agent_skill_context, "interview": build_interview_skill_context}
_QUICK = {"main": quick_agent_greeting_prompt, "interview": quick_interview_greeting_prompt}


def _stream_fn(kind: AgentKind):
    from Langchain_Agent.agents import stream_agent, stream_interview_agent

    return stream_agent if kind == "main" else stream_interview_agent


def _reply(events: list[dict]) -> str:
    parts: list[str] = []
    had_interrupt = False
    for evt in events:
        if evt.get("type") == "delta":
            parts.append(evt.get("text") or "")
        elif evt.get("type") == "interrupt":
            had_interrupt = True
    reply = "".join(parts).strip()
    return _INTERRUPT_HINT if had_interrupt and not reply else reply


async def stream_chat_events(
    kind: AgentKind,
    user_input: str,
    *,
    thread_id: str,
    temperature: float = 0.45,
    resume_pdf: bool | None = None,
    enable_web_search: bool = False,
) -> AsyncIterator[dict]:
    """统一事件流：delta / status / interrupt / pdf_ready。"""
    fn = _stream_fn(kind)
    extra = {"enable_web_search": enable_web_search} if kind == "main" else {}

    if resume_pdf is not None:
        async for evt in fn(
            thread_id=thread_id,
            temperature=temperature,
            resume_pdf=resume_pdf,
            **extra,
        ):
            yield evt
        return

    if not (user_input or "").strip():
        raise ValueError("user_input is empty")

    if quick := _QUICK[kind](user_input):
        llm = get_qwen_chat_model(temperature=temperature, streaming=True)
        async for chunk in llm.astream([HumanMessage(content=quick)]):
            if text := message_content_to_text(getattr(chunk, "content", chunk)):
                yield {"type": "delta", "text": text}
        return

    prompt = wrap_user_message(user_input, skill_context=_SKILL[kind](user_input))
    for attempt in range(2):
        tid = thread_id if attempt == 0 else f"{thread_id}:recover:{int(time.time() * 1000)}"
        try:
            async for evt in fn(
                prompt_text=prompt,
                thread_id=tid,
                temperature=temperature,
                **extra,
            ):
                yield evt
            return
        except Exception as e:  # noqa: BLE001
            if attempt == 0 and "No tool output found for function call" in str(e):
                continue
            raise


def sse_bytes(obj: dict) -> bytes:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")


def parse_resume_pdf(raw: Any) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    return str(raw).lower() in ("1", "true", "yes")


def parse_bool_flag(raw: Any, *, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def session_message_rows(sessions: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": s.id,
            "question": s.question,
            "ai_response": s.ai_response,
            "created_at": format_datetime(s.created_at),
        }
        for s in sessions
    ]


def _to_sse(evt: dict) -> bytes | None:
    t = evt.get("type")
    if t == "status" and evt.get("text") is not None:
        return sse_bytes({"type": "status", "text": evt["text"]})
    if t == "delta" and evt.get("text") is not None:
        return sse_bytes({"type": "delta", "text": evt["text"]})
    if t == "interrupt" and evt.get("kind") is not None:
        return sse_bytes(
            {"type": "interrupt", "kind": evt["kind"], "message": evt.get("message") or ""}
        )
    if t == "pdf_ready" and evt.get("url"):
        return sse_bytes(
            {
                "type": "pdf_ready",
                "url": evt["url"],
                "filename": evt.get("filename") or "export.pdf",
            }
        )
    return None


async def iter_sse_chat(
    *,
    db: AsyncSession,
    kind: AgentKind,
    user_input: str,
    thread_id: str,
    conversation_id: int,
    session_id: int,
    session_obj: Any,
    conversation: Any | None = None,
    log_prefix: str,
    resume_pdf: bool | None = None,
    enable_web_search: bool = False,
) -> AsyncIterator[bytes]:
    yield sse_bytes({"type": "meta", "conversation_id": conversation_id, "session_id": session_id})

    events: list[dict] = []
    err: BaseException | None = None

    try:
        async for item in stream_chat_events(
            kind,
            user_input,
            thread_id=thread_id,
            resume_pdf=resume_pdf,
            enable_web_search=enable_web_search,
        ):
            events.append(item)
            if chunk := _to_sse(item):
                yield chunk
    except Exception as e:  # noqa: BLE001
        err = e

    if any(e.get("type") in ("delta", "interrupt", "pdf_ready") for e in events):
        yield sse_bytes({"type": "stream_done"})

    if err is not None:
        tb = traceback.format_exception(type(err), err, err.__traceback__)
        detail = f"{err}\n\n--- traceback ---\n{''.join(tb)}"[:_MAX_ERR_LEN]
        session_obj.ai_response = f"[智能体调用失败]\n{detail}"
        if conversation is not None:
            conversation.updated_at = datetime.now(timezone.utc)
        await db.commit()
        yield sse_bytes({"type": "error", "message": str(err)})
        yield sse_bytes({"type": "done"})
        log_exception_event(logger, f"{log_prefix}_error", error=str(err))
        return

    session_obj.ai_response = _reply(events).strip()
    if conversation is not None:
        conversation.updated_at = datetime.now(timezone.utc)
    await db.commit()

    yield sse_bytes({"type": "done"})


def sse_response(gen: AsyncIterator[bytes]) -> StreamingResponse:
    return StreamingResponse(
        gen,
        media_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
