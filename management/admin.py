from django.contrib import admin
from .models import AnalyticsSnapshot, SystemAlert


@admin.register(AnalyticsSnapshot)
class AnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "date",
        "total_users",
        "active_students",
        "total_revenue",
        "avg_completion_rate",
    ]
    list_filter = ["date"]
    ordering = ["-date"]


@admin.register(SystemAlert)
class SystemAlertAdmin(admin.ModelAdmin):
    list_display = ["title", "severity", "is_resolved", "created_at"]
    list_filter = ["severity", "is_resolved"]
    ordering = ["-created_at"]
