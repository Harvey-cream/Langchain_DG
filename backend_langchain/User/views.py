import re
import hashlib
from rest_framework.views import APIView

from .models import User
from .utils.user_utils import get_current_user
from .utils.jwt_token import create_token
from .utils.sm2 import request_handler
from common.response_web import HttpResult
from common.utils import format_datetime


class UserRegisterView(APIView):
    """
    用户注册视图
    """
    def post(self, request, format=None):
        """
        处理用户注册请求
        """
        try:
            data = request.data

            username = (data.get('name') or '').strip()
            email = (data.get('email') or '').strip()
            password = data.get('password') or ''
            # 解密密码
            try:
                password = request_handler.decrypt(password)
            except Exception as e:
                return HttpResult.fail(f"密码解密失败：{str(e)}")
            if not username:
                return HttpResult.fail("用户名不能为空")
            if not email:
                return HttpResult.fail("邮箱不能为空")
            email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
            if not re.match(email_pattern, email):
                return HttpResult.fail("请输入有效的邮箱地址")
            if not password:
                return HttpResult.fail("密码不能为空")
            if len(password) < 6:
                return HttpResult.fail("密码长度不能少于6位")
            if User.objects.filter(email=email).exists():
                return HttpResult.fail("该邮箱已被注册")
            # 哈希加密（SHA-256）
            hashed_password = hashlib.sha256(password.encode()).hexdigest()

            user = User.objects.create(
                username=username,
                email=email,
                password=hashed_password
            )
            user.ensure_display_tag()
            user_data = {
                'user_id': user.user_id,
                'username': user.username,
                'email': user.email,
                'display_tag': user.display_tag,
                'created_at': format_datetime(user.created_at)
            }
            return HttpResult.success_with_data("注册成功", user_data)
        except Exception as e:
            return HttpResult.fail(f"注册失败：{str(e)}")


class UserLoginView(APIView):
    """
    用户登录视图
    """
    def post(self, request, format=None):
        """
        处理用户登录请求
        """
        try:
            data = request.data
            email = (data.get('email') or '').strip()
            password = data.get('password') or ''
            # 解密密码
            try:
                password = request_handler.decrypt(password)
            except Exception as e:
                return HttpResult.fail(f"密码解密失败：{str(e)}")
            if not email:
                return HttpResult.fail("邮箱不能为空")
            email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
            if not re.match(email_pattern, email):
                return HttpResult.fail("请输入有效的邮箱地址")
            if not password:
                return HttpResult.fail("密码不能为空")
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return HttpResult.fail("邮箱或密码错误")
            # 验证密码（SHA-256）
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            if user.password != hashed_password:
                return HttpResult.fail("邮箱或密码错误")
            user.ensure_display_tag()
            # token
            token = create_token(user.user_id)
            response_data = {
                'token': token,
                'user': {
                    'user_id': user.user_id,
                    'username': user.username,
                    'email': user.email,
                    'display_tag': user.display_tag,
                }
            }
            return HttpResult.success_with_data("登录成功", response_data)

        except Exception as e:
            return HttpResult.fail(f"登录失败：{str(e)}")


class UserInfoView(APIView):
    """
    用户信息视图
    """
    def get(self, request):
        user = get_current_user(request)

        if not user:
            return HttpResult.fail("认证失败，请重新登录")
        user.ensure_display_tag()
        user_data = {
            'user_id': user.user_id,
            'username': user.username,
            'email': user.email,
            'display_tag': user.display_tag,
            'created_at': format_datetime(user.created_at)
        }
        return HttpResult.success_with_data("获取成功", user_data)

    def put(self, request, format=None):
        """
        更新当前登录用户信息
        """
        user = get_current_user(request)
        if not user:
            return HttpResult.fail("认证失败，请重新登录")
        try:
            data = request.data
            username = (data.get('username') or '').strip()
            if username:
                user.username = username
                user.save()

            user.ensure_display_tag()
            user_data = {
                'user_id': user.user_id,
                'username': user.username,
                'email': user.email,
                'display_tag': user.display_tag,
                'updated_at': format_datetime(user.updated_at)
            }
            return HttpResult.success_with_data("更新成功", user_data)
        except Exception as e:
            return HttpResult.fail(f"更新失败：{str(e)}")
