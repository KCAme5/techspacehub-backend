# dashboard/models.py
from django.db import models
from django.conf import settings


# We might not need models initially, but keeping the file for future use
class DashboardPreference(models.Model):
    """User preferences for dashboard display"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_preferences",
    )
    show_completed_levels = models.BooleanField(default=True)
    default_view = models.CharField(
        max_length=20,
        choices=(
            ("grid", "Grid View"),
            ("list", "List View"),
        ),
        default="grid",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dashboard preferences for {self.user.username}"
