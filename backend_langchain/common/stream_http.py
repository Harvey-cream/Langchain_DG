"""Django SSE 流式响应：agent / interview 共用。"""

from __future__ import annotations

import json
import logging
import queue
import threading
import traceback
from typing import Any, Callable, Iterator, Optional

from django.db import close_old_connections
from django.http import StreamingHttpResponse

from backend_langchain.logger_func import (
    log_error_event,
    log_exception_event,
    log_warning_event,
)

logger = logging.getLogger(__name__)

STREAM_END = object()


def sse_bytes(obj: dict) -> bytes:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")


_MAX_ERROR_DETAIL_LEN = 8000
_PING_INTERVAL_SEC = 2.0
_WORKER_JOIN_TIMEOUT_SEC = 120.0
_WORKER_JOIN_AFTER_CANCEL_SEC = 30.0
_FALLBACK_DELTA_CHARS = 16

RunStreamFn = Callable[[queue.Queue, threading.Event], str]


def parse_resume_pdf(raw: Any) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    return str(raw).lower() in ("1", "true", "yes")


def session_message_rows(qs) -> list[dict[str, Any]]:
    from common_web.utils import format_datetime

    return [
        {
            "id": s.id,
            "question": s.question,
            "ai_response": s.ai_response,
            "created_at": format_datetime(s.created_at),
        }
        for s in qs
    ]


def iter_sse_chat(
    *,
    conversation_id: int,
    session_id: int,
    run_stream: RunStreamFn,
    session_obj: Any,
    conversation: Any,
    log_prefix: str,
    trace_event: Optional[Callable[..., None]] = None,
) -> Iterator[bytes]:
    result_q: queue.Queue = queue.Queue(maxsize=1)
    token_q: queue.Queue = queue.Queue()
    cancel_evt = threading.Event()

    def worker() -> None:
        close_old_connections()
        try:
            reply = run_stream(token_q, cancel_evt)
            result_q.put(("ok", reply))
        except Exception as e:  # noqa: BLE001
            result_q.put(("err", (e, traceback.format_exc())))
        finally:
            token_q.put(STREAM_END)
            close_old_connections()

    yield sse_bytes(
        {"type": "meta", "conversation_id": conversation_id, "session_id": session_id}
    )

    thread = threading.Thread(target=worker, daemon=True, name=f"{log_prefix}-worker")
    thread.start()

    tokens_received = 0
    got_end = False
    interrupt_sent = False
    pdf_ready_sent = False

    while True:
        try:
            item = token_q.get(timeout=_PING_INTERVAL_SEC)
        except queue.Empty:
            if thread.is_alive():
                yield sse_bytes({"type": "ping"})
            else:
                break
            continue
        if item is STREAM_END:
            got_end = True
            break
        if not isinstance(item, dict):
            continue
        t = item.get("type")
        if t == "status" and item.get("text") is not None:
            yield sse_bytes({"type": "status", "text": item["text"]})
        elif t == "delta" and item.get("text") is not None:
            tokens_received += 1
            yield sse_bytes({"type": "delta", "text": item["text"]})
        elif t == "interrupt" and item.get("kind") is not None:
            interrupt_sent = True
            yield sse_bytes(
                {
                    "type": "interrupt",
                    "kind": item["kind"],
                    "message": item.get("message") or "",
                }
            )
        elif t == "pdf_ready" and item.get("url"):
            pdf_ready_sent = True
            yield sse_bytes(
                {
                    "type": "pdf_ready",
                    "url": item["url"],
                    "filename": item.get("filename") or "export.pdf",
                }
            )

    peek_kind = peek_payload = None
    if got_end:
        try:
            peek_kind, peek_payload = result_q.get_nowait()
        except queue.Empty:
            pass

    stream_done_sent = False
    if got_end and (tokens_received or interrupt_sent or pdf_ready_sent):
        yield sse_bytes({"type": "stream_done"})
        if trace_event:
            trace_event("stream_done", tokens_received=tokens_received)
        stream_done_sent = True

    thread.join(timeout=_WORKER_JOIN_TIMEOUT_SEC)
    if thread.is_alive():
        cancel_evt.set()
        log_warning_event(
            logger,
            f"{log_prefix}_worker_join_timeout",
            tokens_received=tokens_received,
        )
        thread.join(timeout=_WORKER_JOIN_AFTER_CANCEL_SEC)
        if thread.is_alive():
            log_error_event(logger, f"{log_prefix}_worker_still_alive", tokens_received=tokens_received)

    kind, payload = peek_kind, peek_payload
    if kind is None:
        try:
            kind, payload = result_q.get_nowait()
        except queue.Empty:
            session_obj.ai_response = "[智能体调用失败]\n未收到执行结果"
            session_obj.save()
            conversation.save()
            if not got_end:
                yield sse_bytes({"type": "error", "message": "智能体未返回结果"})
            elif tokens_received:
                log_warning_event(
                    logger,
                    f"{log_prefix}_result_queue_empty_with_deltas",
                    tokens_received=tokens_received,
                )
            else:
                log_error_event(logger, f"{log_prefix}_result_queue_empty")
            yield sse_bytes({"type": "done"})
            if trace_event:
                trace_event("done", status="result_queue_empty", tokens_received=tokens_received)
            return

    if kind == "err":
        err, tb = payload
        detail = f"{str(err)}\n\n--- traceback ---\n{tb}"
        if len(detail) > _MAX_ERROR_DETAIL_LEN:
            detail = detail[:_MAX_ERROR_DETAIL_LEN] + "\n…(已截断)"
        session_obj.ai_response = f"[智能体调用失败]\n{detail}"
        session_obj.save()
        conversation.save()
        if not got_end:
            yield sse_bytes({"type": "error", "message": str(err)})
        else:
            log_exception_event(logger, f"{log_prefix}_error_after_stream", error=str(err))
        yield sse_bytes({"type": "done"})
        if trace_event:
            trace_event("done", status="agent_error", tokens_received=tokens_received)
        return

    stored = str(payload).strip()
    session_obj.ai_response = stored
    session_obj.save()
    conversation.save()

    if not tokens_received and stored:
        for i in range(0, len(stored), _FALLBACK_DELTA_CHARS):
            yield sse_bytes({"type": "delta", "text": stored[i : i + _FALLBACK_DELTA_CHARS]})
        if got_end and not stream_done_sent:
            yield sse_bytes({"type": "stream_done"})
            if trace_event:
                trace_event("stream_done", tokens_received=tokens_received)

    yield sse_bytes({"type": "done"})
    if trace_event:
        trace_event("done", status="ok", tokens_received=tokens_received)


def sse_streaming_response(gen: Iterator[bytes]) -> StreamingHttpResponse:
    resp = StreamingHttpResponse(gen, content_type="text/event-stream; charset=utf-8")
    resp["Cache-Control"] = "no-cache, no-transform"
    resp["X-Accel-Buffering"] = "no"
    return resp
