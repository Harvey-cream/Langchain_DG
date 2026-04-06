from django.urls import path

from .views import (
    InterviewChatView,
    InterviewChatStreamView,
    InterviewConversationManageView,
)

urlpatterns = [
    path("api/interview/chat/", InterviewChatView.as_view(), name="interview_chat"),
    path("api/interview/chat/stream/", InterviewChatStreamView.as_view(), name="interview_chat_stream"),
    path(
        "api/interview/conversation/",
        InterviewConversationManageView.as_view(),
        name="interview_conversation_manage",
    ),
]
