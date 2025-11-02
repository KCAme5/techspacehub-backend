"""from rest_framework import serializers
from .models import Resource, UserBookProgress


class ResourceSerializer(serializers.ModelSerializer):
    # Compute file_url dynamically from the FileField
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = ["id", "title", "description", "file_url", "category"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None


class UserBookProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserBookProgress
        fields = ["id", "book", "is_open", "last_page", "updated_at"]
"""

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
