from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from library.models import Resource
from accounts.models import Profile, Subscription, User
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Max, Q, Prefetch
from django.utils import timezone
from datetime import timedelta
import traceback

from courses.models import (
    Course,
    Week,
    Lesson,
    Enrollment,
    Progress,
    WeeklyProgress,
    WeeklyQuizSubmission,
    UserPoints,
)
from .serializers import (
    CourseProgressSerializer,
    RecentActivitySerializer,
    DashboardStatsSerializer,
)


class UserDashboardProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            enrolled_courses = Course.objects.filter(
                weeks__enrollments__user=user, weeks__enrollments__is_active=True
            ).distinct()

            dashboard_data = []

            for course in enrolled_courses:
                course_data = self.get_course_progress_data(course, user)
                if course_data and course_data["levels"]:
                    dashboard_data.append(course_data)

            dashboard_data.sort(
                key=lambda x: x.get("last_accessed") or timezone.now(), reverse=True
            )

            serializer = CourseProgressSerializer(dashboard_data, many=True)
            return Response(serializer.data)

        except Exception as e:
            print(f"DEBUG: Dashboard Progress Error: {str(e)}")
            traceback.print_exc()
            return Response(
                {"error": f"Server Error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get_course_progress_data(self, course, user):
        enrollments = Enrollment.objects.filter(
            user=user, week__course=course, is_active=True
        ).select_related("week")

        if not enrollments.exists():
            return None

        levels_data = []
        total_enrolled_weeks = 0
        total_completed_weeks = 0
        last_accessed = None

        enrolled_weeks_data = enrollments.values_list(
            "week__id", "week__level", "week__week_number"
        ).distinct()

        level_week_map = {}
        for week_id, level, week_number in enrolled_weeks_data:
            if level not in level_week_map:
                level_week_map[level] = []
            level_week_map[level].append(week_number)

        for level, enrolled_week_numbers in level_week_map.items():
            level_enrollments = enrollments.filter(week__level=level)

            if level_enrollments.exists():
                level_data = self.get_level_progress_data(
                    course, user, level, level_enrollments
                )
                if level_data:
                    levels_data.append(level_data)
                    total_enrolled_weeks += len(enrolled_week_numbers)

                    completed_weeks_in_level = WeeklyProgress.objects.filter(
                        user=user,
                        week__course=course,
                        week__level=level,
                        week_completed=True,
                        week__week_number__in=enrolled_week_numbers,
                    ).count()
                    total_completed_weeks += completed_weeks_in_level

        if not levels_data:
            return None

        overall_progress = 0
        if total_enrolled_weeks > 0:
            overall_progress = int((total_completed_weeks / total_enrolled_weeks) * 100)

        last_progress = (
            Progress.objects.filter(user=user, lesson__week__course=course)
            .order_by("-last_viewed_at")
            .first()
        )

        if last_progress:
            last_accessed = last_progress.last_viewed_at

        return {
            "course": course,
            "levels": levels_data,
            "overall_progress": overall_progress,
            "total_enrolled_weeks": total_enrolled_weeks,
            "last_accessed": last_accessed,
        }

    def get_level_progress_data(self, course, user, level, level_enrollments):
        if not level_enrollments.exists():
            return None

        enrolled_weeks_data = level_enrollments.values_list(
            "week__week_number", flat=True
        ).distinct()
        enrolled_weeks = list(enrolled_weeks_data)
        enrolled_weeks.sort()

        completed_weekly_progress = WeeklyProgress.objects.filter(
            user=user, week__course=course, week__level=level, week_completed=True
        )
        completed_weeks = list(
            completed_weekly_progress.values_list(
                "week__week_number", flat=True
            ).distinct()
        )

        total_weeks_in_level = Week.objects.filter(course=course, level=level).count()

        progress_percentage = 0
        if enrolled_weeks:
            progress_percentage = int(
                (len(completed_weeks) / len(enrolled_weeks)) * 100
            )

        current_week = None
        for week_num in enrolled_weeks:
            if week_num not in completed_weeks:
                current_week = week_num
                break

        return {
            "level": level,
            "enrolled_weeks": enrolled_weeks,
            "completed_weeks": completed_weeks,
            "total_weeks_in_level": total_weeks_in_level,
            "progress_percentage": progress_percentage,
            "current_week": current_week,
        }


class RecentActivityView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        days_back = int(request.query_params.get("days", 7))

        since_date = timezone.now() - timedelta(days=days_back)

        recent_lessons = (
            Progress.objects.filter(user=user, last_viewed_at__gte=since_date)
            .select_related("lesson", "lesson__week", "lesson__week__course")
            .order_by("-last_viewed_at")[:10]
        )

        recent_quizzes = (
            WeeklyQuizSubmission.objects.filter(
                student=user, submitted_at__gte=since_date
            )
            .select_related(
                "weekly_quiz", "weekly_quiz__week", "weekly_quiz__week__course"
            )
            .order_by("-submitted_at")[:5]
        )

        activity_data = []

        for progress in recent_lessons:
            activity_data.append(
                {
                    "course_title": progress.lesson.week.course.title,
                    "week_title": progress.lesson.week.title,
                    "level": progress.lesson.week.level,
                    "week_number": progress.lesson.week.week_number,
                    "activity_type": "lesson_viewed",
                    "activity_time": progress.last_viewed_at,
                }
            )

        for quiz in recent_quizzes:
            activity_data.append(
                {
                    "course_title": quiz.weekly_quiz.week.course.title,
                    "week_title": quiz.weekly_quiz.week.title,
                    "level": quiz.weekly_quiz.week.level,
                    "week_number": quiz.weekly_quiz.week.week_number,
                    "activity_type": "quiz_completed",
                    "activity_time": quiz.submitted_at,
                }
            )

        activity_data.sort(key=lambda x: x["activity_time"], reverse=True)
        activity_data = activity_data[:10]

        serializer = RecentActivitySerializer(activity_data, many=True)
        return Response(serializer.data)


class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        total_courses = (
            Course.objects.filter(
                weeks__enrollments__user=user, weeks__enrollments__is_active=True
            )
            .distinct()
            .count()
        )

        total_enrolled_weeks = Enrollment.objects.filter(
            user=user, is_active=True
        ).count()

        completed_weeks = WeeklyProgress.objects.filter(
            user=user, week_completed=True
        ).count()

        overall_progress = 0
        if total_enrolled_weeks > 0:
            overall_progress = int((completed_weeks / total_enrolled_weeks) * 100)

        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_courses = (
            Course.objects.filter(
                weeks__lessons__progress__user=user,
                weeks__lessons__progress__last_viewed_at__gte=thirty_days_ago,
            )
            .distinct()
            .count()
        )

        user_points, _ = UserPoints.objects.get_or_create(user=user)

        stats = {
            "total_courses": total_courses,
            "total_enrolled_weeks": total_enrolled_weeks,
            "completed_weeks": completed_weeks,
            "overall_progress": overall_progress,
            "active_courses": active_courses,
            "total_points": user_points.total_points,
        }

        serializer = DashboardStatsSerializer(stats)
        return Response(serializer.data)


class ContinueLearningView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        enrolled_courses = Course.objects.filter(
            weeks__enrollments__user=user, weeks__enrollments__is_active=True
        ).distinct()

        continue_data = []

        for course in enrolled_courses:
            next_lesson = self.get_next_lesson(course, user)
            if next_lesson:
                continue_data.append(
                    {
                        "course": course.title,
                        "course_id": course.id,
                        "week": next_lesson["week_title"],
                        "week_id": next_lesson["week_id"],
                        "lesson": next_lesson["lesson_title"],
                        "lesson_id": next_lesson["lesson_id"],
                        "level": next_lesson["level"],
                    }
                )

        return Response(continue_data)

    def get_next_lesson(self, course, user):
        uncompleted_lessons = (
            Lesson.objects.filter(
                week__enrollments__user=user,
                week__enrollments__is_active=True,
                week__course=course,
            )
            .exclude(progress__user=user, progress__completed_at__isnull=False)
            .select_related("week")
            .order_by("week__level", "week__week_number", "order")
            .first()
        )

        if uncompleted_lessons:
            return {
                "week_title": uncompleted_lessons.week.title,
                "week_id": uncompleted_lessons.week.id,
                "lesson_title": uncompleted_lessons.title,
                "lesson_id": uncompleted_lessons.id,
                "level": uncompleted_lessons.week.level,
            }

        return None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_library(request):
    resources = Resource.objects.all()
    data = [
        {
            "id": r.id,
            "title": r.title,
            "url": r.file.url if r.file else None,
        }
        for r in resources
    ]
    return Response({"library": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_referral(request):
    profile = Profile.objects.get(user=request.user)
    referrals = User.objects.filter(referred_by=request.user).count()
    earnings = referrals * 100

    return Response(
        {
            "referral_code": profile.referral_code,
            "referrals": referrals,
            "earnings": earnings,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_payment_status(request):
    subscription = Subscription.objects.filter(user=request.user).first()
    if subscription:
        return Response(
            {
                "paid": True,
                "plan": subscription.plan if subscription.plan else None,
                "expires": subscription.expiry_date,
            }
        )
    return Response({"paid": False})
