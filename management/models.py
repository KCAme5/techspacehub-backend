from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class AnalyticsSnapshot(models.Model):
    """Daily snapshot of key platform metrics"""

    date = models.DateField(unique=True, default=timezone.now)

    # User metrics
    total_users = models.PositiveIntegerField(default=0)
    active_students = models.PositiveIntegerField(default=0)
    active_staff = models.PositiveIntegerField(default=0)
    new_users_today = models.PositiveIntegerField(default=0)

    # Course metrics
    total_courses = models.PositiveIntegerField(default=0)
    total_enrollments = models.PositiveIntegerField(default=0)
    active_enrollments = models.PositiveIntegerField(default=0)

    # Financial metrics
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    revenue_today = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    successful_payments = models.PositiveIntegerField(default=0)
    pending_payments = models.PositiveIntegerField(default=0)

    # Engagement metrics
    quiz_submissions_today = models.PositiveIntegerField(default=0)
    project_submissions_today = models.PositiveIntegerField(default=0)
    avg_completion_rate = models.FloatField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Analytics - {self.date}"


class SystemAlert(models.Model):
    """System-wide alerts for management"""

    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="low")
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_alerts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.severity.upper()} - {self.title}"
