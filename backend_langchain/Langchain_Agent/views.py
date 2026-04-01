from rest_framework.views import APIView

from common.response_web import HttpResult
from common.LLM.config import get_qwen_chat_model
from common.utils import format_datetime
from User.models import UserConversation, UserSession
from User.utils.user_utils import get_current_user


class ChatView(APIView):
    """阿里云千问对话接口（无系统提示词）"""

    def get(self, request):
        user = get_current_user(request)
        if not user:
            return HttpResult.fail('认证失败，请重新登录')

        conversation_id = request.GET.get('conversation_id')

        if conversation_id:
            conversation = UserConversation.objects.filter(id=conversation_id, user=user).first()
            if not conversation:
                return HttpResult.fail('会话不存在')

            sessions = UserSession.objects.filter(user=user, conversation=conversation).order_by('created_at')
            messages = [
                {
                    'id': session.id,
                    'question': session.question,
                    'ai_response': session.ai_response,
                    'created_at': format_datetime(session.created_at),
                }
                for session in sessions
            ]

            return HttpResult.success_with_data('获取成功', {
                'conversation': {
                    'id': conversation.id,
                    'title': conversation.title,
                    'created_at': format_datetime(conversation.created_at),
                    'updated_at': format_datetime(conversation.updated_at),
                },
                'messages': messages,
            })

        conversations = UserConversation.objects.filter(user=user).order_by('-updated_at')
        conversation_list = [
            {
                'id': conversation.id,
                'title': conversation.title,
                'created_at': format_datetime(conversation.created_at),
                'updated_at': format_datetime(conversation.updated_at),
            }
            for conversation in conversations
        ]

        return HttpResult.success_with_data('获取成功', {'conversations': conversation_list})

    def post(self, request):
        user = get_current_user(request)
        if not user:
            return HttpResult.fail('认证失败，请重新登录')

        try:
            data = request.data
            user_input = (data.get('message') or '').strip()
            conversation_id = data.get('conversation_id')

            if not user_input:
                return HttpResult.fail('消息不能为空')

            conversation = None
            if conversation_id:
                conversation = UserConversation.objects.filter(id=conversation_id, user=user).first()

            if not conversation:
                conversation = UserConversation.objects.create(user=user, title='新对话')

            llm = get_qwen_chat_model()
            ai_text = llm.invoke(user_input).content

            UserSession.objects.create(
                user=user,
                conversation=conversation,
                question=user_input,
                ai_response=ai_text,
            )

            return HttpResult.success_with_data('调用成功', {
                'reply': ai_text,
                'conversation_id': conversation.id,
            })
        except Exception as e:
            return HttpResult.fail(f'调用千问失败：{str(e)}')
