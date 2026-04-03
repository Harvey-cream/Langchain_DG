from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("User", "0002_userconversation_usersession"),
    ]

    operations = [
        migrations.AddField(
            model_name="userconversation",
            name="pinned",
            field=models.BooleanField(default=False, verbose_name="置顶"),
        ),
    ]
