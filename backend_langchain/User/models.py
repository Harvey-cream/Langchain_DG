from django.db import models


class User(models.Model):
    """
    用户模型
    
    存储用户的基本信息，包括用户ID、邮箱、用户名和密码
    """
    user_id = models.AutoField(primary_key=True, verbose_name='用户ID')
    email = models.EmailField(unique=True, max_length=255, verbose_name='邮箱')
    username = models.CharField(max_length=150, verbose_name='用户名')
    password = models.CharField(max_length=255, verbose_name='密码')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'users'
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def __str__(self):
        return f"{self.username} ({self.email})"
