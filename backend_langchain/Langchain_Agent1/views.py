from __future__ import annotations

import logging
import queue
import threading
import traceback
from typing import Any, Dict, Iterator, List

from common.SSE import (
    _TOKEN_STREAM_END,
    _sse_bytes,
    _user_visible_reply,
)
from common.agent import chat_interview, interview_checkpoint_thread_id
from common.Queue import run_interview_chat_stream_with_queue
from common.extend import (
    fallback_chat_title,
    polish_interview_title,
    schedule_async_title_polish,
)
from common_web.response_web import HttpResult
from common_web.utils import format_datetime
from django.db import close_old_connections
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from backend_langchain.logger_func import (
    log_error_event,
    log_exception_event,
    log_warning_event,
)
from User.models import InterviewConversation, InterviewSession
from User.utils.user_utils import get_current_user
logger = logging.getLogger(__name__)

_MAX_ERROR_DETAIL_LEN = 8000


@method_decorator(csrf_exempt, name="dispatch")
class InterviewChatView(APIView):
    """
    - GET /api/interview/chat/               -> 面试会话列表
    - GET /api/interview/chat/?conversation_id= -> 历史消息
    - POST /api/interview/chat/              -> 非流式
    """

    def get(self, request):
        user = get_current_user(request)
        if not user:
            return HttpResult.fail("认证失败，请重新登录")

        conversation_id = request.query_params.get("conversation_id")

        if conversation_id:
            conv = InterviewConversation.objects.filter(user=user, id=conversation_id).first()
            if not conv:
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
                messages = [
                    {
                        "id": s.id,
                        "question": s.question,
                        "ai_response": s.ai_response,
                        "created_at": format_datetime(s.created_at),
                    }
                ]
                return HttpResult.success_with_data("获取会话消息成功", {"messages": messages})
            sessions = (
                InterviewSession.objects.filter(user=user, conversation_id=conversation_id)
                .order_by("created_at")
                .only("id", "question", "ai_response", "created_at")
            )
            messages = [
                {
                    "id": s.id,
                    "question": s.question,
                    "ai_response": s.ai_response,
                    "created_at": format_datetime(s.created_at),
                }
                for s in sessions
            ]
            return HttpResult.success_with_data("获取会话消息成功", {"messages": messages})

        conversations = (
            InterviewConversation.objects.filter(user=user)
            .order_by("-pinned", "pinned_at", "-updated_at")
            .all()
        )
        data: List[Dict[str, Any]] = []
        for c in conversations:
            data.append(
                {
                    "id": c.id,
                    "title": c.title,
                    "pinned": bool(c.pinned),
                    "created_at": format_datetime(c.created_at),
                    "updated_at": format_datetime(c.updated_at),
                }
            )
        return HttpResult.success_with_data("获取会话列表成功", {"conversations": data})

    def post(self, request):
        user = get_current_user(request)
        if not user:
            return HttpResult.fail("认证失败，请重新登录")

        try:
            data = request.data
            message = (data.get("message") or "").strip()
            if not message:
                return HttpResult.fail("消息不能为空")

            conversation_id = data.get("conversation_id")

            conversation = None
            if conversation_id:
                conversation = (
                    InterviewConversation.objects.filter(
                        id=conversation_id,
                        user=user,
                    ).first()
                )

            if not conversation:
                title = fallback_chat_title(message)
                conversation = InterviewConversation.objects.create(
                    user=user,
                    title=title,
                )
                schedule_async_title_polish(
                    conversation_id=conversation.id,
                    user_id=user.pk,
                    user_message=message,
                    polish_fn=polish_interview_title,
                    model=InterviewConversation,
                    thread_name_prefix="polish-interview-title",
                    log_context="interview chat",
                )

            thread_id = interview_checkpoint_thread_id(user.pk, conversation.id)

            session_obj = InterviewSession.objects.create(
                user=user,
                conversation=conversation,
                question=message,
                ai_response="",
            )
            try:
                reply = chat_interview(message, thread_id=thread_id)
            except Exception as e:  # noqa: BLE001
                tb = traceback.format_exc()
                detail = f"{str(e)}\n\n--- traceback ---\n{tb}"
                if len(detail) > _MAX_ERROR_DETAIL_LEN:
                    detail = detail[: _MAX_ERROR_DETAIL_LEN] + "\n…(已截断)"
                session_obj.ai_response = f"[智能体调用失败]\n{detail}"
                session_obj.save()
                conversation.save()
                return HttpResult.fail(f"调用智能体失败：{str(e)}")

            visible = _user_visible_reply(str(reply))
            session_obj.ai_response = visible
            session_obj.save()
            conversation.save()

            resp_data = {
                "reply": visible,
                "conversation_id": conversation.id,
            }
            return HttpResult.success_with_data("对话成功", resp_data)

        except Exception as e:  # noqa: BLE001
            return HttpResult.fail(f"对话失败：{str(e)}")


