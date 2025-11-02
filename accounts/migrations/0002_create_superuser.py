from django.db import migrations
from django.contrib.auth import get_user_model


def create_superuser(apps, schema_editor):
    User = get_user_model()
    if not User.objects.filter(email="marcus@cybercraft.com").exists():
        User.objects.create_superuser(
            email="marcus@cybercraft.com", password="adminpassword123Marcus"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_superuser),
    ]
