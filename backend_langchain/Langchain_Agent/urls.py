from django.urls import path

from .views import ChatView, ChatStreamView, ConversationManageView

# 统一写完整路径；根 urls 里用 path('', include(...)) 一次引入即可
urlpatterns = [
    path("api/agent/chat/", ChatView.as_view(), name="agent_chat"),
    path("api/agent/chat/stream/", ChatStreamView.as_view(), name="agent_chat_stream"),
    path("api/agent/conversation/", ConversationManageView.as_view(), name="agent_conversation_manage"),
]
