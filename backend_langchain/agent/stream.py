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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.memory.memory_persist import MemoryTurnContext
from app.models import AgentWebSource
from app.utils import format_datetime, utc_now_naive
from backend_langchain.logger_func import log_exception_event
from agent.graph_factory import message_content_to_text
from app.services.extend import quick_agent_greeting_prompt, quick_interview_greeting_prompt
from config.config import get_qwen_chat_model

logger = logging.getLogger(__name__)

AgentKind = Literal["main", "interview"]
_MAX_ERR_LEN = 8000
_INTERRUPT_HINT = "（请在界面点击按钮确认或取消 PDF 导出。）"

_QUICK = {"main": quick_agent_greeting_prompt, "interview": quick_interview_greeting_prompt}

SESSION_STATUS_GENERATING = "generating"
SESSION_STATUS_COMPLETED = "completed"
SESSION_STATUS_FAILED = "failed"


def _stream_fn(kind: AgentKind):
    from agent.runtime.runtime_interview import stream_interview_agent
    from agent.runtime.runtime_knowledge import stream_agent

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


def _extract_web_sources(events: list[dict]) -> list[dict[str, str]]:
    """取本轮最后一次 web_sources（强制搜通常只发一次）。"""
    for evt in reversed(events):
        if evt.get("type") != "web_sources":
            continue
        raw = evt.get("sources")
        if not isinstance(raw, list):
            continue
        out: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            title = str(item.get("title") or "").strip() or url
            out.append({"title": title, "url": url})
        return out
    return []


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
    enable_web_search: bool = False,
    attachments: list[dict] | None = None,
    memory: MemoryTurnContext | None = None,
) -> AsyncIterator[dict]:
    """统一事件流：delta / status / interrupt / pdf_ready（生成阶段不写库）。"""
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


def session_message_rows(
    sessions: list[Any],
    *,
    sources_by_session: dict[int, list[dict[str, str]]] | None = None,
) -> list[dict[str, Any]]:
    src_map = sources_by_session or {}
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
        sources = src_map.get(int(s.id))
        if sources:
            row["web_sources"] = sources
        rows.append(row)
    return rows


async def load_web_sources_by_session_ids(
    db: AsyncSession, session_ids: list[int]
) -> dict[int, list[dict[str, str]]]:
    if not session_ids:
        return {}
    result = await db.execute(
        select(AgentWebSource).where(AgentWebSource.session_id.in_(session_ids))
    )
    out: dict[int, list[dict[str, str]]] = {}
    for row in result.scalars():
        raw = row.sources_json
        if isinstance(raw, list):
            out[int(row.session_id)] = [
                {"title": str(x.get("title") or ""), "url": str(x.get("url") or "")}
                for x in raw
                if isinstance(x, dict) and str(x.get("url") or "").strip()
            ]
    return out


def _to_sse(evt: dict) -> bytes | None:
    t = evt.get("type")
    if t == "status" and evt.get("text") is not None:
        return sse_bytes({"type": "status", "text": evt["text"]})
    if t == "web_sources" and isinstance(evt.get("sources"), list):
        return sse_bytes({"type": "web_sources", "sources": evt["sources"]})
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
    kind: AgentKind,
    session_obj: Any,
    conversation: Any | None,
    content: str,
    status: str,
    sources: list[dict[str, str]],
) -> None:
    """一次事务：content + token + status +（可选）sources。"""
    session_obj.ai_response = content
    if hasattr(session_obj, "status"):
        session_obj.status = status
    if hasattr(session_obj, "token_estimate"):
        session_obj.token_estimate = _token_estimate(content)
    if conversation is not None:
        conversation.updated_at = utc_now_naive()

    if kind == "main" and sources:
        existing = await db.execute(
            select(AgentWebSource).where(AgentWebSource.session_id == int(session_obj.id))
        )
        row = existing.scalar_one_or_none()
        if row is None:
            db.add(
                AgentWebSource(
                    session_id=int(session_obj.id),
                    conversation_id=getattr(session_obj, "conversation_id", None),
                    user_id=int(session_obj.user_id),
                    sources_json=sources,
                )
            )
        else:
            row.sources_json = sources

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
    enable_web_search: bool = False,
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
            enable_web_search=enable_web_search,
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
                kind=kind,
                session_obj=session_obj,
                conversation=conversation,
                content=f"[智能体调用失败]\n{detail}",
                status=SESSION_STATUS_FAILED,
                sources=[],
            )
        except Exception:  # noqa: BLE001
            log_exception_event(logger, f"{log_prefix}_finalize_failed", error=str(err))
            await db.rollback()
        yield sse_bytes({"type": "error", "message": str(err)})
        yield sse_bytes({"type": "done"})
        log_exception_event(logger, f"{log_prefix}_error", error=str(err))
        return

    reply = _reply(events).strip()
    sources = _extract_web_sources(events) if kind == "main" else []
    try:
        await _finalize_session_txn(
            db,
            kind=kind,
            session_obj=session_obj,
            conversation=conversation,
            content=reply,
            status=SESSION_STATUS_COMPLETED,
            sources=sources,
        )
    except Exception as e:  # noqa: BLE001
        log_exception_event(logger, f"{log_prefix}_finalize_failed", error=str(e))
        await db.rollback()
        yield sse_bytes({"type": "error", "message": f"落库失败: {e}"})
        yield sse_bytes({"type": "done"})
        return

    yield sse_bytes({"type": "done"})


def sse_response(gen: AsyncIterator[bytes]) -> StreamingResponse:
    return StreamingResponse(
        gen,
        media_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
