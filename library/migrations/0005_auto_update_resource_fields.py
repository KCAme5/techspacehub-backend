from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0004_auto_20240101_staff_upload"),
    ]

    operations = [
        # Remove author field
        migrations.RemoveField(
            model_name="resource",
            name="author",
        ),
        # Update file -> URLField (if it wasn't already)
        migrations.AlterField(
            model_name="resource",
            name="file",
            field=models.URLField(max_length=500, blank=True, null=True),
        ),
        # Update thumbnail -> URLField
        migrations.AlterField(
            model_name="resource",
            name="thumbnail",
            field=models.URLField(max_length=500, blank=True, null=True),
        ),
        # Change is_public default to True
        migrations.AlterField(
            model_name="resource",
            name="is_public",
            field=models.BooleanField(
                default=True, help_text="Allow free/public access."
            ),
        ),
    ]
