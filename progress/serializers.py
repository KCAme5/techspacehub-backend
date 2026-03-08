# progress/serializers.py
from rest_framework import serializers
from .models import UserLessonProgress, UserModuleAccess


class UserLessonProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserLessonProgress
        fields = [
            'id', 'lesson', 'completed', 'drills_done',
            'quiz_passed', 'xp_awarded', 'completed_at'
        ]
        read_only_fields = ['xp_awarded', 'completed_at']


class UserModuleAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserModuleAccess
        fields = ['id', 'module', 'access_type', 'granted_at']
        read_only_fields = ['granted_at']
