from django.contrib import admin
from .models import Lab


@admin.register(Lab)
class LabAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "category",
        "difficulty",
        "environment_type",
        "is_free",
        "is_active",
        "price",
        "duration_days",
        "created_at",
    )
    list_filter = (
        "category",
        "difficulty",
        "environment_type",
        "is_free",
        "is_active",
    )
    search_fields = ("title", "description", "course__title")
    ordering = ("-created_at",)
    list_editable = ("is_free", "is_active", "price", "duration_days")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic Info", {"fields": ("title", "course", "category", "description")}),
        (
            "Lab Settings",
            {"fields": ("difficulty", "environment_type", "is_free", "is_active")},
        ),
        (
            "Pricing & Duration",
            {"fields": ("price", "duration_days")},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("course")
