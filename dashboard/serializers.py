# dashboard/serializers.py
from rest_framework import serializers
from courses.models import Course, Week, Enrollment, WeeklyProgress
from courses.serializers import CourseSerializer, WeekSerializer
from accounts.models import User


class LevelProgressSerializer(serializers.Serializer):
    """Serializer for level progress within a course"""

    level = serializers.CharField()
    level_display = serializers.SerializerMethodField()
    enrolled_weeks = serializers.ListField(child=serializers.IntegerField())
    completed_weeks = serializers.ListField(child=serializers.IntegerField())
    total_weeks_in_level = serializers.IntegerField()
    progress_percentage = serializers.IntegerField()
    current_week = serializers.IntegerField(allow_null=True)

    def get_level_display(self, obj):
        level_map = {
            "beginner": "Beginner",
            "intermediate": "Intermediate",
            "advanced": "Advanced",
        }
        return level_map.get(obj["level"], obj["level"])


class CourseProgressSerializer(serializers.Serializer):
    """Serializer for course progress with levels"""

    course = CourseSerializer()
    levels = LevelProgressSerializer(many=True)
    overall_progress = serializers.IntegerField()
    total_enrolled_weeks = serializers.IntegerField()
    last_accessed = serializers.DateTimeField(allow_null=True)


class RecentActivitySerializer(serializers.Serializer):
    """Serializer for recent user activity"""

    course_title = serializers.CharField()
    week_title = serializers.CharField()
    level = serializers.CharField()
    week_number = serializers.IntegerField()
    activity_type = serializers.CharField()
    activity_time = serializers.DateTimeField()


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""

    total_courses = serializers.IntegerField()
    total_enrolled_weeks = serializers.IntegerField()
    completed_weeks = serializers.IntegerField()
    overall_progress = serializers.IntegerField()
    active_courses = serializers.IntegerField()
    total_points = serializers.IntegerField()
