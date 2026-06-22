from __future__ import annotations

import logging
from typing import Any

from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from User.models import (
    InterviewConversation,
    InterviewSession,
    UserConversation,
    UserSession,
)
from User.utils.user_utils import get_current_user
from backend_langchain.logger_func import make_trace_event_logger
from common.Queue import run_chat_stream_with_queue, run_interview_chat_stream_with_queue
from common.agent import agent_checkpoint_thread_id, interview_checkpoint_thread_id
from common.extend import (
    fallback_chat_title,
    polish_agent_conversation_title,
    polish_interview_title,
    schedule_async_title_polish,
)
from common.stream_http import (
    iter_sse_chat,
    parse_resume_pdf,
    session_message_rows,
    sse_streaming_response,
)
from common_web.response_web import HttpResult
from common_web.utils import format_datetime

logger = logging.getLogger(__name__)


def _parse_bool_flag(raw: Any, *, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


@method_decorator(csrf_exempt, name="dispatch")
class ChatView(APIView):
    """GET /api/agent/chat/ — 会话列表或历史消息。"""

    def get(self, request):
        user = get_current_user(request)
        if not user:
            return HttpResult.fail("认证失败，请重新登录")

        conversation_id = request.query_params.get("conversation_id")
        if conversation_id:
            session_id = request.query_params.get("session_id")
            if session_id:
                try:
                    sid = int(session_id)
                except ValueError:
                    return HttpResult.fail("session_id 无效")
                s = (
                    UserSession.objects.filter(
                        user=user, conversation_id=conversation_id, id=sid
                    )
                    .only("id", "question", "ai_response", "created_at")
                    .first()
                )
                if not s:
                    return HttpResult.fail("消息不存在")
                return HttpResult.success_with_data(
                    "获取会话消息成功", {"messages": session_message_rows([s])}
                )
            qs = UserSession.objects.filter(
                user=user, conversation_id=conversation_id
            ).order_by("created_at").only("id", "question", "ai_response", "created_at")
            return HttpResult.success_with_data(
                "获取会话消息成功", {"messages": session_message_rows(qs)}
            )

        conversations = UserConversation.objects.filter(user=user).order_by(
            "-pinned", "pinned_at", "-updated_at"
        )
        data = [
            {
                "id": c.id,
                "title": c.title,
                "pinned": bool(c.pinned),
                "created_at": format_datetime(c.created_at),
                "updated_at": format_datetime(c.updated_at),
            }
            for c in conversations
        ]
        return HttpResult.success_with_data("获取会话列表成功", {"conversations": data})


@method_decorator(csrf_exempt, name="dispatch")
class ChatStreamView(APIView):
    """POST /api/agent/chat/stream/ — SSE 流式对话。"""

    def post(self, request):
        trace_event = make_trace_event_logger(
            logger, log_key="chat_stream_trace", trace_prefix="stream"
        )
        user = get_current_user(request)
        if not user:
            return JsonResponse({"success": False, "msg": "认证失败，请重新登录"}, status=401)

        data = request.data if isinstance(request.data, dict) else {}
        resume_pdf = parse_resume_pdf(data.get("resume_pdf_export"))
        msg_text = (data.get("message") or "").strip()
        conversation_id = data.get("conversation_id")
        enable_web_search = _parse_bool_flag(data.get("enable_web_search"), default=False)

        if resume_pdf is not None:
            if conversation_id is None:
                return JsonResponse(
                    {"success": False, "msg": "恢复 PDF 确认需要 conversation_id"}, status=400
                )
            conversation = UserConversation.objects.filter(
                id=conversation_id, user=user
            ).first()
            if not conversation:
                return JsonResponse({"success": False, "msg": "会话不存在"}, status=404)
            if not msg_text:
                msg_text = "[PDF导出确认]"
        else:
            if not msg_text:
                return JsonResponse({"success": False, "msg": "消息不能为空"}, status=400)
            conversation = None
            if conversation_id is not None:
                conversation = UserConversation.objects.filter(
                    id=conversation_id, user=user
                ).first()
            if not conversation:
                conversation = UserConversation.objects.create(
                    user=user, title=fallback_chat_title(msg_text)
                )
                schedule_async_title_polish(
                    conversation_id=conversation.id,
                    user_id=user.pk,
                    user_message=msg_text,
                    polish_fn=polish_agent_conversation_title,
                    model=UserConversation,
                    thread_name_prefix="polish-title",
                    log_context="agent chat stream",
                )

        thread_id = agent_checkpoint_thread_id(user.pk, conversation.id)
        session_obj = UserSession.objects.create(
            user=user,
            conversation=conversation,
            question=msg_text,
            ai_response="",
        )
        trace_event(
            "request_enter",
            user_id=user.pk,
            msg_len=len(msg_text),
            resume_pdf=resume_pdf,
            enable_web_search=enable_web_search,
        )

        def run_stream(token_q, cancel_evt):
            return run_chat_stream_with_queue(
                msg_text,
                token_q,
                thread_id=thread_id,
                trace_cb=trace_event,
                resume_pdf=resume_pdf,
                enable_web_search=enable_web_search,
                cancel_event=cancel_evt,
            )

        return sse_streaming_response(
            iter_sse_chat(
                conversation_id=conversation.id,
                session_id=session_obj.id,
                run_stream=run_stream,
                session_obj=session_obj,
                conversation=conversation,
                log_prefix="chat_stream",
                trace_event=trace_event,
            )
        )


@method_decorator(csrf_exempt, name="dispatch")
class ConversationManageView(APIView):
    """PATCH/DELETE /api/agent/conversation/"""

    def patch(self, request):
        user = get_current_user(request)
        if not user:
            return HttpResult.fail("认证失败，请重新登录")
        data = request.data or {}
        cid = data.get("conversation_id")
        if cid is None:
            return HttpResult.fail("缺少 conversation_id")
        conv = UserConversation.objects.filter(id=cid, user=user).first()
        if not conv:
            return HttpResult.fail("会话不存在")

        if "title" in data:
            title = (data.get("title") or "").strip()
            if not title:
                return HttpResult.fail("标题不能为空")
            conv.title = title[:255]

        if "pinned" in data:
            conv.pinned = bool(data.get("pinned"))
            conv.pinned_at = timezone.now() if conv.pinned else None

        if "title" not in data and "pinned" not in data:
            return HttpResult.fail("请提供 title 或 pinned")

        conv.save()
        return HttpResult.success_with_data(
            "更新成功",
            {
                "id": conv.id,
                "title": conv.title,
                "pinned": bool(conv.pinned),
                "updated_at": format_datetime(conv.updated_at),
            },
        )

    def delete(self, request):
        user = get_current_user(request)
        if not user:
            return HttpResult.fail("认证失败，请重新登录")
        data = request.data if isinstance(request.data, dict) else {}
        cid = data.get("conversation_id") or request.query_params.get("conversation_id")
        if cid is None:
            return HttpResult.fail("缺少 conversation_id")
        conv = UserConversation.objects.filter(id=cid, user=user).first()
        if not conv:
            return HttpResult.fail("会话不存在")
        conv.delete()
        return HttpResult.success("删除成功")


# --- 面试大师（独立会话表，API 路径不变）---


@method_decorator(csrf_exempt, name="dispatch")
class InterviewChatView(APIView):
    """GET /api/interview/chat/ — 会话列表或历史消息。"""

    def get(self, request):
        user = get_current_user(request)
        if not user:
            return HttpResult.fail("认证失败，请重新登录")

        conversation_id = request.query_params.get("conversation_id")
        if conversation_id:
            if not InterviewConversation.objects.filter(
                user=user, id=conversation_id
            ).exists():
                return HttpResult.fail("会话不存在")
            session_id = request.query_params.get("session_id")
            if session_id:
                try:
                    sid = int(session_id)
                except ValueError:
                    return HttpResult.fail("session_id 无效")
                s = (
                    InterviewSession.objects.filter(
                        user=user, conversation_id=conversation_id, id=sid
                    )
                    .only("id", "question", "ai_response", "created_at")
                    .first()
                )
                if not s:
                    return HttpResult.fail("消息不存在")
                return HttpResult.success_with_data(
                    "获取会话消息成功", {"messages": session_message_rows([s])}
                )
            qs = InterviewSession.objects.filter(
                user=user, conversation_id=conversation_id
            ).order_by("created_at").only("id", "question", "ai_response", "created_at")
            return HttpResult.success_with_data(
                "获取会话消息成功", {"messages": session_message_rows(qs)}
            )

        conversations = InterviewConversation.objects.filter(user=user).order_by(
            "-pinned", "pinned_at", "-updated_at"
        )
        data = [
            {
                "id": c.id,
                "title": c.title,
                "pinned": bool(c.pinned),
                "created_at": format_datetime(c.created_at),
                "updated_at": format_datetime(c.updated_at),
            }
            for c in conversations
        ]
        return HttpResult.success_with_data("获取会话列表成功", {"conversations": data})


@method_decorator(csrf_exempt, name="dispatch")
class InterviewChatStreamView(APIView):
    """POST /api/interview/chat/stream/ — SSE 流式对话。"""

    def post(self, request):
        user = get_current_user(request)
        if not user:
            return JsonResponse({"success": False, "msg": "认证失败，请重新登录"}, status=401)

        data = request.data if isinstance(request.data, dict) else {}
        resume_pdf = parse_resume_pdf(data.get("resume_pdf_export"))
        msg_text = (data.get("message") or "").strip()
        conversation_id = data.get("conversation_id")

        if resume_pdf is not None:
            if conversation_id is None:
                return JsonResponse(
                    {"success": False, "msg": "恢复 PDF 确认需要 conversation_id"}, status=400
                )
            conversation = InterviewConversation.objects.filter(
                id=conversation_id, user=user
            ).first()
            if not conversation:
                return JsonResponse({"success": False, "msg": "会话不存在"}, status=404)
            if not msg_text:
                msg_text = "[PDF导出确认]"
        else:
            if not msg_text:
                return JsonResponse({"success": False, "msg": "消息不能为空"}, status=400)
            conversation = None
            if conversation_id is not None:
                conversation = InterviewConversation.objects.filter(
                    id=conversation_id, user=user
                ).first()
            if not conversation:
                conversation = InterviewConversation.objects.create(
                    user=user, title=fallback_chat_title(msg_text)
                )
                schedule_async_title_polish(
                    conversation_id=conversation.id,
                    user_id=user.pk,
                    user_message=msg_text,
                    polish_fn=polish_interview_title,
                    model=InterviewConversation,
                    thread_name_prefix="polish-interview-title",
                    log_context="interview chat stream",
                )

        thread_id = interview_checkpoint_thread_id(user.pk, conversation.id)
        session_obj = InterviewSession.objects.create(
            user=user,
            conversation=conversation,
            question=msg_text,
            ai_response="",
        )

        def run_stream(token_q, cancel_evt):
            return run_interview_chat_stream_with_queue(
                msg_text,
                token_q,
                thread_id=thread_id,
                resume_pdf=resume_pdf,
                cancel_event=cancel_evt,
            )

        return sse_streaming_response(
            iter_sse_chat(
                conversation_id=conversation.id,
                session_id=session_obj.id,
                run_stream=run_stream,
                session_obj=session_obj,
                conversation=conversation,
                log_prefix="interview_chat_stream",
            )
        )


@method_decorator(csrf_exempt, name="dispatch")
class InterviewConversationManageView(APIView):
    """PATCH/DELETE /api/interview/conversation/"""

    def patch(self, request):
        user = get_current_user(request)
        if not user:
            return HttpResult.fail("认证失败，请重新登录")
        data = request.data or {}
        cid = data.get("conversation_id")
        if cid is None:
            return HttpResult.fail("缺少 conversation_id")
        conv = InterviewConversation.objects.filter(id=cid, user=user).first()
        if not conv:
            return HttpResult.fail("会话不存在")

        if "title" in data:
            title = (data.get("title") or "").strip()
            if not title:
                return HttpResult.fail("标题不能为空")
            conv.title = title[:255]

        if "pinned" in data:
            conv.pinned = bool(data.get("pinned"))
            conv.pinned_at = timezone.now() if conv.pinned else None

        if "title" not in data and "pinned" not in data:
            return HttpResult.fail("请提供 title 或 pinned")

        conv.save()
        return HttpResult.success_with_data(
            "更新成功",
            {
                "id": conv.id,
                "title": conv.title,
                "pinned": bool(conv.pinned),
                "updated_at": format_datetime(conv.updated_at),
            },
        )

    def delete(self, request):
        user = get_current_user(request)
        if not user:
            return HttpResult.fail("认证失败，请重新登录")
        data = request.data if isinstance(request.data, dict) else {}
        cid = data.get("conversation_id") or request.query_params.get("conversation_id")
        if cid is None:
            return HttpResult.fail("缺少 conversation_id")
        conv = InterviewConversation.objects.filter(id=cid, user=user).first()
        if not conv:
            return HttpResult.fail("会话不存在")
        conv.delete()
        return HttpResult.success("删除成功")
