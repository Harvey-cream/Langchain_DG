from django.urls import path

from .views import ChatView, ChatStreamView, ConversationManageView

urlpatterns = [
    # POST /api/agent/chat/  发起对话
    # GET  /api/agent/chat/  获取会话列表或历史消息
    path("chat/", ChatView.as_view(), name="agent_chat"),
    path("chat/stream/", ChatStreamView.as_view(), name="agent_chat_stream"),
    path("conversation/", ConversationManageView.as_view(), name="agent_conversation_manage"),
]

