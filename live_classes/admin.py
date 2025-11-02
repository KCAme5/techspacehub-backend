"""# live_classes/admin.py
from django.contrib import admin
from .models import LiveClass, LiveClassRecording, LiveClassAttendance


@admin.register(LiveClass)
class LiveClassAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "instructor",
        "start_time",
        "end_time",
        "visibility",
        "is_cancelled",
    )
    list_filter = ("course", "visibility", "is_cancelled", "repeat")
    search_fields = ("title", "course__title", "instructor__username")
    ordering = ("-start_time",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Details", {"fields": ("course", "title", "description", "instructor")}),
        (
            "Schedule",
            {
                "fields": (
                    "start_time",
                    "end_time",
                    "timezone",
                    "repeat",
                    "repeat_count",
                    "capacity",
                )
            },
        ),
        (
            "Jitsi & Access",
            {
                "fields": (
                    "visibility",
                    "jitsi_room_name",
                    "jitsi_meet_url",
                    "jitsi_password",
                )
            },
        ),
        (
            "Status",
            {"fields": ("allow_recording", "recording_available", "is_cancelled")},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(LiveClassRecording)
class LiveClassRecordingAdmin(admin.ModelAdmin):
    list_display = (
        "live_class",
        "title",
        "recorded_at",
        "file_url",
        "duration_seconds",
    )
    search_fields = ("live_class__title", "title")
    list_filter = ("recorded_at",)
    ordering = ("-recorded_at",)


@admin.register(LiveClassAttendance)
class LiveClassAttendanceAdmin(admin.ModelAdmin):
    list_display = ("live_class", "user", "status", "joined_at", "left_at")
    search_fields = ("live_class__title", "user__username")
    list_filter = ("status",)
    ordering = ("-joined_at",)"""
