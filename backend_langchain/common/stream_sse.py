"""FastAPI SSE 流式响应。"""
from __future__ import annotations

import asyncio
import json
import logging
import traceback
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from typing import Any

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils import format_datetime
from backend_langchain.logger_func import log_exception_event
from common.stream_runner import AgentKind, reply_from_events, stream_chat_events

logger = logging.getLogger(__name__)

_PING_INTERVAL_SEC = 2.0
_MAX_ERROR_DETAIL_LEN = 8000
_FALLBACK_DELTA_CHARS = 16


def sse_bytes(obj: dict) -> bytes:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")


def parse_resume_pdf(raw: Any) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    return str(raw).lower() in ("1", "true", "yes")


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


def parse_bool_flag(raw: Any, *, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _sse_from_event(item: dict) -> bytes | None:
    t = item.get("type")
    if t == "status" and item.get("text") is not None:
        return sse_bytes({"type": "status", "text": item["text"]})
    if t == "delta" and item.get("text") is not None:
        return sse_bytes({"type": "delta", "text": item["text"]})
    if t == "interrupt" and item.get("kind") is not None:
        return sse_bytes(
            {
                "type": "interrupt",
                "kind": item["kind"],
                "message": item.get("message") or "",
            }
        )
    if t == "pdf_ready" and item.get("url"):
        return sse_bytes(
            {
                "type": "pdf_ready",
                "url": item["url"],
                "filename": item.get("filename") or "export.pdf",
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
    trace_event: Callable[..., None] | None = None,
) -> AsyncIterator[bytes]:
    yield sse_bytes({"type": "meta", "conversation_id": conversation_id, "session_id": session_id})

    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    cancel_evt = asyncio.Event()

    async def _worker() -> None:
        try:
            async for evt in stream_chat_events(
                kind,
                user_input,
                thread_id=thread_id,
                trace_cb=trace_event,
                resume_pdf=resume_pdf,
                enable_web_search=enable_web_search,
                cancel_event=cancel_evt,
            ):
                await queue.put(evt)
        except Exception as e:  # noqa: BLE001
            await queue.put({"type": "_error", "error": e})
        finally:
            await queue.put(None)

    task = asyncio.create_task(_worker())
    events: list[dict] = []
    tokens_received = 0
    interrupt_sent = False
    pdf_ready_sent = False
    stream_done_sent = False
    err: BaseException | None = None

    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=_PING_INTERVAL_SEC)
        except asyncio.TimeoutError:
            if not task.done():
                yield sse_bytes({"type": "ping"})
            continue
        if item is None:
            break
        if item.get("type") == "_error":
            err = item["error"]
            break
        events.append(item)
        if item.get("type") == "delta":
            tokens_received += 1
        elif item.get("type") == "interrupt":
            interrupt_sent = True
        elif item.get("type") == "pdf_ready":
            pdf_ready_sent = True
        chunk = _sse_from_event(item)
        if chunk:
            yield chunk

    if not task.done():
        cancel_evt.set()
        await task

    if tokens_received or interrupt_sent or pdf_ready_sent:
        yield sse_bytes({"type": "stream_done"})
        if trace_event:
            trace_event("stream_done", tokens_received=tokens_received)
        stream_done_sent = True

    if err is not None:
        tb = traceback.format_exception(type(err), err, err.__traceback__)
        detail = f"{str(err)}\n\n--- traceback ---\n{''.join(tb)}"
        if len(detail) > _MAX_ERROR_DETAIL_LEN:
            detail = detail[:_MAX_ERROR_DETAIL_LEN] + "\n…(已截断)"
        session_obj.ai_response = f"[智能体调用失败]\n{detail}"
        if conversation is not None:
            conversation.updated_at = datetime.now(timezone.utc)
        await db.commit()
        yield sse_bytes({"type": "error", "message": str(err)})
        yield sse_bytes({"type": "done"})
        if trace_event:
            trace_event("done", status="agent_error", tokens_received=tokens_received)
        log_exception_event(logger, f"{log_prefix}_error", error=str(err))
        return

    stored = reply_from_events(events).strip()
    session_obj.ai_response = stored
    if conversation is not None:
        conversation.updated_at = datetime.now(timezone.utc)
    await db.commit()

    if not tokens_received and stored:
        for i in range(0, len(stored), _FALLBACK_DELTA_CHARS):
            yield sse_bytes({"type": "delta", "text": stored[i : i + _FALLBACK_DELTA_CHARS]})
        if not stream_done_sent:
            yield sse_bytes({"type": "stream_done"})
            if trace_event:
                trace_event("stream_done", tokens_received=tokens_received)

    yield sse_bytes({"type": "done"})
    if trace_event:
        trace_event("done", status="ok", tokens_received=tokens_received)


def sse_response(gen: AsyncIterator[bytes]) -> StreamingResponse:
    return StreamingResponse(
        gen,
        media_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
