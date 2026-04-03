from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("User", "0003_userconversation_pinned"),
    ]

    operations = [
        migrations.AddField(
            model_name="userconversation",
            name="pinned_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="置顶时间"),
        ),
    ]

