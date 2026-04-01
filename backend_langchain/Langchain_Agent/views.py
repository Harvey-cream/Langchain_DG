import json
from rest_framework.views import APIView

from common.response_web import HttpResult
from common.LLM.config import get_qwen_chat_model
from User.utils.user_utils import get_current_user


class ChatView(APIView):
    """阿里云千问对话接口（无系统提示词）"""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user = get_current_user(request)
        if not user:
            return HttpResult.fail('认证失败，请重新登录')

        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST

            user_input = (data.get('message') or '').strip()
            if not user_input:
                return HttpResult.fail('消息不能为空')

            llm = get_qwen_chat_model()
            ai_text = llm.invoke(user_input).content

            return HttpResult.success_with_data('调用成功', {'reply': ai_text})
        except json.JSONDecodeError:
            return HttpResult.fail('请求数据格式错误')
        except Exception as e:
            return HttpResult.fail(f'调用千问失败：{str(e)}')
