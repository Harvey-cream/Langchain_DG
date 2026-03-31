import json
import re
import hashlib
from rest_framework.views import APIView

from .models import User
from .utils.user_utils import get_current_user
from .utils.jwt_token import create_token
from .utils.sm2 import request_handler
from common.response_web import HttpResult


class UserRegisterView(APIView):
    """
    用户注册视图
    """
    
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        """
        处理用户注册请求
        """
        try:
            # 解析请求体
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            username = data.get('name', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            # 解密密码
            try:
                password = request_handler.decrypt(password)
            except Exception as e:
                return HttpResult.fail(f"密码解密失败：{str(e)}")
            
            # 验证用户名
            if not username:
                return HttpResult.fail("用户名不能为空")
            
            # 验证邮箱
            if not email:
                return HttpResult.fail("邮箱不能为空")
            
            email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
            if not re.match(email_pattern, email):
                return HttpResult.fail("请输入有效的邮箱地址")
            
            # 验证密码
            if not password:
                return HttpResult.fail("密码不能为空")
            
            if len(password) < 6:
                return HttpResult.fail("密码长度不能少于6位")
            
            # 检查邮箱是否已存在
            if User.objects.filter(email=email).exists():
                return HttpResult.fail("该邮箱已被注册")
            
            # 对密码进行MD5加密
            hashed_password = hashlib.md5(password.encode()).hexdigest()
            
            # 创建用户
            user = User.objects.create(
                username=username,
                email=email,
                password=hashed_password
            )
            
            # 返回用户信息
            user_data = {
                'user_id': user.user_id,
                'username': user.username,
                'email': user.email,
                'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return HttpResult.success_with_data("注册成功", user_data)
            
        except json.JSONDecodeError:
            return HttpResult.fail("请求数据格式错误")
        except Exception as e:
            return HttpResult.fail(f"注册失败：{str(e)}")


class UserLoginView(APIView):
    """
    用户登录视图
    """
    
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        """
        处理用户登录请求
        """
        try:
            # 解析请求体
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            # 解密密码
            try:
                password = request_handler.decrypt(password)
            except Exception as e:
                return HttpResult.fail(f"密码解密失败：{str(e)}")
            
            # 验证邮箱
            if not email:
                return HttpResult.fail("邮箱不能为空")
            
            email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
            if not re.match(email_pattern, email):
                return HttpResult.fail("请输入有效的邮箱地址")
            
            # 验证密码
            if not password:
                return HttpResult.fail("密码不能为空")
            
            # 查找用户
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return HttpResult.fail("邮箱或密码错误")
            
            # 验证密码
            hashed_password = hashlib.md5(password.encode()).hexdigest()
            if user.password != hashed_password:
                return HttpResult.fail("邮箱或密码错误")
            
            # 生成JWT token
            token = create_token(user.user_id)
            
            # 返回用户信息和token
            response_data = {
                'token': token,
                'user': {
                    'user_id': user.user_id,
                    'username': user.username,
                    'email': user.email
                }
            }
            
            return HttpResult.success_with_data("登录成功", response_data)
            
        except json.JSONDecodeError:
            return HttpResult.fail("请求数据格式错误")
        except Exception as e:
            return HttpResult.fail(f"登录失败：{str(e)}")


class UserInfoView(APIView):
    """
    用户信息视图
    """
    
    authentication_classes = []
    permission_classes = []
    
    def get(self, request):
        """
        获取当前登录用户信息
        """
        user = get_current_user(request)
        
        if not user:
            return HttpResult.fail("认证失败，请重新登录")
        
        user_data = {
            'user_id': user.user_id,
            'username': user.username,
            'email': user.email,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return HttpResult.success_with_data("获取成功", user_data)
    
    def put(self, request):
        """
        更新当前登录用户信息
        """
        user = get_current_user(request)
        
        if not user:
            return HttpResult.fail("认证失败，请重新登录")
        
        try:
            # 解析请求体
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            username = data.get('username', '').strip()
            
            # 更新用户名
            if username:
                user.username = username
                user.save()
            
            user_data = {
                'user_id': user.user_id,
                'username': user.username,
                'email': user.email,
                'updated_at': user.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return HttpResult.success_with_data("更新成功", user_data)
            
        except json.JSONDecodeError:
            return HttpResult.fail("请求数据格式错误")
        except Exception as e:
            return HttpResult.fail(f"更新失败：{str(e)}")
