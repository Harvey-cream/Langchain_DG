import random

from django.db import migrations, models


def backfill_display_tags(apps, schema_editor):
    User = apps.get_model("User", "User")
    for user in User.objects.all():
        if user.display_tag:
            continue
        for _ in range(500):
            tag = f"{random.randint(100000, 999999)}"
            if not User.objects.filter(display_tag=tag).exists():
                user.display_tag = tag
                user.save(update_fields=["display_tag"])
                break


class Migration(migrations.Migration):

    dependencies = [
        ("User", "0004_userconversation_pinned_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="display_tag",
            field=models.CharField(
                blank=True,
                max_length=6,
                null=True,
                unique=True,
                verbose_name="展示编号",
            ),
        ),
        migrations.RunPython(backfill_display_tags, migrations.RunPython.noop),
    ]
