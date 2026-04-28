from __future__ import annotations

import logging
import queue
import threading
import traceback
from typing import List, Dict, Any, Iterator

from common.SSE import (
    _sse_bytes,
    _user_visible_reply,
    _TOKEN_STREAM_END,
    user_visible_reply_inline,
)

from django.db import close_old_connections
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView

from User.models import UserConversation, UserSession
from User.utils.user_utils import get_current_user
from common_web.response_web import HttpResult
from common_web.utils import format_datetime
from django.utils import timezone
from common.agent import agent_checkpoint_thread_id, chat as agent_chat
from common.Queue import run_chat_stream_with_queue
from backend_langchain.logger_func import (
    log_error_event,
    log_exception_event,
    log_warning_event,
    make_trace_event_logger,
)
from common.extend import (
    fallback_chat_title,
    polish_agent_conversation_title,
    schedule_async_title_polish,
)

logger = logging.getLogger(__name__)

# 错误详情存库时截断，避免超长 traceback 撑爆数据库行
_MAX_ERROR_DETAIL_LEN = 8000


def _parse_bool_flag(raw: Any, *, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


@method_decorator(csrf_exempt, name="dispatch")
class ChatView(APIView):
    """
    基于 ReAct + RAG 的对话接口
    - GET /api/agent/chat/               -> 获取当前用户的会话列表
    - GET /api/agent/chat/?conversation_id=xxx -> 获取某个会话的历史消息
    - POST /api/agent/chat/              -> 发起一条新消息，调用智能体并落库
    """

    def get(self, request):
        user = get_current_user(request)
        if not user:
            return HttpResult.fail("认证失败，请重新登录")

        conversation_id = request.query_params.get("conversation_id")

        # 返回指定会话的历史消息；可选 session_id 仅拉一条（流式结束对账，避免长会话全表扫描）
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
                UserSession.objects.filter(user=user, conversation_id=conversation_id)
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

        # 置顶优先，其次按置顶先后（pinned_at 越早越靠前）
        conversations = (
            UserConversation.objects.filter(user=user)
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
        """
        前端调用：POST /api/agent/chat/
        body: { message: string, conversation_id?: number }
        """
        user = get_current_user(request)
        if not user:
            return HttpResult.fail("认证失败，请重新登录")

        try:
            data = request.data
            message = (data.get("message") or "").strip()
            if not message:
                return HttpResult.fail("消息不能为空")
            enable_web_search = _parse_bool_flag(data.get("enable_web_search"), default=False)

            conversation_id = data.get("conversation_id")

            # 如果传了 conversation_id，就在该会话下继续对话；否则新建一个会话
            conversation = None
            if conversation_id:
                conversation = (
                    UserConversation.objects.filter(
                        id=conversation_id,
                        user=user,
                    ).first()
                )

            if not conversation:
                title = fallback_chat_title(message)
                conversation = UserConversation.objects.create(
                    user=user,
                    title=title,
                )
                schedule_async_title_polish(
                    conversation_id=conversation.id,
                    user_id=user.pk,
                    user_message=message,
                    polish_fn=polish_agent_conversation_title,
                    model=UserConversation,
                    thread_name_prefix="polish-title",
                    log_context="agent chat",
                )

            thread_id = agent_checkpoint_thread_id(user.pk, conversation.id)

            # 先落库用户输入
            session_obj = UserSession.objects.create(
                user=user,
                conversation=conversation,
                question=message,
                ai_response="",
            )
            # 调用智能体（ReAct + RAG）
            try:
                reply = agent_chat(
                    message,
                    thread_id=thread_id,
                    enable_web_search=enable_web_search,
                )
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
            # 更新 AI 回复
            session_obj.ai_response = visible
            session_obj.save()

            # 更新会话更新时间
            conversation.save()

            # 响应结构与前端期望保持一致
            resp_data = {
                "reply": visible,
                "conversation_id": conversation.id,
            }
            return HttpResult.success_with_data("对话成功", resp_data)

        except Exception as e:  # noqa: BLE001
            return HttpResult.fail(f"对话失败：{str(e)}")





@method_decorator(csrf_exempt, name="dispatch")
class ChatStreamView(APIView):
    """
    SSE 流式对话（text/event-stream）。
    - 千问 streaming=True；仅「Final Answer:」之后的 token 推给前端（Thought/Action/Observation 不推送）。
    - 推理期间若尚无 Final Answer，周期性 type=ping，避免长时间无字节被网关/浏览器断开。
    - type=stream_done：token 队列结束即发（先于落库）；type=done：落库完成后发，用于结束拉流。
    POST /api/agent/chat/stream/  body: { message, conversation_id? }
    """

    _FALLBACK_DELTA_CHARS = 16
    _PING_INTERVAL_SEC = 2.0
    _WORKER_JOIN_TIMEOUT_SEC = 120.0
    _WORKER_JOIN_AFTER_CANCEL_SEC = 30.0

    def post(self, request):
        trace_event = make_trace_event_logger(
            logger,
            log_key="chat_stream_trace",
            trace_prefix="stream",
        )

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
        enable_web_search = _parse_bool_flag(data.get("enable_web_search"), default=False)

        if resume_pdf is not None:
            if conversation_id is None:
                return JsonResponse(
                    {"success": False, "msg": "恢复 PDF 确认需要 conversation_id"}, status=400
                )
            conversation = UserConversation.objects.filter(id=conversation_id, user=user).first()
            if not conversation:
                return JsonResponse({"success": False, "msg": "会话不存在"}, status=404)
            if not msg_text:
                msg_text = "[PDF导出确认]"
        else:
            if not msg_text:
                return JsonResponse({"success": False, "msg": "消息不能为空"}, status=400)
            conversation = None
            if conversation_id is not None:
                conversation = UserConversation.objects.filter(id=conversation_id, user=user).first()

            if not conversation:
                title = fallback_chat_title(msg_text)
                conversation = UserConversation.objects.create(user=user, title=title)
                schedule_async_title_polish(
                    conversation_id=conversation.id,
                    user_id=user.pk,
                    user_message=msg_text,
                    polish_fn=polish_agent_conversation_title,
                    model=UserConversation,
                    thread_name_prefix="polish-title",
                    log_context="agent chat stream",
                )

        trace_event(
            "request_enter",
            user_id=getattr(user, "pk", None),
            msg_len=len(msg_text),
            resume_pdf=resume_pdf,
            enable_web_search=enable_web_search,
        )

        thread_id = agent_checkpoint_thread_id(user.pk, conversation.id)

        session_obj = UserSession.objects.create(
            user=user,
            conversation=conversation,
            question=msg_text,
            ai_response="",
        )
        trace_event(
            "session_created",
            conversation_id=conversation.id,
            session_id=session_obj.id,
        )

        def gen() -> Iterator[bytes]:
            result_q: queue.Queue = queue.Queue(maxsize=1)
            token_q: queue.Queue = queue.Queue()
            worker_cancel_evt = threading.Event()

            def run_agent() -> None:
                close_old_connections()
                try:
                    reply = run_chat_stream_with_queue(
                        msg_text,
                        token_q,
                        thread_id=thread_id,
                        trace_cb=trace_event,
                        resume_pdf=resume_pdf,
                        enable_web_search=enable_web_search,
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

            # Worker 在发送 token END 之前已将 ok/err 写入 result_q；可先 peek，不必等 join（避免卡在收尾）。
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
                trace_event("stream_done", tokens_received=tokens_received)
                stream_done_sent = True

            # join：收回线程数据库连接；超时则 cancel_event，促使 LangGraph / LLM 流协作退出后再 join。
            worker.join(timeout=self._WORKER_JOIN_TIMEOUT_SEC)
            if worker.is_alive():
                worker_cancel_evt.set()
                log_warning_event(
                    logger,
                    "chat_stream_worker_join_timeout",
                    hint="cancel_event set for cooperative shutdown",
                    tokens_received=tokens_received,
                )
                worker.join(timeout=self._WORKER_JOIN_AFTER_CANCEL_SEC)
                if worker.is_alive():
                    log_error_event(
                        logger,
                        "chat_stream_worker_still_alive_after_cancel",
                        tokens_received=tokens_received,
                    )

            # 须先落库再发 done：若先发 done，浏览器/前端常会立刻断开，迭代器可能被中止，save() 来不及执行。
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
                            "chat_stream_result_queue_empty_with_deltas",
                            hint="check worker timeout or thread errors",
                            tokens_received=tokens_received,
                        )
                    else:
                        log_error_event(logger, "chat_stream_result_queue_empty_after_join")
                    yield _sse_bytes({"type": "done"})
                    trace_event("done", status="result_queue_empty", tokens_received=tokens_received)
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
                        "chat_stream_agent_invoke_failed_after_stream_end",
                        error=str(err),
                    )
                yield _sse_bytes({"type": "done"})
                trace_event("done", status="agent_error", tokens_received=tokens_received)
                return

            reply = str(payload)
            stored = (
                user_visible_reply_inline(reply).strip()
                or _user_visible_reply(reply).strip()
                or reply.strip()
            )
            session_obj.ai_response = stored
            session_obj.save()
            conversation.save()

            # 极少数情况下未触发 token 回调，按块补发（与落库一致，仅最终回答）
            if not tokens_received and stored:
                for i in range(0, len(stored), self._FALLBACK_DELTA_CHARS):
                    chunk = stored[i : i + self._FALLBACK_DELTA_CHARS]
                    yield _sse_bytes({"type": "delta", "text": chunk})
                if got_token_end and not stream_done_sent:
                    yield _sse_bytes({"type": "stream_done"})
                    trace_event("stream_done", tokens_received=tokens_received)

            yield _sse_bytes({"type": "done"})
            trace_event("done", status="ok", tokens_received=tokens_received)

        resp = StreamingHttpResponse(gen(), content_type="text/event-stream; charset=utf-8")
        resp["Cache-Control"] = "no-cache, no-transform"
        resp["X-Accel-Buffering"] = "no"
        return resp


@method_decorator(csrf_exempt, name="dispatch")
class ConversationManageView(APIView):
    """
    会话管理（重命名、置顶、删除）
    - PATCH /api/agent/conversation/  body: { conversation_id, title? } 或 { conversation_id, pinned: bool }
    - DELETE /api/agent/conversation/ body: { conversation_id }
    """

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
            is_pinned = bool(data.get("pinned"))
            conv.pinned = is_pinned
            if is_pinned:
                # 记录置顶时间，用于多条置顶的先后排序
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
        conv = UserConversation.objects.filter(id=cid, user=user).first()
        if not conv:
            return HttpResult.fail("会话不存在")
        conv.delete()
        return HttpResult.success("删除成功")
