from django.contrib import admin
from .models import Resource, UserBookProgress, ResourceViewLog, FavoriteResource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "course",
        "is_public",
        "upload_date",
        "view_count",
    ]
    list_filter = ["category", "course", "is_public", "upload_date"]
    search_fields = ["title", "description", "author"]
    readonly_fields = ["uuid", "view_count", "upload_date", "updated_at"]
    fieldsets = [
        (
            "Basic Information",
            {"fields": ["title", "description", "category", "course", "author"]},
        ),
        ("Media Files", {"fields": ["file", "thumbnail"]}),
        ("Access Control", {"fields": ["is_public"]}),
        (
            "Metadata",
            {
                "fields": ["uuid", "view_count", "upload_date", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]


@admin.register(UserBookProgress)
class UserBookProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "book", "is_open", "last_page", "updated_at"]
    list_filter = ["is_open", "updated_at"]


@admin.register(ResourceViewLog)
class ResourceViewLogAdmin(admin.ModelAdmin):
    list_display = ["user", "resource", "action", "timestamp"]
    list_filter = ["action", "timestamp"]
    readonly_fields = ["timestamp"]


@admin.register(FavoriteResource)
class FavoriteResourceAdmin(admin.ModelAdmin):
    list_display = ["user", "resource", "added_at"]
    list_filter = ["added_at"]
