# progress/admin.py
from django.contrib import admin
from .models import UserLessonProgress, UserModuleAccess


@admin.register(UserLessonProgress)
class UserLessonProgressAdmin(admin.ModelAdmin):
    list_display  = ['user', 'lesson', 'completed', 'drills_done', 'quiz_passed', 'xp_awarded', 'completed_at']
    list_filter   = ['completed', 'quiz_passed', 'xp_awarded']
    search_fields = ['user__username', 'lesson__title']
    readonly_fields = ['completed_at']


@admin.register(UserModuleAccess)
class UserModuleAccessAdmin(admin.ModelAdmin):
    list_display  = ['user', 'module', 'access_type', 'granted_at', 'payment']
    list_filter   = ['access_type']
    search_fields = ['user__username', 'module__title']
    readonly_fields = ['granted_at']
