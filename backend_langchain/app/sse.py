"""流式：事件编排 → SSE → 内存聚合 → 一次事务落库 → done。"""
from __future__ import annotations

import json
import logging
import time
import traceback
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.memory.memory_persist import MemoryTurnContext
from app.utils import format_datetime, utc_now_naive
from backend_langchain.logger_func import log_exception_event
from runtime.execution.graph_factory import message_content_to_text
from app.services.extend import quick_interview_greeting_prompt
from config.config import get_qwen_chat_model

logger = logging.getLogger(__name__)

AgentKind = Literal["interview"]
_MAX_ERR_LEN = 8000
_INTERRUPT_HINT = "（请在界面点击按钮确认或取消 PDF 导出。）"

_QUICK = {"interview": quick_interview_greeting_prompt}

SESSION_STATUS_GENERATING = "generating"
SESSION_STATUS_COMPLETED = "completed"
SESSION_STATUS_FAILED = "failed"


def _stream_fn() -> Any:
    from products.interview.runtime import stream_interview_agent

    return stream_interview_agent


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


def _token_estimate(text: str) -> int:
    """粗估 token（中英混合近似按字符计），仅作落库统计。"""
    return max(0, len(text or ""))


async def stream_chat_events(
    kind: AgentKind,
    user_input: str,
    *,
    thread_id: str,
    temperature: float = 0.45,
    resume_pdf: bool | None = None,
    attachments: list[dict] | None = None,
    memory: MemoryTurnContext | None = None,
) -> AsyncIterator[dict]:
    """统一事件流：delta / status / interrupt / pdf_ready（生成阶段不写库）。"""
    fn = _stream_fn()

    if resume_pdf is not None:
        async for evt in fn(
            thread_id=thread_id,
            temperature=temperature,
            resume_pdf=resume_pdf,
        ):
            yield evt
        return

    if not (user_input or "").strip():
        raise ValueError("user_input is empty")

    if not attachments and (quick := _QUICK[kind](user_input)):
        llm = get_qwen_chat_model(temperature=temperature, streaming=True)
        async for chunk in llm.astream([HumanMessage(content=quick)]):
            if text := message_content_to_text(getattr(chunk, "content", chunk)):
                yield {"type": "delta", "text": text}
        return

    for attempt in range(2):
        tid = thread_id if attempt == 0 else f"{thread_id}:recover:{int(time.time() * 1000)}"
        try:
            async for evt in fn(
                prompt_text=user_input.strip(),
                thread_id=tid,
                temperature=temperature,
                memory=memory,
                attachments=attachments,
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


def session_message_rows(sessions: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for s in sessions:
        row: dict[str, Any] = {
            "id": s.id,
            "question": s.question,
            "ai_response": s.ai_response,
            "status": getattr(s, "status", None) or SESSION_STATUS_COMPLETED,
            "token_estimate": getattr(s, "token_estimate", None),
            "created_at": format_datetime(s.created_at),
        }
        rows.append(row)
    return rows


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


async def _finalize_session_txn(
    db: AsyncSession,
    *,
    session_obj: Any,
    conversation: Any | None,
    content: str,
    status: str,
) -> None:
    """一次事务：content + token + status。"""
    session_obj.ai_response = content
    if hasattr(session_obj, "status"):
        session_obj.status = status
    if hasattr(session_obj, "token_estimate"):
        session_obj.token_estimate = _token_estimate(content)
    if conversation is not None:
        conversation.updated_at = utc_now_naive()

    await db.commit()


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
    attachments: list[dict] | None = None,
) -> AsyncIterator[bytes]:
    yield sse_bytes({"type": "meta", "conversation_id": conversation_id, "session_id": session_id})

    memory = MemoryTurnContext(
        user_id=int(session_obj.user_id),
        conversation_id=conversation_id,
        kind=kind,
    )

    events: list[dict] = []
    err: BaseException | None = None

    try:
        async for item in stream_chat_events(
            kind,
            user_input,
            thread_id=thread_id,
            resume_pdf=resume_pdf,
            attachments=attachments,
            memory=memory,
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
        try:
            await _finalize_session_txn(
                db,
                session_obj=session_obj,
                conversation=conversation,
                content=f"[智能体调用失败]\n{detail}",
                status=SESSION_STATUS_FAILED,
            )
        except Exception:  # noqa: BLE001
            log_exception_event(logger, f"{log_prefix}_finalize_failed", error=str(err))
            await db.rollback()
        yield sse_bytes({"type": "error", "message": str(err)})
        yield sse_bytes({"type": "done"})
        log_exception_event(logger, f"{log_prefix}_error", error=str(err))
        return

    reply = _reply(events).strip()
    try:
        await _finalize_session_txn(
            db,
            session_obj=session_obj,
            conversation=conversation,
            content=reply,
            status=SESSION_STATUS_COMPLETED,
        )
    except Exception as e:  # noqa: BLE001
        log_exception_event(logger, f"{log_prefix}_finalize_failed", error=str(e))
        await db.rollback()
        yield sse_bytes({"type": "error", "message": f"落库失败: {e}"})
        yield sse_bytes({"type": "done"})
        return

    try:
        from infrastructure.memory.long_term_agent import schedule_long_term_memory

        schedule_long_term_memory(
            user_id=int(session_obj.user_id),
            user_text=user_input,
            assistant_text=reply,
        )
    except Exception:  # noqa: BLE001
        log_exception_event(logger, f"{log_prefix}_memory_schedule_failed")

    yield sse_bytes({"type": "done"})


def sse_response(gen: AsyncIterator[bytes]) -> StreamingResponse:
    return StreamingResponse(
        gen,
        media_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
