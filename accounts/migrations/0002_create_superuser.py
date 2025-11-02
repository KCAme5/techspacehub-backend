from django.db import migrations
from django.contrib.auth import get_user_model


def create_superuser(apps, schema_editor):
    User = get_user_model()
    if not User.objects.filter(email="marcus@cybercraft.com").exists():
        # Try creating with username first, then fallback to email as username
        try:
            User.objects.create_superuser(
                username="MarcusB",
                email="marcus@cybercraft.com",
                password="adminpassword123Marcus",
            )
        except TypeError:
            # If that fails, try without username (email-only)
            User.objects.create_superuser(
                email="marcus@cybercraft.com", password="adminpassword123Marcus"
            )
        print("Superuser created successfully!")
    else:
        print("Superuser already exists.")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_superuser),
    ]
