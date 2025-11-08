# courses/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from statistics import mean
from rest_framework.parsers import MultiPartParser, FormParser
import random

from .models import (
    Category,
    Course,
    Week,
    Lesson,
    Enrollment,
    Progress,
    WeeklyProgress,
    WeeklyQuiz,
    WeeklyProject,
    QuizQuestion,
    QuestionChoice,
    WeeklyQuizSubmission,
    ProjectSubmission,
    StudentAnswer,
    Plan,
    ProjectFeedback,
    Notification,
)
from .serializers import (
    EnrollmentDashboardSerializer,
    CategorySerializer,
    CourseSerializer,
    CourseListSerializer,
    WeekSerializer,
    LessonSerializer,
    EnrollmentSerializer,
    EnrollmentCreateSerializer,
    ProgressSerializer,
    WeeklyProgressSerializer,
    WeeklyQuizSerializer,
    WeeklyProjectSerializer,
    QuizQuestionSerializer,
    WeeklyQuizSubmissionSerializer,
    WeeklyQuizSubmissionDetailSerializer,
    ProjectSubmissionSerializer,
    StudentAnswerSerializer,
    CoursePerformanceQuizSerializer,
    CoursePerformanceSerializer,
    PlanSerializer,
    ProjectFeedbackSerializer,
    NotificationSerializer,
    QuestionChoiceSerializer,
)


# Category listing
class CategoryList(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


# Course listing and detail
class CourseList(generics.ListAPIView):
    serializer_class = CourseListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = (
            Course.objects.filter(is_active=True)
            .select_related("category", "instructor")
            .prefetch_related("weeks")
        )
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__slug=category)
        level = self.request.query_params.get("level")
        if level:
            qs = qs.filter(weeks__level=level).distinct()
        return qs


class CourseDetail(generics.RetrieveAPIView):
    queryset = Course.objects.filter(is_active=True)
    serializer_class = CourseSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        return (
            Course.objects.filter(is_active=True)
            .select_related("category", "instructor")
            .prefetch_related(
                "weeks__lessons", "weeks__weekly_quiz", "weeks__weekly_project"
            )
        )


class CourseDetailById(generics.RetrieveAPIView):
    queryset = Course.objects.filter(is_active=True)
    serializer_class = CourseSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "id"

    def get_queryset(self):
        return (
            Course.objects.filter(is_active=True)
            .select_related("category", "instructor")
            .prefetch_related(
                "weeks__lessons", "weeks__weekly_quiz", "weeks__weekly_project"
            )
        )


# Week endpoints
class WeekListByCourse(generics.ListAPIView):
    serializer_class = WeekSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        course_slug = self.kwargs.get("slug")
        level = self.request.query_params.get("level")

        qs = (
            Week.objects.filter(course__slug=course_slug)
            .select_related("course")
            .prefetch_related("lessons", "weekly_quiz", "weekly_project")
        )

        if level:
            qs = qs.filter(level=level)

        return qs.order_by("level", "week_number")


