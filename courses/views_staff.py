from rest_framework import generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.db import transaction
from django.db.models import Count, Q
from accounts.models import User
from django.utils import timezone
from .models import (
    Category,
    Course,
    Week,
    Lesson,
    WeeklyQuiz,
    WeeklyProject,
    QuizQuestion,
    QuestionChoice,
    Plan,
    Enrollment,
    WeeklyProgress,
    ProjectSubmission,
)
from .staff_serializers import *
from .permissions import IsStaffUser, IsInstructorOrStaff


# Staff Dashboard Statistics
class StaffDashboardView(generics.GenericAPIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta

        # Basic statistics
        total_courses = Course.objects.count()
        total_students = User.objects.filter(role="student").count()
        total_staff = User.objects.filter(role="staff").count()

        # Recent activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_enrollments = Enrollment.objects.filter(
            enrolled_at__gte=thirty_days_ago
        ).count()

        recent_courses = Course.objects.filter(created_at__gte=thirty_days_ago).count()

        # Course statistics
        course_stats = Course.objects.annotate(
            total_students=Count("weeks__enrollments", distinct=True),
            total_weeks=Count("weeks"),
        ).values("id", "title", "total_students", "total_weeks", "created_at")

        data = {
            "overview": {
                "total_courses": total_courses,
                "total_students": total_students,
                "total_staff": total_staff,
                "recent_enrollments": recent_enrollments,
                "recent_courses": recent_courses,
            },
            "course_stats": list(course_stats),
        }

        return Response(data)


# Staff Model ViewSets for CRUD operations
class StaffCategoryViewSet(ModelViewSet):
    permission_classes = [IsStaffUser]
    queryset = Category.objects.all()
    serializer_class = StaffCategorySerializer


class StaffCourseViewSet(ModelViewSet):
    permission_classes = [IsStaffUser]
    queryset = Course.objects.all().select_related("instructor", "category")
    serializer_class = StaffCourseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        # Staff can see all courses, instructors only see their courses
        if self.request.user.role == "staff":
            return queryset
        return queryset.filter(instructor=self.request.user)

    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user)


class StaffWeekViewSet(ModelViewSet):
    permission_classes = [IsStaffUser]
    queryset = Week.objects.all().select_related("course")
    serializer_class = StaffWeekSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        course_id = self.request.query_params.get("course_id")
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        return queryset


class StaffLessonViewSet(ModelViewSet):
    permission_classes = [IsStaffUser]
    queryset = Lesson.objects.all().select_related("week", "week__course")
    serializer_class = StaffLessonSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        week_id = self.request.query_params.get("week_id")
        if week_id:
            queryset = queryset.filter(week_id=week_id)
        return queryset


class StaffWeeklyQuizViewSet(ModelViewSet):
    permission_classes = [IsStaffUser]
    queryset = WeeklyQuiz.objects.all().select_related("week", "week__course")
    serializer_class = StaffWeeklyQuizSerializer


class StaffWeeklyProjectViewSet(ModelViewSet):
    permission_classes = [IsStaffUser]
    queryset = WeeklyProject.objects.all().select_related("week", "week__course")
    serializer_class = StaffWeeklyProjectSerializer


class StaffQuizQuestionViewSet(ModelViewSet):
    permission_classes = [IsStaffUser]
    queryset = QuizQuestion.objects.all().select_related("weekly_quiz")
    serializer_class = StaffQuizQuestionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        quiz_id = self.request.query_params.get("quiz_id")
        if quiz_id:
            queryset = queryset.filter(weekly_quiz_id=quiz_id)
        return queryset


class StaffQuestionChoiceViewSet(ModelViewSet):
    permission_classes = [IsStaffUser]
    queryset = QuestionChoice.objects.all().select_related("question")
    serializer_class = QuestionChoiceSerializer


class StaffPlanViewSet(ModelViewSet):
    permission_classes = [IsStaffUser]
    queryset = Plan.objects.all()
    serializer_class = StaffPlanSerializer


# Bulk Operations
class StaffBulkWeekView(generics.GenericAPIView):
    permission_classes = [IsStaffUser]
    serializer_class = BulkWeekSerializer

    def post(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        weeks_data = serializer.validated_data["weeks"]
        created_weeks = []

        with transaction.atomic():
            for week_data in weeks_data:
                week = Week.objects.create(course=course, **week_data)
                created_weeks.append(week)

        return Response(
            StaffWeekSerializer(created_weeks, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class StaffBulkLessonView(generics.GenericAPIView):
    permission_classes = [IsStaffUser]
    serializer_class = BulkLessonSerializer

    def post(self, request, week_id):
        try:
            week = Week.objects.get(id=week_id)
        except Week.DoesNotExist:
            return Response(
                {"error": "Week not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lessons_data = serializer.validated_data["lessons"]
        created_lessons = []

        with transaction.atomic():
            for lesson_data in lessons_data:
                lesson = Lesson.objects.create(week=week, **lesson_data)
                created_lessons.append(lesson)

        return Response(
            StaffLessonSerializer(created_lessons, many=True).data,
            status=status.HTTP_201_CREATED,
        )


# Project Submission Management for Staff
class StaffProjectSubmissionView(generics.ListAPIView):
    permission_classes = [IsStaffUser]
    serializer_class = StaffProjectSubmissionSerializer

    def get_queryset(self):
        queryset = ProjectSubmission.objects.all().select_related(
            "student",
            "weekly_project",
            "weekly_project__week",
            "weekly_project__week__course",
        )

        project_id = self.request.query_params.get("weekly_project_id")
        status_filter = self.request.query_params.get("status")

        if project_id:
            queryset = queryset.filter(weekly_project_id=project_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset


class StaffProjectSubmissionDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsStaffUser]
    queryset = ProjectSubmission.objects.all()
    serializer_class = StaffProjectSubmissionSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        # Set reviewed_at if status is being changed from submitted/under_review to a final status
        if instance.status in ["submitted", "under_review"] and request.data.get(
            "status"
        ) in ["approved", "needs_revision", "rejected"]:
            request.data["reviewed_at"] = timezone.now()

        return super().update(request, *args, **kwargs)
