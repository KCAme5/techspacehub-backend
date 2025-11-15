from rest_framework import serializers
from .models import Resource, UserBookProgress, ResourceViewLog, FavoriteResource


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = "__all__"


class UserBookProgressSerializer(serializers.ModelSerializer):
    resource_title = serializers.CharField(source="book.title", read_only=True)

    class Meta:
        model = UserBookProgress
        fields = ["id", "book", "resource_title", "is_open", "last_page", "updated_at"]


class ResourceViewLogSerializer(serializers.ModelSerializer):
    resource_title = serializers.CharField(source="resource.title", read_only=True)

    class Meta:
        model = ResourceViewLog
        fields = ["id", "user", "resource", "resource_title", "action", "timestamp"]
        read_only_fields = ["user", "timestamp"]


class FavoriteResourceSerializer(serializers.ModelSerializer):
    resource_title = serializers.CharField(source="resource.title", read_only=True)
    category = serializers.CharField(source="resource.category", read_only=True)
    thumbnail = serializers.ImageField(source="resource.thumbnail", read_only=True)

    class Meta:
        model = FavoriteResource
        fields = [
            "id",
            "user",
            "resource",
            "resource_title",
            "category",
            "thumbnail",
            "added_at",
        ]
        read_only_fields = ["user", "added_at"]


class StaffResourceCreateSerializer(serializers.ModelSerializer):
    """Serializer for staff to create/update resources"""

    class Meta:
        model = Resource
        fields = [
            "title",
            "description",
            "file",
            "thumbnail",
            "category",
            "course",
            "author",
            "is_public",
        ]


class StaffResourceSerializer(serializers.ModelSerializer):
    """Serializer for staff to view resources with all details"""

    course_title = serializers.CharField(source="course.title", read_only=True)
    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "uuid",
            "title",
            "description",
            "file",
            "file_url",
            "thumbnail",
            "thumbnail_url",
            "category",
            "course",
            "course_title",
            "author",
            "is_public",
            "view_count",
            "upload_date",
            "updated_at",
        ]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and hasattr(obj.file, "url"):
            return request.build_absolute_uri(obj.file.url) if request else obj.file.url
        return None

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail and hasattr(obj.thumbnail, "url"):
            return (
                request.build_absolute_uri(obj.thumbnail.url)
                if request
                else obj.thumbnail.url
            )
        return None
