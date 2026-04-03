import secrets

from django.db import IntegrityError, models


class User(models.Model):
    """
    用户模型

    存储用户的基本信息，包括用户ID、邮箱、用户名和密码
    """
    user_id = models.AutoField(primary_key=True, verbose_name='用户ID')
    email = models.EmailField(unique=True, max_length=255, verbose_name='邮箱')
    username = models.CharField(max_length=150, verbose_name='用户名')
    password = models.CharField(max_length=255, verbose_name='密码')
    # 侧栏展示「用户123456」用，6 位数字，全局唯一，由后端生成
    display_tag = models.CharField(max_length=6,unique=True,null=True, blank=True,verbose_name='展示编号',)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'users'
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def ensure_display_tag(self) -> str:
        """若尚未分配则生成并保存，返回 6 位数字编号（000000–999999，全局唯一）。"""
        if self.display_tag:
            return self.display_tag
        for _ in range(256):
            self.display_tag = f"{secrets.randbelow(1_000_000):06d}"
            try:
                self.save(update_fields=["display_tag"])
                return self.display_tag
            except IntegrityError:
                self.display_tag = None
        raise RuntimeError("无法为用户分配 display_tag")

    def __str__(self):
        return f"{self.username} ({self.email})"


class UserConversation(models.Model):
    """
    用户的对话会话（一个用户可以创建多个）
    相当于：对话文件夹
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations', db_column='user_id', verbose_name='用户ID')
    title = models.CharField(max_length=255, default='新对话', verbose_name='会话标题')
    pinned = models.BooleanField(default=False, verbose_name='置顶')
    pinned_at = models.DateTimeField(null=True, blank=True, verbose_name='置顶时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'user_conversations'
        verbose_name = '用户对话会话'
        verbose_name_plural = '用户对话会话'
        # 置顶优先，其次按置顶先后（pinned_at 越早越靠前），最后按更新时间
        ordering = ['-pinned', 'pinned_at', '-updated_at']

    def __str__(self):
        return f"会话{self.id}-{self.title}"


class UserSession(models.Model):
    """
    用户会话记录模型
    存储每次对话所属用户、用户问题、AI返回内容和对话时间
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions', db_column='user_id', verbose_name='用户ID')
    conversation = models.ForeignKey(UserConversation, on_delete=models.CASCADE, related_name='messages',
     db_column='conversation_id', verbose_name='会话文件夹ID', null=True, blank=True)
    question = models.TextField(verbose_name='用户问题')
    ai_response = models.TextField(verbose_name='AI模型返回内容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='对话时间')

    class Meta:
        db_table = 'user_sessions'
        verbose_name = '用户会话'
        verbose_name_plural = '用户会话'
        ordering = ['-created_at']

    def __str__(self):
        return f"会话{self.id}-用户{self.user_id}"
