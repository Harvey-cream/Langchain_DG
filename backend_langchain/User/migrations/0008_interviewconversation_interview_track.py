# Generated manually: 面试大师题库方向

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("User", "0007_alter_userconversation_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="interviewconversation",
            name="interview_track",
            field=models.CharField(
                default="llm",
                help_text="llm=AI大模型面试题 java=Java vue=Vue前端",
                max_length=16,
                verbose_name="面试题库方向",
            ),
        ),
    ]