class WeekDetail(generics.RetrieveAPIView):
    serializer_class = WeekSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Week.objects.select_related("course").prefetch_related(
            "lessons", "weekly_quiz", "weekly_project"
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class WeekListByLevel(generics.ListAPIView):
    serializer_class = WeekSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        course_slug = self.kwargs.get("slug")
        level = self.kwargs.get("level")
        user = self.request.user

        weeks = (
            Week.objects.filter(course__slug=course_slug, level=level)
            .select_related("course")
            .prefetch_related("lessons", "weekly_quiz", "weekly_project")
            .order_by("week_number")
        )

        paid_enrollments = Enrollment.objects.filter(
            user=user,
            plan__in=["BASIC", "PRO", "PREMIUM"],
        ).values_list("week_id", flat=True)

        weeks = weeks.exclude(id__in=paid_enrollments)
        return weeks


# Enrollment endpoints
class EnrolledWeekList(generics.ListAPIView):
    serializer_class = EnrollmentDashboardSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Enrollment.objects.filter(
            user=self.request.user, is_active=True
        ).select_related("week", "week__course")


class EnrollmentList(generics.ListAPIView):
    serializer_class = EnrollmentDashboardSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Enrollment.objects.filter(user=self.request.user).select_related(
            "week", "week__course"
        )


class EnrollmentCreate(generics.CreateAPIView):
    queryset = Enrollment.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = EnrollmentCreateSerializer

    def create(self, request, *args, **kwargs):
        user = request.user
        week_id = request.data.get("week_id")
        plan = request.data.get("plan", "FREE").upper()

        if not week_id:
            return Response(
                {"error": "Week ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            week = Week.objects.get(id=week_id)
        except Week.DoesNotExist:
            return Response(
                {"error": "Week not found"}, status=status.HTTP_404_NOT_FOUND
            )

        existing_enrollment = Enrollment.objects.filter(user=user, week=week).first()

        if existing_enrollment:
            if existing_enrollment.plan != plan:
                existing_enrollment.plan = plan
                existing_enrollment.save()
            serializer = EnrollmentSerializer(
                existing_enrollment, context={"request": request}
            )
            return Response(
                {
                    "message": f"Enrollment updated to {plan} plan",
                    "enrollment": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        enrollment = Enrollment.objects.create(
            user=user,
            week=week,
            plan=plan,
            is_active=True,
        )

        total_lessons = week.lessons.count()
        weekly_progress, created = WeeklyProgress.objects.get_or_create(
            user=user, week=week, defaults={"total_lessons": total_lessons}
        )

        if not created and weekly_progress.total_lessons != total_lessons:
            weekly_progress.total_lessons = total_lessons
            weekly_progress.save()

        serializer = EnrollmentSerializer(enrollment, context={"request": request})
        return Response(
            {
                "message": f"Successfully enrolled in {week} ({plan} Plan)",
                "enrollment": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


# Progress endpoints
class ProgressList(generics.ListAPIView):
    serializer_class = ProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Progress.objects.filter(user=self.request.user).select_related("lesson")


class ProgressMarkCompleted(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        lesson_id = request.data.get("lesson_id")
        lesson = get_object_or_404(Lesson, id=lesson_id)

        enrollment = get_object_or_404(
            Enrollment, user=request.user, week=lesson.week, is_active=True
        )

        progress, created = Progress.objects.update_or_create(
            user=request.user, lesson=lesson, defaults={"completed_at": timezone.now()}
        )

        weekly_progress, _ = WeeklyProgress.objects.get_or_create(
            user=request.user, week=lesson.week
        )

        completed_lessons = Progress.objects.filter(
            user=request.user, lesson__week=lesson.week, completed_at__isnull=False
        ).count()

        total_lessons = Lesson.objects.filter(week=lesson.week).count()

        weekly_progress.lessons_completed = completed_lessons
        weekly_progress.total_lessons = total_lessons

        if completed_lessons == total_lessons and total_lessons > 0:
            quiz_completed = (
                hasattr(lesson.week, "weekly_quiz")
                and WeeklyQuizSubmission.objects.filter(
                    student=request.user, weekly_quiz__week=lesson.week
                ).exists()
            )

            project_completed = (
                hasattr(lesson.week, "weekly_project")
                and ProjectSubmission.objects.filter(
                    student=request.user, weekly_project__week=lesson.week
                ).exists()
            )

            weekly_progress.week_completed = quiz_completed and project_completed
            if weekly_progress.week_completed and not weekly_progress.completed_at:
                weekly_progress.completed_at = timezone.now()
        else:
            weekly_progress.week_completed = False

        weekly_progress.save()

        serializer = ProgressSerializer(progress)
        return Response(serializer.data)


class ProgressUpdateLastViewed(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        lesson_id = request.data.get("lesson_id")
        lesson = get_object_or_404(Lesson, id=lesson_id)

        get_object_or_404(
            Enrollment, user=request.user, week=lesson.week, is_active=True
        )

        progress, created = Progress.objects.update_or_create(
            user=request.user,
            lesson=lesson,
            defaults={"last_viewed_at": timezone.now()},
        )

        serializer = ProgressSerializer(progress)
        return Response(serializer.data)


class WeeklyProgressDetail(generics.RetrieveAPIView):
    serializer_class = WeeklyProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        week_id = self.kwargs.get("week_id")
        week = get_object_or_404(Week, id=week_id)

        get_object_or_404(Enrollment, user=self.request.user, week=week, is_active=True)

        weekly_progress, created = WeeklyProgress.objects.get_or_create(
            user=self.request.user, week=week
        )

        if created or weekly_progress.total_lessons == 0:
            weekly_progress.total_lessons = week.lessons.count()
            weekly_progress.save()

        return weekly_progress


# Lesson endpoints
class LessonList(generics.ListAPIView):
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        enrolled_week_ids = Enrollment.objects.filter(
            user=self.request.user, is_active=True
        ).values_list("week_id", flat=True)
        return Lesson.objects.filter(week_id__in=enrolled_week_ids)


class LessonDetail(generics.RetrieveAPIView):
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]
    queryset = Lesson.objects.select_related("week", "week__course")

    def retrieve(self, request, *args, **kwargs):
        lesson = self.get_object()
        user = request.user

        enrollment = get_object_or_404(
            Enrollment, user=user, week=lesson.week, is_active=True
        )

        if enrollment.plan == "FREE":
            unlocked_count = 2
            lesson_position = lesson.order
            if lesson_position >= unlocked_count:
                return Response(
                    {
                        "error": "This lesson is locked for free plan. Upgrade to access."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = self.get_serializer(lesson)
        return Response(serializer.data)


# Quiz endpoints
class WeeklyQuizQuestionsView(generics.ListAPIView):
    serializer_class = QuizQuestionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        quiz_id = self.kwargs["quiz_id"]
        weekly_quiz = get_object_or_404(WeeklyQuiz, id=quiz_id)
        week = weekly_quiz.week

        get_object_or_404(Enrollment, user=self.request.user, week=week, is_active=True)

        return (
            QuizQuestion.objects.filter(weekly_quiz_id=quiz_id)
            .prefetch_related("choices")
            .order_by("order")
        )


class WeeklyQuizSubmissionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data

            quiz_id = data.get("weekly_quiz")
            if not quiz_id:
                return Response({"error": "Missing weekly_quiz field"}, status=400)

            try:
                quiz = WeeklyQuiz.objects.get(id=quiz_id)
            except WeeklyQuiz.DoesNotExist:
                return Response({"error": "Quiz not found"}, status=404)

            existing_attempts = WeeklyQuizSubmission.objects.filter(
                student=user, weekly_quiz=quiz
            ).count()
            if existing_attempts >= 2:
                return Response(
                    {"error": "You have reached the maximum number of attempts (2)."},
                    status=403,
                )

            answers = data.get("answers", [])
            correct_count = 0
            evaluated_questions = []

            for ans in answers:
                qid = ans.get("question")
                selected_id = (
                    ans.get("selected_option")
                    or ans.get("selected_choice")
                    or ans.get("choice_id")
                    or ans.get("choice")
                )

                if not qid or not selected_id:
                    continue

                try:
                    question = QuizQuestion.objects.get(id=qid)
                    selected_option = QuestionChoice.objects.get(
                        id=selected_id, question=question
                    )
                except (QuizQuestion.DoesNotExist, QuestionChoice.DoesNotExist):
                    continue

                evaluated_questions.append(qid)

                if selected_option.is_correct:
                    correct_count += 1

            total_questions = len(evaluated_questions) if evaluated_questions else 1
            score = round((correct_count / total_questions) * 100, 2)
            if score.is_integer():
                score = int(score)

            passed = correct_count >= max(1, int(0.7 * total_questions))

            existing_submission = (
                WeeklyQuizSubmission.objects.filter(student=user, weekly_quiz=quiz)
                .order_by("-submitted_at")
                .first()
            )

            if existing_submission:
                if score > existing_submission.score:
                    existing_submission.correct_answers = correct_count
                    existing_submission.total_questions = total_questions
                    existing_submission.score = score
                    existing_submission.passed = passed
                    existing_submission.submitted_at = timezone.now()
                    existing_submission.save()
                    submission = existing_submission
                else:
                    return Response(
                        {
                            "message": "Previous submission retained.",
                            "correct_answers": existing_submission.correct_answers,
                            "total_questions": existing_submission.total_questions,
                            "score": existing_submission.score,
                            "passed": existing_submission.passed,
                        },
                        status=200,
                    )
            else:
                submission = WeeklyQuizSubmission.objects.create(
                    student=user,
                    weekly_quiz=quiz,
                    correct_answers=correct_count,
                    total_questions=total_questions,
                    score=score,
                    passed=passed,
                )

            for ans in answers:
                qid = ans.get("question")
                selected_id = (
                    ans.get("selected_option")
                    or ans.get("selected_choice")
                    or ans.get("choice_id")
                    or ans.get("choice")
                )
                if not qid or not selected_id:
                    continue

                student_answer = StudentAnswer.objects.create(
                    submission=submission, question_id=qid
                )
                student_answer.selected_choices.set([selected_id])

            return Response(
                {
                    "message": "Quiz submitted successfully",
                    "correct_answers": correct_count,
                    "total_questions": total_questions,
                    "score": score,
                    "passed": passed,
                }
            )

        except Exception as e:
            return Response({"error": str(e)}, status=500)


class WeeklyQuizSubmissionHistoryView(generics.ListAPIView):
    serializer_class = WeeklyQuizSubmissionDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        quiz_id = self.kwargs.get("quiz_id")
        if quiz_id:
            weekly_quiz = get_object_or_404(WeeklyQuiz, id=quiz_id)
            week = weekly_quiz.week
            get_object_or_404(Enrollment, user=self.request.user, week=week)
            return WeeklyQuizSubmission.objects.filter(
                student=self.request.user, weekly_quiz=weekly_quiz
            )
        return WeeklyQuizSubmission.objects.filter(student=self.request.user)


class WeeklyQuizSubmissionDetailView(generics.RetrieveAPIView):
    serializer_class = WeeklyQuizSubmissionDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WeeklyQuizSubmission.objects.filter(student=self.request.user)


class WeeklyQuizRandomQuestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        weekly_quiz = get_object_or_404(WeeklyQuiz, id=quiz_id)
        week = weekly_quiz.week

        get_object_or_404(Enrollment, user=request.user, week=week, is_active=True)

        last_submission = (
            WeeklyQuizSubmission.objects.filter(
                student=request.user, weekly_quiz=weekly_quiz
            )
            .order_by("-submitted_at")
            .first()
        )

        if last_submission and last_submission.passed:
            serializer = WeeklyQuizSubmissionDetailSerializer(last_submission)
            return Response(
                {
                    "status": "completed",
                    "result": serializer.data,
                    "message": "You already passed this quiz. Showing your result only.",
                },
                status=200,
            )

        all_questions = QuizQuestion.objects.filter(weekly_quiz_id=quiz_id)
        total_available = all_questions.count()

        questions_count = min(
            weekly_quiz.total_questions or total_available, total_available
        )

        if total_available > questions_count:
            random_question_ids = random.sample(
                list(all_questions.values_list("id", flat=True)), questions_count
            )
            questions = QuizQuestion.objects.filter(id__in=random_question_ids)
        else:
            questions = all_questions

        serializer = QuizQuestionSerializer(
            questions.prefetch_related("choices"), many=True
        )
        return Response(
            {
                "status": "in_progress",
                "total_questions": total_available,
                "questions": serializer.data,
            },
            status=200,
        )


# Project endpoints
class ProjectSubmissionView(generics.CreateAPIView):
    serializer_class = ProjectSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        weekly_project = serializer.validated_data["weekly_project"]
        week = weekly_project.week

        get_object_or_404(Enrollment, user=request.user, week=week, is_active=True)

        existing_submission = ProjectSubmission.objects.filter(
            student=request.user, weekly_project=weekly_project
        ).first()
        if existing_submission:
            return Response(
                {"error": "Project already submitted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        submission = ProjectSubmission(
            student=request.user,
            weekly_project=weekly_project,
            submission_url=serializer.validated_data["submission_url"],
            description=serializer.validated_data["description"],
            status="submitted",
            submitted_at=timezone.now(),
        )
        submission.save()

        weekly_progress, _ = WeeklyProgress.objects.get_or_create(
            user=request.user, week=week
        )
        weekly_progress.project_completed = True
        weekly_progress.save()

        return Response(
            ProjectSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED
        )


class ProjectSubmissionDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ProjectSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ProjectSubmission.objects.filter(student=self.request.user)


class WeeklyProjectDetailView(generics.RetrieveAPIView):
    queryset = WeeklyProject.objects.all()
    serializer_class = WeeklyProjectSerializer
    permission_classes = [IsAuthenticated]


class UserProjectSubmissionsListView(generics.ListAPIView):
    serializer_class = ProjectSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        project_id = self.kwargs["project_id"]
        return ProjectSubmission.objects.filter(
            student=self.request.user, weekly_project_id=project_id
        )


class ProjectFeedbackListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProjectFeedbackSerializer

    def get_queryset(self):
        project_id = self.kwargs["project_id"]
        return ProjectFeedback.objects.filter(
            submission__weekly_project_id=project_id,
            submission__student=self.request.user,
        ).select_related("instructor")


class NotificationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by(
            "-created_at"
        )


class MarkNotificationAsReadView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

    def update(self, request, *args, **kwargs):
        notification = self.get_object()
        if notification.user != request.user:
            return Response(
                {"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN
            )
        notification.is_read = True
        notification.save()
        return Response({"status": "marked as read"})


class ProjectSubmissionView(generics.CreateAPIView):
    serializer_class = ProjectSubmissionSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        weekly_project = serializer.validated_data["weekly_project"]
        week = weekly_project.week

        get_object_or_404(Enrollment, user=request.user, week=week, is_active=True)

        if ProjectSubmission.objects.filter(
            student=request.user, weekly_project=weekly_project
        ).exists():
            return Response(
                {"error": "Project already submitted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        submission = ProjectSubmission.objects.create(
            student=request.user,
            weekly_project=weekly_project,
            submission_url=serializer.validated_data.get("submission_url"),
            submission_file=serializer.validated_data.get("submission_file"),
            description=serializer.validated_data.get("description", ""),
            status="submitted",
            submitted_at=timezone.now(),
        )

        weekly_progress, _ = WeeklyProgress.objects.get_or_create(
            user=request.user, week=week
        )
        weekly_progress.project_completed = True
        weekly_progress.save()

        Notification.objects.create(
            user=request.user,
            title="Project Submitted Successfully!",
            message=f"Your project '{weekly_project.title}' has been submitted and is awaiting review.",
            type="success",
            related_project=weekly_project,
        )

        feedbacks = ProjectFeedback.objects.filter(submission=submission)
        submission_data = ProjectSubmissionSerializer(submission).data
        submission_data["feedbacks"] = ProjectFeedbackSerializer(
            feedbacks, many=True
        ).data

        return Response(submission_data, status=status.HTTP_201_CREATED)


# Plan endpoints
class PlanList(generics.ListAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]


# Course performance view
class CoursePerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        user = request.user

        submissions = WeeklyQuizSubmission.objects.filter(
            student=user, weekly_quiz__week__course=course
        ).order_by("-submitted_at")

        total_quizzes = submissions.count()
        all_quizzes_for_course = WeeklyQuiz.objects.filter(week__course=course).count()

        project_submissions = ProjectSubmission.objects.filter(
            student=user, weekly_project__week__course=course, status="approved"
        )
        projects_completed = project_submissions.count()
        total_projects = WeeklyProject.objects.filter(week__course=course).count()

        if total_quizzes == 0:
            data = {
                "course": course.title,
                "quiz_average": 0.0,
                "quizzes_attempted": 0,
                "total_quizzes": all_quizzes_for_course,
                "projects_completed": projects_completed,
                "total_projects": total_projects,
                "overall_completion": 0.0,
                "quizzes": [],
            }
            return Response(data)

        avg_score = mean([s.score for s in submissions])

        enrolled_weeks = Enrollment.objects.filter(
            user=user, week__course=course, is_active=True
        ).count()
        completed_weeks = WeeklyProgress.objects.filter(
            user=user, week__course=course, week_completed=True
        ).count()

        overall_completion = (
            (completed_weeks / enrolled_weeks * 100) if enrolled_weeks > 0 else 0
        )

        quizzes_serialized = CoursePerformanceQuizSerializer(
            submissions, many=True
        ).data

        data = {
            "course": course.title,
            "quiz_average": round(avg_score, 2),
            "quizzes_attempted": total_quizzes,
            "total_quizzes": all_quizzes_for_course,
            "projects_completed": projects_completed,
            "total_projects": total_projects,
            "overall_completion": round(overall_completion, 2),
            "quizzes": quizzes_serialized,
        }
        return Response(data)


# Week lessons list
class WeekLessonsList(generics.ListAPIView):
    serializer_class = LessonSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        week_id = self.kwargs["week_id"]
        user = self.request.user

        week = Week.objects.filter(id=week_id, enrollments__user=user).first()

        if not week:
            return Lesson.objects.none()

        return Lesson.objects.filter(week_id=week_id).order_by("order")
