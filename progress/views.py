# progress/views.py
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Lesson, Level
from .models import UserLessonProgress, UserModuleAccess
from .services import get_level_progress_state
from .serializers import UserLessonProgressSerializer


class LevelProgressView(APIView):
    """
    GET /api/hub/progress/level/<level_id>/
    Returns full unlock state for all modules + lessons in a level.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, level_id):
        try:
            level = Level.objects.get(pk=level_id, is_published=True)
        except Level.DoesNotExist:
            return Response({'detail': 'Level not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = get_level_progress_state(request.user, level)
        return Response(data)


class CompleteLessonView(APIView):
    """
    POST /api/hub/progress/lesson/<lesson_id>/complete/
    Mark a lesson as complete and award XP to the user.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_id):
        try:
            lesson = Lesson.objects.get(pk=lesson_id, is_published=True)
        except Lesson.DoesNotExist:
            return Response({'detail': 'Lesson not found.'}, status=status.HTTP_404_NOT_FOUND)

        prog, _ = UserLessonProgress.objects.get_or_create(
            user=request.user, lesson=lesson
        )

        if not prog.completed:
            prog.completed    = True
            prog.completed_at = timezone.now()
            prog.save()

        # Award XP (idempotent)
        if not prog.xp_awarded:
            user = request.user
            if hasattr(user, 'total_xp'):
                user.total_xp = (user.total_xp or 0) + lesson.xp_reward
                user.save(update_fields=['total_xp'])
            prog.xp_awarded = True
            prog.save(update_fields=['xp_awarded'])

        return Response({
            'completed':  True,
            'xp_awarded': prog.xp_awarded,
            'xp_amount':  lesson.xp_reward,
        })


class ProgressSummaryView(APIView):
    """
    GET /api/hub/progress/summary/
    Quick dashboard stats for the current user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        completed_lessons = UserLessonProgress.objects.filter(
            user=user, completed=True
        ).count()
        total_xp = getattr(user, 'total_xp', 0) or 0

        return Response({
            'completed_lessons': completed_lessons,
            'total_xp':          total_xp,
        })
