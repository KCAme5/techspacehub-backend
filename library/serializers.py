from rest_framework import serializers
from .models import Resource, UserBookProgress, ResourceViewLog, FavoriteResource


"""class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = "__all__"
"""


class ResourceSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    course_slug = serializers.CharField(source="course.slug", read_only=True)

    class Meta:
        model = Resource
        fields = [
            "id",
            "uuid",
            "title",
            "description",
            "file",
            "thumbnail",
            "category",
            "course",
            "course_title",
            "course_slug",
            "is_public",
            "view_count",
            "upload_date",
            "updated_at",
        ]


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
    thumbnail = serializers.URLField(source="resource.thumbnail", read_only=True)

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


'''class StaffResourceCreateSerializer(serializers.ModelSerializer):
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
'''


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
            "is_public",
            "view_count",
            "upload_date",
            "updated_at",
        ]

    def get_file_url(self, obj):
        return obj.file

    def get_thumbnail_url(self, obj):
        return obj.thumbnail


class StaffResourceCreateSerializer(serializers.ModelSerializer):
    """
    Staff upload serializer — only essential fields.
    File + thumbnail accept URLs instead of file uploads.
    Description optional.
    """

    file = serializers.URLField(required=False, allow_null=True)
    thumbnail = serializers.URLField(required=False, allow_null=True)
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    class Meta:
        model = Resource
        fields = [
            "title",
            "description",  # optional
            "file",  # URL
            "thumbnail",  # URL
            "category",
            "course",
        ]

    def create(self, validated_data):
        # Save URLs directly into the file/image fields
        file_url = validated_data.pop("file", None)
        thumbnail_url = validated_data.pop("thumbnail", None)

        resource = Resource.objects.create(**validated_data)

        # Assign URLs manually
        if file_url:
            resource.file = file_url
        if thumbnail_url:
            resource.thumbnail = thumbnail_url

        resource.save()
        return resource

    def update(self, instance, validated_data):
        file_url = validated_data.pop("file", None)
        thumbnail_url = validated_data.pop("thumbnail", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if file_url:
            instance.file = file_url
        if thumbnail_url:
            instance.thumbnail = thumbnail_url

        instance.save()
        return instance
