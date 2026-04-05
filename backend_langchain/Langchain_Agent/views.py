from __future__ import annotations

import json
import logging
import queue
import threading
import traceback
from typing import List, Dict, Any, Iterator, Optional
from uuid import UUID

from .utils.SSE import _sse_bytes, _user_visible_reply, _TOKEN_STREAM_END, _FinalAnswerOnlyTokenHandler

from django.db import close_old_connections
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView

from User.models import UserConversation, UserSession
from User.utils.user_utils import get_current_user
from common.response_web import HttpResult
from common.utils import format_datetime
from common.LLM.config import get_qwen_chat_model
from langchain_core.messages import HumanMessage
from django.utils import timezone
from .agent import chat as agent_chat, invoke_agent_with_stream_callbacks

logger = logging.getLogger(__name__)

# 错误详情存库时截断，避免超长 traceback 撑爆数据库行
_MAX_ERROR_DETAIL_LEN = 8000
_TITLE_MAX_LEN = 30


def _fallback_title(message: str) -> str:
    t = (message[:20] or "新对话").strip()
    return t if t else "新对话"


def _polish_conversation_title(user_message: str) -> str:
    """用千问根据首条用户消息生成简短标题；失败则回退为截取前 20 字。"""
    fb = _fallback_title(user_message)
    if not user_message.strip():
        return "新对话"
    try:
        llm = get_qwen_chat_model(temperature=0.3)
        prompt = (
            "你是标题助手。根据用户的第一条消息，生成一个简短、通顺的中文会话标题。"
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

        # 返回指定会话的历史消息
        if conversation_id:
            sessions = (
                UserSession.objects.filter(user=user, conversation_id=conversation_id)
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
                # 会话标题：千问润色生成；失败则取用户问题前 20 字
                title = _polish_conversation_title(message)
                conversation = UserConversation.objects.create(
                    user=user,
                    title=title,
                )

            # 先落库用户输入
            session_obj = UserSession.objects.create(
                user=user,
                conversation=conversation,
                question=message,
                ai_response="",
            )
            # 调用智能体（ReAct + RAG）
            try:
                reply = agent_chat(message)
            except Exception as e:  # noqa: BLE001
                tb = traceback.format_exc()
                detail = f"{str(e)}\n\n--- traceback ---\n{tb}"
                if len(detail) > _MAX_ERROR_DETAIL_LEN:
                    detail = detail[: _MAX_ERROR_DETAIL_LEN] + "\n…(已截断)"
                session_obj.ai_response = f"[智能体调用失败]\n{detail}"
                session_obj.save()
                conversation.save()
                return HttpResult.fail(f"调用智能体失败：{str(e)}")

            # 更新 AI 回复
            session_obj.ai_response = reply
            session_obj.save()

            # 更新会话更新时间
            conversation.save()

            # 响应结构与前端期望保持一致
            resp_data = {
                "reply": reply,
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
    POST /api/agent/chat/stream/  body: { message, conversation_id? }
    """

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
            conversation = UserConversation.objects.filter(id=conversation_id, user=user).first()

        if not conversation:
            title = _polish_conversation_title(msg_text)
            conversation = UserConversation.objects.create(user=user, title=title)

        session_obj = UserSession.objects.create(
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
                # 与 AppConfig 启动预热相同；若后台线程尚未跑完，此处再拉一次（幂等）
                try:
                    from .tools import warmup_rag_singletons

                    warmup_rag_singletons()
                except Exception:
                    logger.exception("chat_stream: warmup_rag_singletons failed")
                handler = _FinalAnswerOnlyTokenHandler(token_q)
                try:
                    reply = invoke_agent_with_stream_callbacks(msg_text, [handler])
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
                    break
                tokens_received += 1
                yield _sse_bytes({"type": "delta", "text": item})

            worker.join(timeout=120.0)

            try:
                kind, payload = result_q.get_nowait()
            except queue.Empty:
                session_obj.ai_response = "[智能体调用失败]\n未收到执行结果"
                session_obj.save()
                conversation.save()
                yield _sse_bytes({"type": "error", "message": "智能体未返回结果"})
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
                yield _sse_bytes({"type": "error", "message": str(err)})
                yield _sse_bytes({"type": "done"})
                return

            reply = str(payload)
            stored = _user_visible_reply(reply)
            session_obj.ai_response = stored
            session_obj.save()
            conversation.save()

            # 极少数情况下未触发 token 回调，按块补发（与落库一致，仅最终回答）
            if not tokens_received and stored:
                for i in range(0, len(stored), self._FALLBACK_DELTA_CHARS):
                    chunk = stored[i : i + self._FALLBACK_DELTA_CHARS]
                    yield _sse_bytes({"type": "delta", "text": chunk})

            yield _sse_bytes({"type": "done"})

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