@method_decorator(csrf_exempt, name="dispatch")
class InterviewChatStreamView(APIView):
    """POST /api/interview/chat/stream/"""

    _FALLBACK_DELTA_CHARS = 16
    _PING_INTERVAL_SEC = 2.0
    _WORKER_JOIN_TIMEOUT_SEC = 120.0
    _WORKER_JOIN_AFTER_CANCEL_SEC = 30.0

    def post(self, request):
        user = get_current_user(request)
        if not user:
            return JsonResponse({"success": False, "msg": "认证失败，请重新登录"}, status=401)

        data = request.data if isinstance(request.data, dict) else {}
        resume_raw = data.get("resume_pdf_export")
        if resume_raw is None:
            resume_pdf: bool | None = None
        elif isinstance(resume_raw, bool):
            resume_pdf = resume_raw
        else:
            resume_pdf = str(resume_raw).lower() in ("1", "true", "yes")

        msg_text = (data.get("message") or "").strip()
        conversation_id = data.get("conversation_id")

        if resume_pdf is not None:
            if conversation_id is None:
                return JsonResponse(
                    {"success": False, "msg": "恢复 PDF 确认需要 conversation_id"}, status=400
                )
            conversation = InterviewConversation.objects.filter(id=conversation_id, user=user).first()
            if not conversation:
                return JsonResponse({"success": False, "msg": "会话不存在"}, status=404)
            if not msg_text:
                msg_text = "[PDF导出确认]"
        else:
            if not msg_text:
                return JsonResponse({"success": False, "msg": "消息不能为空"}, status=400)
            conversation = None
            if conversation_id is not None:
                conversation = InterviewConversation.objects.filter(id=conversation_id, user=user).first()

            if not conversation:
                title = fallback_chat_title(msg_text)
                conversation = InterviewConversation.objects.create(user=user, title=title)
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

        def gen() -> Iterator[bytes]:
            result_q: queue.Queue = queue.Queue(maxsize=1)
            token_q: queue.Queue = queue.Queue()
            worker_cancel_evt = threading.Event()

            def run_agent() -> None:
                close_old_connections()
                try:
                    reply = run_interview_chat_stream_with_queue(
                        msg_text,
                        token_q,
                        thread_id=thread_id,
                        resume_pdf=resume_pdf,
                        cancel_event=worker_cancel_evt,
                    )
                    result_q.put(("ok", reply))
                except Exception as e:  # noqa: BLE001
                    result_q.put(("err", (e, traceback.format_exc())))
                finally:
                    token_q.put(_TOKEN_STREAM_END)
                    close_old_connections()

            yield _sse_bytes(
                {
                    "type": "meta",
                    "conversation_id": conversation.id,
                    "session_id": session_obj.id,
                }
            )

            worker = threading.Thread(target=run_agent, daemon=True)
            worker.start()

            tokens_received = 0
            got_token_end = False
            interrupt_sent = False
            pdf_ready_sent = False
            while True:
                try:
                    item = token_q.get(timeout=self._PING_INTERVAL_SEC)
                except queue.Empty:
                    if worker.is_alive():
                        yield _sse_bytes({"type": "ping"})
                    else:
                        break
                    continue
                if item is _TOKEN_STREAM_END:
                    got_token_end = True
                    break
                if isinstance(item, dict):
                    t = item.get("type")
                    if t == "status" and item.get("text") is not None:
                        yield _sse_bytes({"type": "status", "text": item["text"]})
                    elif t == "delta" and item.get("text") is not None:
                        tokens_received += 1
                        yield _sse_bytes({"type": "delta", "text": item["text"]})
                    elif t == "interrupt" and item.get("kind") is not None:
                        interrupt_sent = True
                        yield _sse_bytes(
                            {
                                "type": "interrupt",
                                "kind": item["kind"],
                                "message": item.get("message") or "",
                            }
                        )
                    elif t == "pdf_ready" and item.get("url"):
                        pdf_ready_sent = True
                        yield _sse_bytes(
                            {
                                "type": "pdf_ready",
                                "url": item["url"],
                                "filename": item.get("filename") or "export.pdf",
                            }
                        )

            # Worker 在发送 token END 之前已将 ok/err 写入 result_q；可先 peek，不必等 join。
            peek_kind = None
            peek_payload = None
            if got_token_end:
                try:
                    peek_kind, peek_payload = result_q.get_nowait()
                except queue.Empty:
                    pass

            stream_done_sent = False
            if got_token_end and (tokens_received or interrupt_sent or pdf_ready_sent):
                yield _sse_bytes({"type": "stream_done"})
                stream_done_sent = True

            worker.join(timeout=self._WORKER_JOIN_TIMEOUT_SEC)
            if worker.is_alive():
                worker_cancel_evt.set()
                log_warning_event(
                    logger,
                    "interview_chat_stream_worker_join_timeout",
                    hint="cancel_event set for cooperative shutdown",
                    tokens_received=tokens_received,
                )
                worker.join(timeout=self._WORKER_JOIN_AFTER_CANCEL_SEC)
                if worker.is_alive():
                    log_error_event(
                        logger,
                        "interview_chat_stream_worker_still_alive_after_cancel",
                        tokens_received=tokens_received,
                    )

            kind = peek_kind
            payload = peek_payload
            if kind is None:
                try:
                    kind, payload = result_q.get_nowait()
                except queue.Empty:
                    session_obj.ai_response = "[智能体调用失败]\n未收到执行结果"
                    session_obj.save()
                    conversation.save()
                    if not got_token_end:
                        yield _sse_bytes({"type": "error", "message": "智能体未返回结果"})
                    elif tokens_received:
                        log_warning_event(
                            logger,
                            "interview_chat_stream_result_queue_empty_with_deltas",
                            hint="check worker timeout or thread errors",
                            tokens_received=tokens_received,
                        )
                    else:
                        log_error_event(logger, "interview_chat_stream_result_queue_empty_after_join")
                    yield _sse_bytes({"type": "done"})
                    return

            if kind == "err":
                err, tb = payload
                detail = f"{str(err)}\n\n--- traceback ---\n{tb}"
                if len(detail) > _MAX_ERROR_DETAIL_LEN:
                    detail = detail[: _MAX_ERROR_DETAIL_LEN] + "\n…(已截断)"
                session_obj.ai_response = f"[智能体调用失败]\n{detail}"
                session_obj.save()
                conversation.save()
                if not got_token_end:
                    yield _sse_bytes({"type": "error", "message": str(err)})
                else:
                    log_exception_event(
                        logger,
                        "interview_chat_stream_agent_invoke_failed_after_stream_end",
                        error=str(err),
                    )
                yield _sse_bytes({"type": "done"})
                return

            reply = str(payload)
            stored = _user_visible_reply(reply)
            session_obj.ai_response = stored
            session_obj.save()
            conversation.save()

            if not tokens_received and stored:
                for i in range(0, len(stored), self._FALLBACK_DELTA_CHARS):
                    chunk = stored[i : i + self._FALLBACK_DELTA_CHARS]
                    yield _sse_bytes({"type": "delta", "text": chunk})
                if got_token_end and not stream_done_sent:
                    yield _sse_bytes({"type": "stream_done"})

            yield _sse_bytes({"type": "done"})

        resp = StreamingHttpResponse(gen(), content_type="text/event-stream; charset=utf-8")
        resp["Cache-Control"] = "no-cache, no-transform"
        resp["X-Accel-Buffering"] = "no"
        return resp


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
            is_pinned = bool(data.get("pinned"))
            conv.pinned = is_pinned
            if is_pinned:
                if conv.pinned_at is None:
                    conv.pinned_at = timezone.now()
            else:
                conv.pinned_at = None

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
