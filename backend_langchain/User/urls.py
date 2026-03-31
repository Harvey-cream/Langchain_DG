from django.urls import path
from .views import UserRegisterView, UserLoginView, UserInfoView

urlpatterns = [
    # 用户登录
    path('login/', UserLoginView.as_view(), name='user_login'),
    # 用户注册
    path('register/', UserRegisterView.as_view(), name='user_register'),
    # 刷新令牌
    # path('refresh_token/', RefreshTokenView.as_view(), name='refresh_token'),
    # 用户信息
    path('info/', UserInfoView.as_view(), name='user_info'),
    # 更新用户信息
    # path('info/update/', UpdateUserInfoView.as_view(), name='update_user_info'),
    # 上传头像
    # path('info/avatar/', UploadAvatarView.as_view(), name='upload_avatar'),
    # 用户签到
    # path('checkin/', UserCheckInView.as_view(), name='user_checkin'),
    # 用户统计
    # path('stats/', GetUserStatsView.as_view(), name='get_user_stats'),
    # 勋章列表
    # path('medal/list/', GetMedalListView.as_view(), name='get_medal_list'),
    # 用户积分
    # path('points/', GetUserPointsView.as_view(), name='get_user_points'),
    # 积分签到
    # path('points/signin/', UserPointSignInView.as_view(), name='user_point_signin'),
    # 邀请二维码
    # path('invite/qr/', GetInviteQRView.as_view(), name='get_invite_qr'),
]
