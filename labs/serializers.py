from rest_framework import serializers
from .models import Lab
from courses.models import Subscription


class LabSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Lab
        fields = [
            "id",
            "title",
            "course",
            "course_title",
            "category",
            "description",
            "difficulty",
            "environment_type",
            "is_free",
            "is_active",
            "price",
            "duration_days",
            "is_available",
            "created_at",
        ]

    def get_is_available(self, obj):
        user = self.context["request"].user
        sub = Subscription.objects.filter(
            user=user, course=obj.course, is_active=True
        ).first()
        if not sub:
            return obj.is_free
        return sub.plan in ["BASIC", "PRO"]
