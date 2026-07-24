"""企业知识库AI助手 API：/api/agent/*"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_user
from app.models import AgentWebSource, ConversationSummary, User, UserConversation, UserSession
from app.response import fail, ok
from app.utils import format_datetime, utc_now_naive
from backend_langchain.logger_func import make_trace_event_logger
from agent.graph_factory import agent_checkpoint_thread_id
from app.services.extend import (
    fallback_chat_title,
    polish_agent_conversation_title,
    schedule_async_title_polish,
)
from agent.stream import (
    SESSION_STATUS_GENERATING,
    iter_sse_chat,
    load_web_sources_by_session_ids,
    parse_bool_flag,
    parse_resume_pdf,
    session_message_rows,
    sse_response,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])


class StreamBody(BaseModel):
    message: str = ""
    conversation_id: int | None = None
    resume_pdf_export: bool | None = None
    enable_web_search: bool | None = None
    attachments: list[dict] = Field(default_factory=list)


class ConversationPatchBody(BaseModel):
    conversation_id: int | None = None
    title: str | None = None
    pinned: bool | None = None


class ConversationDeleteBody(BaseModel):
    conversation_id: int | None = None


@router.get("/api/agent/chat/")
async def list_or_messages(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    conversation_id: int | None = Query(None),
    session_id: int | None = Query(None),
):
    if conversation_id is not None:
        if session_id is not None:
            result = await db.execute(
                select(UserSession).where(
                    UserSession.user_id == user.user_id,
                    UserSession.conversation_id == conversation_id,
                    UserSession.id == session_id,
                )
            )
            s = result.scalar_one_or_none()
            if not s:
                return fail("消息不存在")
            sources = await load_web_sources_by_session_ids(db, [int(s.id)])
            return ok(
                "获取会话消息成功",
                {"messages": session_message_rows([s], sources_by_session=sources)},
            )
        result = await db.execute(
            select(UserSession)
            .where(
                UserSession.user_id == user.user_id,
                UserSession.conversation_id == conversation_id,
            )
            .order_by(UserSession.created_at)
        )
        sessions = list(result.scalars())
        sources = await load_web_sources_by_session_ids(db, [int(s.id) for s in sessions])
        return ok(
            "获取会话消息成功",
            {"messages": session_message_rows(sessions, sources_by_session=sources)},
        )

    result = await db.execute(
        select(UserConversation)
        .where(UserConversation.user_id == user.user_id)
        .order_by(
            UserConversation.pinned.desc(),
            UserConversation.pinned_at.asc(),
            UserConversation.updated_at.desc(),
        )
    )
    data = [
        {
            "id": c.id,
            "title": c.title,
            "pinned": bool(c.pinned),
            "created_at": format_datetime(c.created_at),
            "updated_at": format_datetime(c.updated_at),
        }
        for c in result.scalars()
    ]
    return ok("获取会话列表成功", {"conversations": data})


@router.post("/api/agent/chat/stream/")
async def chat_stream(
    body: StreamBody,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    trace_event = make_trace_event_logger(
        logger, log_key="chat_stream_trace", trace_prefix="stream"
    )
    resume_pdf = parse_resume_pdf(body.resume_pdf_export)
    msg_text = (body.message or "").strip()
    enable_web_search = parse_bool_flag(body.enable_web_search, default=False)

    if resume_pdf is not None:
        if body.conversation_id is None:
            return fail("恢复 PDF 确认需要 conversation_id", status_code=400)
        result = await db.execute(
            select(UserConversation).where(
                UserConversation.id == body.conversation_id,
                UserConversation.user_id == user.user_id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            return fail("会话不存在", status_code=404)
        if not msg_text:
            msg_text = "[PDF导出确认]"
    else:
        if not msg_text:
            return fail("消息不能为空", status_code=400)
        conversation = None
        if body.conversation_id is not None:
            result = await db.execute(
                select(UserConversation).where(
                    UserConversation.id == body.conversation_id,
                    UserConversation.user_id == user.user_id,
                )
            )
            conversation = result.scalar_one_or_none()
        if not conversation:
            conversation = UserConversation(
                user_id=user.user_id, title=fallback_chat_title(msg_text)
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)
            schedule_async_title_polish(
                conversation_id=conversation.id,
                user_id=user.user_id,
                user_message=msg_text,
                polish_fn=polish_agent_conversation_title,
                table=UserConversation,
                log_context="agent chat stream",
            )

    thread_id = agent_checkpoint_thread_id(user.user_id, conversation.id)
    session_obj = UserSession(
        user_id=user.user_id,
        conversation_id=conversation.id,
        question=msg_text,
        ai_response="",
        status=SESSION_STATUS_GENERATING,
    )
    db.add(session_obj)
    await db.commit()
    await db.refresh(session_obj)

    trace_event(
        "request_enter",
        user_id=user.user_id,
        msg_len=len(msg_text),
        resume_pdf=resume_pdf,
        enable_web_search=enable_web_search,
    )

    return sse_response(
        iter_sse_chat(
            db=db,
            kind="main",
            user_input=msg_text,
            thread_id=thread_id,
            conversation_id=conversation.id,
            session_id=session_obj.id,
            session_obj=session_obj,
            conversation=conversation,
            log_prefix="chat_stream",
            resume_pdf=resume_pdf,
            enable_web_search=enable_web_search,
            attachments=body.attachments,
        )
    )


@router.patch("/api/agent/conversation/")
async def patch_conversation(
    body: ConversationPatchBody,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if body.conversation_id is None:
        return fail("缺少 conversation_id")
    result = await db.execute(
        select(UserConversation).where(
            UserConversation.id == body.conversation_id,
            UserConversation.user_id == user.user_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return fail("会话不存在")

    if body.title is not None:
        title = (body.title or "").strip()
        if not title:
            return fail("标题不能为空")
        conv.title = title[:255]

    if body.pinned is not None:
        conv.pinned = bool(body.pinned)
        conv.pinned_at = utc_now_naive() if conv.pinned else None

    if body.title is None and body.pinned is None:
        return fail("请提供 title 或 pinned")

    await db.commit()
    await db.refresh(conv)
    return ok(
        "更新成功",
        {
            "id": conv.id,
            "title": conv.title,
            "pinned": bool(conv.pinned),
            "updated_at": format_datetime(conv.updated_at),
        },
    )


@router.delete("/api/agent/conversation/")
async def delete_conversation(
    body: ConversationDeleteBody,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    conversation_id: int | None = Query(None),
):
    cid = body.conversation_id or conversation_id
    if cid is None:
        return fail("缺少 conversation_id")
    result = await db.execute(
        select(UserConversation).where(
            UserConversation.id == cid,
            UserConversation.user_id == user.user_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return fail("会话不存在")
    # 先删子表，再删对话（无 ON DELETE CASCADE）
    session_ids = select(UserSession.id).where(UserSession.conversation_id == cid)
    await db.execute(
        delete(AgentWebSource).where(
            or_(
                AgentWebSource.conversation_id == cid,
                AgentWebSource.session_id.in_(session_ids),
            )
        )
    )
    await db.execute(
        delete(ConversationSummary).where(
            ConversationSummary.kind == "main",
            ConversationSummary.conversation_id == cid,
        )
    )
    await db.execute(delete(UserSession).where(UserSession.conversation_id == cid))
    await db.delete(conv)
    await db.commit()
    return ok("删除成功")
