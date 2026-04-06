# Generated manually for interview feature tables

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("User", "0005_user_display_tag"),
    ]

    operations = [
        migrations.CreateModel(
            name="InterviewConversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(default="新对话", max_length=255, verbose_name="会话标题")),
                ("pinned", models.BooleanField(default=False, verbose_name="置顶")),
                ("pinned_at", models.DateTimeField(blank=True, null=True, verbose_name="置顶时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "user",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interview_conversations",
                        to="User.user",
                        verbose_name="用户ID",
                    ),
                ),
            ],
            options={
                "verbose_name": "面试会话",
                "verbose_name_plural": "面试会话",
                "db_table": "interview_conversations",
                "ordering": ["-pinned", "pinned_at", "-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="InterviewSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question", models.TextField(verbose_name="用户问题")),
                ("ai_response", models.TextField(verbose_name="AI模型返回内容")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="对话时间")),
                (
                    "conversation",
                    models.ForeignKey(
                        blank=True,
                        db_column="conversation_id",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="User.interviewconversation",
                        verbose_name="会话ID",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interview_sessions",
                        to="User.user",
                        verbose_name="用户ID",
                    ),
                ),
            ],
            options={
                "verbose_name": "面试会话消息",
                "verbose_name_plural": "面试会话消息",
                "db_table": "interview_sessions",
                "ordering": ["-created_at"],
            },
        ),
    ]
