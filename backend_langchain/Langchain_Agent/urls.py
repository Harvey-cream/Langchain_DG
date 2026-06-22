from django.urls import path

from .views import (
    ChatStreamView,
    ChatView,
    ConversationManageView,
    InterviewChatStreamView,
    InterviewChatView,
    InterviewConversationManageView,
)

urlpatterns = [
    path("api/agent/chat/", ChatView.as_view(), name="agent_chat"),
    path("api/agent/chat/stream/", ChatStreamView.as_view(), name="agent_chat_stream"),
    path("api/agent/conversation/", ConversationManageView.as_view(), name="agent_conversation_manage"),
    path("api/interview/chat/", InterviewChatView.as_view(), name="interview_chat"),
    path("api/interview/chat/stream/", InterviewChatStreamView.as_view(), name="interview_chat_stream"),
    path(
        "api/interview/conversation/",
        InterviewConversationManageView.as_view(),
        name="interview_conversation_manage",
    ),
]
