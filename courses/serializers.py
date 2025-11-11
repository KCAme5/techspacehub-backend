# courses/serializers.py
from rest_framework import serializers
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import *


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = "__all__"


class QuestionChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionChoice
        fields = ["id", "choice_text", "order", "is_correct"]


class QuizQuestionSerializer(serializers.ModelSerializer):
    choices = QuestionChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = QuizQuestion
        fields = [
            "id",
            "question_text",
            "question_type",
            "points",
            "order",
            "choices",
            "explanation",
        ]


class WeeklyQuizSerializer(serializers.ModelSerializer):
    questions = QuizQuestionSerializer(many=True, read_only=True)
    has_submission = serializers.SerializerMethodField()
    user_score = serializers.SerializerMethodField()

    class Meta:
        model = WeeklyQuiz
        fields = [
            "id",
            "week",
            "title",
            "description",
            "time_limit",
            "passing_score",
            "total_questions",
            "is_active",
            "questions",
            "has_submission",
            "user_score",
        ]

    def get_has_submission(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.submissions.filter(student=request.user).exists()
        return False

    def get_user_score(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            submission = obj.submissions.filter(student=request.user).first()
            return submission.score if submission else None
        return None


class WeeklyProjectSerializer(serializers.ModelSerializer):
    has_submission = serializers.SerializerMethodField()
    user_status = serializers.SerializerMethodField()

    class Meta:
        model = WeeklyProject
        fields = [
            "id",
            "week",
            "title",
            "description",
            "objectives",
            "requirements",
            "resources",
            "difficulty",
            "estimated_hours",
            "submission_instructions",
            "is_active",
            "has_submission",
            "user_status",
        ]

    def get_has_submission(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.submissions.filter(student=request.user).exists()
        return False

    def get_user_status(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            submission = obj.submissions.filter(student=request.user).first()
            return submission.status if submission else None
        return None


class SimpleWeekSerializer(serializers.ModelSerializer):
    """Simple serializer for Week to avoid recursion"""

    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = Week
        fields = [
            "id",
            "course",
            "course_title",
            "level",
            "week_number",
            "title",
            "description",
            "price",
            "is_free",
            "order",
        ]


class LessonSerializer(serializers.ModelSerializer):
    is_completed = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()
    enrollment_plan = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            "id",
            "week",
            "title",
            "slug",
            "content",
            "video_url",
            "pdf_url",
            "code_sniplet",
            "duration",
            "order",
            "is_preview",
            "is_completed",
            "is_locked",
            "enrollment_plan",
        ]

    def get_is_completed(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Progress.objects.filter(
                user=request.user, lesson=obj, completed_at__isnull=False
            ).exists()
        return False

    def get_is_locked(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return True

        enrollment = Enrollment.objects.filter(
            user=request.user, week=obj.week, is_active=True
        ).first()

        if not enrollment:
            return True

        if enrollment.plan == "FREE":
            unlocked_count = 2
            lesson_position = obj.order
            return lesson_position >= unlocked_count

        return False

    def get_enrollment_plan(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            enrollment = Enrollment.objects.filter(
                user=request.user, week=obj.week, is_active=True
            ).first()
            return enrollment.plan if enrollment else None
        return None


class CourseSerializer(serializers.ModelSerializer):
    instructor_detail = UserSerializer(source="instructor", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    # Use SimpleWeekSerializer for weeks to avoid recursion in course views
    weeks = SimpleWeekSerializer(many=True, read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    levels_available = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "thumbnail",
            "thumbnail_url",
            "category",
            "category_name",
            "is_active",
            "instructor",
            "instructor_detail",
            "created_at",
            "updated_at",
            "weeks",
            "levels_available",
        ]

    def get_thumbnail_url(self, obj):
        return obj.thumbnail if obj.thumbnail else None

    def get_levels_available(self, obj):
        levels = []
        for level_key, level_name in Week.LEVEL_CHOICES:
            weeks = obj.weeks.filter(level=level_key)
            if weeks.exists():
                levels.append(
                    {
                        "key": level_key,
                        "name": level_name,
                        "week_count": weeks.count(),
                    }
                )
        return levels


class CourseListSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    instructor_name = serializers.CharField(
        source="instructor.get_full_name", read_only=True
    )
    thumbnail_url = serializers.SerializerMethodField()
    levels_available = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "thumbnail",
            "thumbnail_url",
            "category_name",
            "instructor_name",
            "is_active",
            "created_at",
            "updated_at",
            "levels_available",
        ]

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_thumbnail_url(self, obj):
        return obj.thumbnail if obj.thumbnail else None

    def get_levels_available(self, obj):
        levels = obj.weeks.values_list("level", flat=True).distinct()
        return list(levels)


class WeekSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    weekly_quiz = WeeklyQuizSerializer(read_only=True)
    weekly_project = WeeklyProjectSerializer(read_only=True)
    is_enrolled = serializers.SerializerMethodField()
    enrollment_plan = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    has_quiz = serializers.SerializerMethodField()
    has_project = serializers.SerializerMethodField()

    class Meta:
        model = Week
        fields = [
            "id",
            "course",
            "level",
            "week_number",
            "title",
            "description",
            "price",
            "is_free",
            "order",
            "lessons",
            "weekly_quiz",
            "weekly_project",
            "is_enrolled",
            "enrollment_plan",
            "progress",
            "has_quiz",
            "has_project",
        ]

    def get_is_enrolled(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            try:
                return Enrollment.objects.filter(
                    user=request.user, week=obj, is_active=True
                ).exists()
            except Exception as e:
                print(f"Error checking enrollment: {e}")
                return False
        return False

    def get_enrollment_plan(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            try:
                enrollment = (
                    Enrollment.objects.filter(
                        user=request.user, week=obj, is_active=True
                    )
                    .values("id", "plan")
                    .first()
                )
                plan = enrollment["plan"] if enrollment else None
                print(
                    f"DEBUG: User {request.user.username} enrollment plan for week {obj.id}: {plan}"
                )
                return plan
            except Exception as e:
                print(f"Error getting enrollment plan: {e}")
                return None

        return None

    def get_progress(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            weekly_progress = WeeklyProgress.objects.filter(
                user=request.user, week=obj
            ).first()
            if weekly_progress:
                return {
                    "lessons_completed": weekly_progress.lessons_completed,
                    "total_lessons": weekly_progress.total_lessons,
                    "completion_percentage": weekly_progress.completion_percentage,
                    "quiz_completed": weekly_progress.quiz_completed,
                    "project_completed": weekly_progress.project_completed,
                    "week_completed": weekly_progress.week_completed,
                }
        return None

    def get_has_quiz(self, obj):
        return hasattr(obj, "weekly_quiz") and obj.weekly_quiz is not None

    def get_has_project(self, obj):
        return hasattr(obj, "weekly_project") and obj.weekly_project is not None


class EnrollmentDashboardSerializer(serializers.ModelSerializer):
    week_title = serializers.CharField(source="week.title", read_only=True)
    week_level = serializers.CharField(source="week.level", read_only=True)
    week_number = serializers.IntegerField(source="week.week_number", read_only=True)
    course_title = serializers.CharField(source="week.course.title", read_only=True)
    course_id = serializers.IntegerField(source="week.course.id", read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "week",
            "week_title",
            "week_level",
            "week_number",
            "course_title",
            "course_id",
            "plan",
            "enrolled_at",
            "completed",
            "progress",
            "is_active",
        ]


class EnrollmentSerializer(serializers.ModelSerializer):
    # Use SimpleWeekSerializer to avoid recursion
    week = SimpleWeekSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    progress_detail = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "user",
            "week",
            "plan",
            "enrolled_at",
            "completed",
            "progress",
            "is_active",
            "progress_detail",
        ]
        read_only_fields = ["user", "enrolled_at", "progress"]

    def get_progress_detail(self, obj):
        try:
            weekly_progress = WeeklyProgress.objects.filter(
                user=obj.user, week=obj.week
            ).first()
            if weekly_progress:
                return {
                    "lessons_completed": weekly_progress.lessons_completed,
                    "total_lessons": weekly_progress.total_lessons,
                    "completion_percentage": weekly_progress.completion_percentage,
                    "quiz_completed": weekly_progress.quiz_completed,
                    "project_completed": weekly_progress.project_completed,
                    "week_completed": weekly_progress.week_completed,
                }
            return {
                "lessons_completed": 0,
                "total_lessons": 0,
                "completion_percentage": 0,
            }
        except Exception as e:
            return {
                "lessons_completed": 0,
                "total_lessons": 0,
                "completion_percentage": 0,
            }


class EnrollmentCreateSerializer(serializers.ModelSerializer):
    week_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Enrollment
        fields = ["week_id", "plan"]

    def validate_week_id(self, value):
        if not Week.objects.filter(id=value).exists():
            raise serializers.ValidationError("Week not found.")
        return value

    def create(self, validated_data):
        week_id = validated_data.pop("week_id")
        week = Week.objects.get(id=week_id)
        user = self.context["request"].user

        if Enrollment.objects.filter(user=user, week=week).exists():
            raise serializers.ValidationError("You are already enrolled in this week.")

        enrollment = Enrollment.objects.create(
            user=user, week=week, plan=validated_data.get("plan", "FREE")
        )

        # Create weekly progress record
        total_lessons = week.lessons.count()
        WeeklyProgress.objects.create(user=user, week=week, total_lessons=total_lessons)

        return enrollment


class ProgressSerializer(serializers.ModelSerializer):
    lesson_detail = LessonSerializer(source="lesson", read_only=True)

    class Meta:
        model = Progress
        fields = [
            "id",
            "user",
            "lesson",
            "lesson_detail",
            "completed_at",
            "last_viewed_at",
        ]


class WeeklyProgressSerializer(serializers.ModelSerializer):
    # Use SimpleWeekSerializer to avoid recursion
    week = SimpleWeekSerializer(read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = WeeklyProgress
        fields = [
            "id",
            "user",
            "week",
            "lessons_completed",
            "total_lessons",
            "completion_percentage",
            "quiz_completed",
            "project_completed",
            "week_completed",
            "completed_at",
        ]


class StudentAnswerSerializer(serializers.ModelSerializer):
    selected_choices = serializers.PrimaryKeyRelatedField(
        many=True, queryset=QuestionChoice.objects.all(), required=False
    )
    question = serializers.PrimaryKeyRelatedField(queryset=QuizQuestion.objects.all())

    class Meta:
        model = StudentAnswer
        fields = ["question", "answer_text", "selected_choices"]


class WeeklyQuizSubmissionSerializer(serializers.ModelSerializer):
    answers = StudentAnswerSerializer(many=True, write_only=True)
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    week_title = serializers.CharField(source="weekly_quiz.week.title", read_only=True)

    class Meta:
        model = WeeklyQuizSubmission
        fields = [
            "id",
            "weekly_quiz",
            "week_title",
            "student",
            "student_name",
            "submitted_at",
            "score",
            "total_questions",
            "correct_answers",
            "time_taken",
            "passed",
            "answers",
        ]
        read_only_fields = [
            "student",
            "submitted_at",
            "score",
            "total_questions",
            "correct_answers",
            "passed",
        ]


class StudentAnswerDetailSerializer(serializers.ModelSerializer):
    question = QuizQuestionSerializer(read_only=True)
    correct_choices = serializers.SerializerMethodField()

    class Meta:
        model = StudentAnswer
        fields = [
            "id",
            "question",
            "answer_text",
            "selected_choices",
            "is_correct",
            "points_earned",
            "correct_choices",
        ]

    def get_correct_choices(self, obj):
        correct_choices = obj.question.choices.filter(is_correct=True)
        return QuestionChoiceSerializer(correct_choices, many=True).data


class WeeklyQuizSubmissionDetailSerializer(serializers.ModelSerializer):
    answers = serializers.SerializerMethodField()
    week_title = serializers.CharField(source="weekly_quiz.week.title", read_only=True)

    class Meta:
        model = WeeklyQuizSubmission
        fields = [
            "id",
            "weekly_quiz",
            "week_title",
            "submitted_at",
            "score",
            "total_questions",
            "correct_answers",
            "time_taken",
            "passed",
            "answers",
        ]

    def get_answers(self, obj):
        answers = obj.answers.all().select_related("question")
        return StudentAnswerDetailSerializer(answers, many=True).data


class ProjectSubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    project_title = serializers.CharField(source="weekly_project.title", read_only=True)
    file_name = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()

    class Meta:
        model = ProjectSubmission
        fields = [
            "id",
            "weekly_project",
            "project_title",
            "student",
            "student_name",
            "submission_url",
            "submission_file",
            "file_name",
            "file_size",
            "description",
            "status",
            "submitted_at",
            "reviewed_at",
            "reviewer_feedback",
            "score",
        ]
        read_only_fields = [
            "student",
            "submitted_at",
            "reviewed_at",
            "status",
        ]
        extra_kwargs = {
            "description": {"allow_blank": True, "required": False},
            "submission_url": {"allow_blank": True, "required": False},
        }

    def get_file_name(self, obj):
        if obj.submission_file:
            return obj.submission_file.name.split("/")[-1]
        return None

    def get_file_size(self, obj):
        if obj.submission_file and obj.submission_file.size:
            return obj.submission_file.size
        return None

    def validate(self, data):
        # Ensure at least one submission method is provided
        if not data.get("submission_url") and not data.get("submission_file"):
            raise serializers.ValidationError(
                "Either submission URL or file must be provided."
            )
        return data


# serializers.py
class ProjectFeedbackSerializer(serializers.ModelSerializer):
    instructor_name = serializers.SerializerMethodField()

    class Meta:
        model = ProjectFeedback
        fields = [
            "id",
            "submission",
            "instructor",
            "instructor_name",
            "feedback",
            "status",
            "created_at",
        ]
        read_only_fields = ["instructor", "created_at"]

    def get_instructor_name(self, obj):
        return obj.instructor.get_full_name() or obj.instructor.username


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "type",
            "related_project",
            "is_read",
            "created_at",
        ]
        read_only_fields = ["created_at"]


# Performance serializers
class CoursePerformanceQuizSerializer(serializers.ModelSerializer):
    week_title = serializers.CharField(source="weekly_quiz.week.title", read_only=True)

    class Meta:
        model = WeeklyQuizSubmission
        fields = [
            "id",
            "weekly_quiz",
            "week_title",
            "score",
            "total_questions",
            "correct_answers",
            "submitted_at",
            "time_taken",
            "passed",
        ]


class CoursePerformanceSerializer(serializers.Serializer):
    course = serializers.CharField()
    quiz_average = serializers.FloatField()
    quizzes_attempted = serializers.IntegerField()
    total_quizzes = serializers.IntegerField()
    projects_completed = serializers.IntegerField()
    total_projects = serializers.IntegerField()
    overall_completion = serializers.FloatField()
    quizzes = CoursePerformanceQuizSerializer(many=True)


# Certificate Serializers
class CertificateSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    verification_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            "id",
            "certificate_id",
            "user",
            "user_name",
            "course",
            "course_title",
            "full_name",
            "email",
            "issue_date",
            "completion_date",
            "final_grade",
            "completion_percentage",
            "pdf_file",
            "verification_url",
        ]
        read_only_fields = [
            "certificate_id",
            "issue_date",
            "completion_date",
            "final_grade",
            "completion_percentage",
        ]

    def get_verification_url(self, obj):
        return f"/verify/certificate/{obj.certificate_id}/"


class CertificateRequestSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = CertificateRequest
        fields = [
            "id",
            "user",
            "user_name",
            "course",
            "course_title",
            "full_name",
            "email",
            "status",
            "created_at",
            "processed_at",
            "error_message",
        ]
        read_only_fields = [
            "user",
            "status",
            "created_at",
            "processed_at",
            "error_message",
        ]


class CertificateGenerateSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()

    def validate_course_id(self, value):
        if not Course.objects.filter(id=value).exists():
            raise serializers.ValidationError("Course not found.")
        return value


# Points and Rewards Serializers
class UserPointsSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = UserPoints
        fields = [
            "id",
            "user",
            "user_name",
            "total_points",
            "available_points",
            "redeemed_points",
            "last_updated",
        ]
        read_only_fields = [
            "user",
            "total_points",
            "available_points",
            "redeemed_points",
            "last_updated",
        ]


class PointTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PointTransaction
        fields = [
            "id",
            "points",
            "transaction_type",
            "reason",
            "balance_after",
            "created_at",
        ]
        read_only_fields = ["balance_after", "created_at"]


class RewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reward
        fields = [
            "id",
            "name",
            "description",
            "reward_type",
            "points_required",
            "cash_value",
            "is_active",
            "quantity_available",
            "created_at",
        ]


class RewardRedemptionSerializer(serializers.ModelSerializer):
    reward_name = serializers.CharField(source="reward.name", read_only=True)
    reward_type = serializers.CharField(source="reward.reward_type", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = RewardRedemption
        fields = [
            "id",
            "user",
            "user_name",
            "reward",
            "reward_name",
            "reward_type",
            "points_used",
            "status",
            "redemption_code",
            "requested_at",
            "processed_at",
            "notes",
            "payout_method",
            "payout_details",
        ]
        read_only_fields = [
            "user",
            "points_used",
            "redemption_code",
            "requested_at",
            "processed_at",
        ]


class RewardRedemptionCreateSerializer(serializers.ModelSerializer):
    payout_method = serializers.CharField(required=False, allow_blank=True)
    payout_details = serializers.JSONField(required=False)

    class Meta:
        model = RewardRedemption
        fields = ["reward", "payout_method", "payout_details"]

    def validate(self, data):
        user = self.context["request"].user
        reward = data["reward"]

        # Check if user has enough points
        user_points = UserPoints.objects.get(user=user)
        if user_points.available_points < reward.points_required:
            raise serializers.ValidationError("Insufficient points for this reward.")

        # Check if reward is available
        if not reward.is_active:
            raise serializers.ValidationError("This reward is no longer available.")

        # Check quantity if limited
        if reward.quantity_available is not None:
            redeemed_count = RewardRedemption.objects.filter(
                reward=reward, status__in=["pending", "processing", "completed"]
            ).count()
            if redeemed_count >= reward.quantity_available:
                raise serializers.ValidationError("This reward is out of stock.")

        # Validate payout details for cash rewards
        if reward.reward_type == "cash" and not data.get("payout_method"):
            raise serializers.ValidationError(
                "Payout method is required for cash rewards."
            )

        return data


class CompletedCourseSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    course_title = serializers.CharField()
    completed_at = serializers.DateTimeField()
    completion_percentage = serializers.FloatField()
    is_eligible_for_certificate = serializers.BooleanField()
