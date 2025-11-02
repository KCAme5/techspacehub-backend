from rest_framework import serializers
from .models import (
    Category,
    Course,
    Week,
    Lesson,
    WeeklyQuiz,
    WeeklyProject,
    QuizQuestion,
    QuestionChoice,
    ProjectSubmission,
    Plan,
)


class StaffCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class StaffCourseSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(
        source="instructor.get_full_name", read_only=True
    )
    total_weeks = serializers.SerializerMethodField()
    total_students = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "slug")

    def get_total_weeks(self, obj):
        return obj.weeks.count()

    def get_total_students(self, obj):
        from django.db.models import Count

        return obj.weeks.aggregate(total_students=Count("enrollments", distinct=True))[
            "total_students"
        ]


class StaffWeekSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    total_lessons = serializers.SerializerMethodField()
    total_enrollments = serializers.SerializerMethodField()

    class Meta:
        model = Week
        fields = "__all__"

    def get_total_lessons(self, obj):
        return obj.lessons.count()

    def get_total_enrollments(self, obj):
        return obj.enrollments.count()


class StaffLessonSerializer(serializers.ModelSerializer):
    week_title = serializers.CharField(source="week.title", read_only=True)
    course_title = serializers.CharField(source="week.course.title", read_only=True)

    class Meta:
        model = Lesson
        fields = "__all__"
        read_only_fields = ("slug",)


class QuestionChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionChoice
        fields = "__all__"


class StaffQuizQuestionSerializer(serializers.ModelSerializer):
    choices = QuestionChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = QuizQuestion
        fields = "__all__"


class StaffWeeklyQuizSerializer(serializers.ModelSerializer):
    week_title = serializers.CharField(source="week.title", read_only=True)
    course_title = serializers.CharField(source="week.course.title", read_only=True)
    questions = StaffQuizQuestionSerializer(many=True, read_only=True)
    total_questions = serializers.IntegerField(source="questions.count", read_only=True)
    total_submissions = serializers.IntegerField(
        source="submissions.count", read_only=True
    )

    class Meta:
        model = WeeklyQuiz
        fields = "__all__"


class StaffWeeklyProjectSerializer(serializers.ModelSerializer):
    week_title = serializers.CharField(source="week.title", read_only=True)
    course_title = serializers.CharField(source="week.course.title", read_only=True)
    total_submissions = serializers.IntegerField(
        source="submissions.count", read_only=True
    )

    class Meta:
        model = WeeklyProject
        fields = "__all__"


class StaffPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = "__all__"


# Bulk creation serializers
class BulkWeekSerializer(serializers.Serializer):
    weeks = serializers.ListField(child=serializers.DictField(), write_only=True)


class BulkLessonSerializer(serializers.Serializer):
    lessons = serializers.ListField(child=serializers.DictField(), write_only=True)


class StaffProjectSubmissionSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source="student.username", read_only=True)
    student_email = serializers.CharField(source="student.email", read_only=True)
    project_title = serializers.CharField(source="weekly_project.title", read_only=True)
    week_title = serializers.CharField(
        source="weekly_project.week.title", read_only=True
    )
    course_title = serializers.CharField(
        source="weekly_project.week.course.title", read_only=True
    )
    week_id = serializers.IntegerField(source="weekly_project.week.id", read_only=True)
    course_id = serializers.IntegerField(
        source="weekly_project.week.course.id", read_only=True
    )

    class Meta:
        model = ProjectSubmission
        fields = [
            "id",
            "student",
            "student_username",
            "student_email",
            "weekly_project",
            "project_title",
            "week_title",
            "course_title",
            "week_id",
            "course_id",
            "submission_url",
            "submission_file",
            "description",
            "status",
            "submitted_at",
            "reviewed_at",
            "reviewer_feedback",
            "score",
        ]
        read_only_fields = ["student", "weekly_project", "submitted_at"]
