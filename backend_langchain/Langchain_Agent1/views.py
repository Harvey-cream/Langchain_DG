from __future__ import annotations

import logging
import queue
import threading
import traceback
from typing import Any, Dict, Iterator, List

from common.SSE import (
    _FinalAnswerOnlyTokenHandler,
    _TOKEN_STREAM_END,
    _sse_bytes,
    _user_visible_reply,
)
from common.agent import (
    chat_interview,
    interview_checkpoint_thread_id,
    invoke_interview_agent_with_stream_callbacks,
)
from config.config import get_qwen_chat_model
from common_web.response_web import HttpResult
from common_web.utils import format_datetime
from django.db import close_old_connections
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from langchain_core.messages import HumanMessage
from rest_framework.views import APIView

from User.models import InterviewConversation, InterviewSession
from User.utils.user_utils import get_current_user
logger = logging.getLogger(__name__)

_MAX_ERROR_DETAIL_LEN = 8000
_TITLE_MAX_LEN = 30


def _fallback_title(message: str) -> str:
    t = (message[:20] or "新对话").strip()
    return t if t else "新对话"


def _polish_interview_title(user_message: str) -> str:
    """面试会话标题：提示词侧重求职/面试场景。"""
    fb = _fallback_title(user_message)
    if not user_message.strip():
        return "新对话"
    try:
        llm = get_qwen_chat_model(temperature=0.3)
        prompt = (
            "你是标题助手。根据用户关于面试/求职的第一条消息，生成一个简短、通顺的中文会话标题。"
            f"要求：5～15 个字为宜，不超过 {_TITLE_MAX_LEN} 个字；不要引号、不要标点结尾、不要解释、只输出标题一行。\n\n"
            f"用户消息：\n{user_message[:800]}"
        )
        resp = llm.invoke([HumanMessage(content=prompt)])
        text = (getattr(resp, "content", None) or str(resp)).strip()
        text = text.splitlines()[0].strip()
        for q in ('"', "'", "「", "」", "《", "》"):
            text = text.replace(q, "")
        text = text.strip()
        if len(text) > _TITLE_MAX_LEN:
            text = text[:_TITLE_MAX_LEN]
        return text if text else fb
    except Exception:
        return fb


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
            sessions = (
                InterviewSession.objects.filter(user=user, conversation_id=conversation_id)
                .order_by("created_at")
                .all()
            )
            messages: List[Dict[str, Any]] = []
            for s in sessions:
                messages.append(
                    {
                        "id": s.id,
                        "question": s.question,
                        "ai_response": s.ai_response,
                        "created_at": format_datetime(s.created_at),
                    }
                )
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
                title = _polish_interview_title(message)
                conversation = InterviewConversation.objects.create(
                    user=user,
                    title=title,
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

    def post(self, request):
        user = get_current_user(request)
        if not user:
            return JsonResponse({"success": False, "msg": "认证失败，请重新登录"}, status=401)

        data = request.data if isinstance(request.data, dict) else {}
        msg_text = (data.get("message") or "").strip()
        if not msg_text:
            return JsonResponse({"success": False, "msg": "消息不能为空"}, status=400)

        conversation_id = data.get("conversation_id")
        conversation = None
        if conversation_id is not None:
            conversation = InterviewConversation.objects.filter(id=conversation_id, user=user).first()

        if not conversation:
            title = _polish_interview_title(msg_text)
            conversation = InterviewConversation.objects.create(user=user, title=title)

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

            def run_agent() -> None:
                close_old_connections()
                try:
                    from Langchain_Agent1.tools import warmup_interview_rag_singletons

                    warmup_interview_rag_singletons()
                except Exception:
                    logger.exception("interview_chat_stream: warmup_interview_rag_singletons failed")
                handler = _FinalAnswerOnlyTokenHandler(token_q)
                try:
                    reply = invoke_interview_agent_with_stream_callbacks(
                        msg_text,
                        [handler],
                        thread_id=thread_id,
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
                tokens_received += 1
                yield _sse_bytes({"type": "delta", "text": item})

            stream_done_sent = False
            if got_token_end and tokens_received:
                yield _sse_bytes({"type": "stream_done"})
                stream_done_sent = True

            # 须先 join + 落库，再发 done：若先发 done，客户端断开可能中止生成器，save() 来不及执行。
            worker.join(timeout=120.0)

            try:
                kind, payload = result_q.get_nowait()
            except queue.Empty:
                session_obj.ai_response = "[智能体调用失败]\n未收到执行结果"
                session_obj.save()
                conversation.save()
                if not got_token_end:
                    yield _sse_bytes({"type": "error", "message": "智能体未返回结果"})
                elif tokens_received:
                    logger.warning(
                        "interview_chat_stream: result_q empty after worker ended but deltas were sent; "
                        "check worker timeout or thread errors"
                    )
                else:
                    logger.error("interview_chat_stream: result_q empty after worker join")
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
                    logger.error(
                        "interview_chat_stream: agent invoke failed after stream ended: %s", err, exc_info=True
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
