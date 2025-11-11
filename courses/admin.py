from django.contrib import admin
from django.utils.html import format_html
from datetime import timezone
from .models import (
    Category,
    Course,
    Week,
    Lesson,
    WeeklyQuiz,
    WeeklyProject,
    QuizQuestion,
    QuestionChoice,
    WeeklyQuizSubmission,
    ProjectSubmission,
    Enrollment,
    Progress,
    WeeklyProgress,
    Plan,
    StudentAnswer,
    ProjectFeedback,
    Notification,
    Certificate,
    CertificateRequest,
    UserPoints,
    PointTransaction,
    Reward,
    RewardRedemption,
)


class WeekInline(admin.TabularInline):
    model = Week
    extra = 0
    fields = ["level", "week_number", "title", "price", "is_free", "order"]
    ordering = ["level", "week_number"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "description"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "slug",
        "category",
        "instructor",
        "is_active",
        "created_at",
    ]
    list_filter = ["category", "is_active", "created_at"]
    search_fields = ["title", "description"]
    prepopulated_fields = {"slug": ["title"]}
    inlines = [WeekInline]


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ["title", "order", "duration", "is_preview"]
    ordering = ["order"]


@admin.register(Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = [
        "course",
        "level",
        "week_number",
        "title",
        "price",
        "is_free",
        "order",
    ]
    list_filter = ["course", "level", "is_free"]
    search_fields = ["title", "description"]
    ordering = ["course", "level", "week_number"]
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ["week", "title", "order", "duration", "is_preview"]
    list_filter = ["week__course", "week__level", "is_preview"]
    search_fields = ["title", "content"]
    ordering = ["week", "order"]


class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    extra = 1
    fields = ["question_text", "question_type", "points", "order"]
    ordering = ["order"]


@admin.register(WeeklyQuiz)
class WeeklyQuizAdmin(admin.ModelAdmin):
    list_display = [
        "week",
        "title",
        "time_limit",
        "passing_score",
        "total_questions",
        "is_active",
    ]
    list_filter = ["is_active", "week__course"]
    search_fields = ["title", "description"]
    inlines = [QuizQuestionInline]


@admin.register(WeeklyProject)
class WeeklyProjectAdmin(admin.ModelAdmin):
    list_display = ["week", "title", "difficulty", "estimated_hours", "is_active"]
    list_filter = ["difficulty", "is_active", "week__course"]
    search_fields = ["title", "description"]


class QuestionChoiceInline(admin.TabularInline):
    model = QuestionChoice
    extra = 4
    fields = ["choice_text", "is_correct", "order"]
    ordering = ["order"]


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = [
        "weekly_quiz",
        "question_type",
        "points",
        "order",
        "get_question_preview",
    ]
    list_filter = ["question_type", "weekly_quiz__week__course"]
    search_fields = ["question_text"]
    ordering = ["weekly_quiz", "order"]
    inlines = [QuestionChoiceInline]

    def get_question_preview(self, obj):
        return (
            obj.question_text[:50] + "..."
            if len(obj.question_text) > 50
            else obj.question_text
        )

    get_question_preview.short_description = "Question Preview"


@admin.register(QuestionChoice)
class QuestionChoiceAdmin(admin.ModelAdmin):
    list_display = ["question", "choice_text", "is_correct", "order"]
    list_filter = ["is_correct", "question__weekly_quiz"]
    search_fields = ["choice_text", "question__question_text"]
    ordering = ["question", "order"]


class StudentAnswerInline(admin.TabularInline):
    model = StudentAnswer
    extra = 0
    readonly_fields = ["question", "answer_text", "is_correct", "points_earned"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class ProjectFeedbackInline(admin.TabularInline):
    model = ProjectFeedback
    extra = 0
    readonly_fields = ["instructor", "created_at"]
    fields = ["instructor", "feedback", "status", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(WeeklyQuizSubmission)
class WeeklyQuizSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "weekly_quiz",
        "score",
        "passed",
        "time_taken",
        "submitted_at",
    ]
    list_filter = ["passed", "submitted_at", "weekly_quiz__week__course"]
    search_fields = ["student__username", "weekly_quiz__title"]
    readonly_fields = ["submitted_at"]
    inlines = [StudentAnswerInline]


@admin.register(ProjectSubmission)
class ProjectSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "weekly_project",
        "status",
        "score",
        "submitted_at",
        "has_feedback",
    ]
    list_filter = ["status", "submitted_at", "weekly_project__week__course"]
    search_fields = ["student__username", "weekly_project__title", "description"]
    readonly_fields = ["submitted_at", "reviewed_at"]
    inlines = [ProjectFeedbackInline]
    actions = ["approve_submissions", "reject_submissions", "request_revisions"]

    def has_feedback(self, obj):
        return obj.feedbacks.exists()

    has_feedback.boolean = True
    has_feedback.short_description = "Has Feedback"

    def approve_submissions(self, request, queryset):
        for submission in queryset:
            # Create feedback
            ProjectFeedback.objects.create(
                submission=submission,
                instructor=request.user,
                feedback="Your project has been approved! Great work!",
                status="approved",
            )
            submission.status = "approved"
            submission.save()

            # Create notification for student
            Notification.objects.create(
                user=submission.student,
                title="Project Approved! 🎉",
                message=f"Your project '{submission.weekly_project.title}' has been approved. Great work!",
                type="success",
                related_project=submission.weekly_project,
            )

        self.message_user(request, f"{queryset.count()} projects approved.")

    approve_submissions.short_description = "Approve selected projects"

    def reject_submissions(self, request, queryset):
        for submission in queryset:
            ProjectFeedback.objects.create(
                submission=submission,
                instructor=request.user,
                feedback="Your project needs significant improvements. Please review the requirements and resubmit.",
                status="rejected",
            )
            submission.status = "rejected"
            submission.save()

            Notification.objects.create(
                user=submission.student,
                title="Project Needs Improvements",
                message=f"Your project '{submission.weekly_project.title}' needs revisions. Please check the feedback.",
                type="warning",
                related_project=submission.weekly_project,
            )

        self.message_user(request, f"{queryset.count()} projects rejected.")

    reject_submissions.short_description = "Reject selected projects"

    def request_revisions(self, request, queryset):
        for submission in queryset:
            ProjectFeedback.objects.create(
                submission=submission,
                instructor=request.user,
                feedback="Your project is good but needs some minor improvements. Please make the requested changes.",
                status="needs_improvement",
            )
            submission.status = "needs_improvement"
            submission.save()

            Notification.objects.create(
                user=submission.student,
                title="Project Revisions Requested",
                message=f"Your project '{submission.weekly_project.title}' needs minor revisions. Please check the feedback.",
                type="info",
                related_project=submission.weekly_project,
            )

        self.message_user(request, f"{queryset.count()} projects marked for revisions.")

    request_revisions.short_description = "Request revisions for selected projects"


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "week",
        "plan",
        "enrolled_at",
        "completed",
        "progress",
        "is_active",
    ]
    list_filter = ["plan", "completed", "is_active", "enrolled_at"]
    search_fields = ["user__username", "week__title"]
    readonly_fields = ["enrolled_at"]


@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "lesson", "completed_at", "last_viewed_at"]
    list_filter = ["completed_at", "lesson__week__course"]
    search_fields = ["user__username", "lesson__title"]
    readonly_fields = ["last_viewed_at"]


@admin.register(WeeklyProgress)
class WeeklyProgressAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "week",
        "lessons_completed",
        "total_lessons",
        "completion_percentage",
        "quiz_completed",
        "project_completed",
        "week_completed",
    ]
    list_filter = [
        "week_completed",
        "quiz_completed",
        "project_completed",
        "week__course",
    ]
    search_fields = ["user__username", "week__title"]
    readonly_fields = ["completion_percentage"]

    def completion_percentage(self, obj):
        return f"{obj.completion_percentage:.1f}%"

    completion_percentage.short_description = "Completion %"


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "price",
        "unlocked_lessons_count",
        "can_access_quizzes",
        "can_access_projects",
        "can_access_certificates",
        "can_access_live_classes",
    ]
    list_filter = ["name"]
    search_fields = ["name", "description"]


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ["submission", "question", "is_correct", "points_earned"]
    list_filter = ["is_correct", "submission__weekly_quiz"]
    search_fields = ["submission__student__username", "question__question_text"]
    readonly_fields = ["submission", "question"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ProjectFeedback)
class ProjectFeedbackAdmin(admin.ModelAdmin):
    list_display = [
        "submission",
        "instructor",
        "status",
        "created_at",
        "get_feedback_preview",
    ]
    list_filter = ["status", "created_at", "submission__weekly_project"]
    search_fields = [
        "feedback",
        "submission__student__username",
        "submission__weekly_project__title",
    ]
    readonly_fields = ["created_at"]

    def get_feedback_preview(self, obj):
        return obj.feedback[:100] + "..." if len(obj.feedback) > 100 else obj.feedback

    get_feedback_preview.short_description = "Feedback Preview"

    def save_model(self, request, obj, form, change):
        if not obj.instructor_id:
            obj.instructor = request.user
        super().save_model(request, obj, form, change)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "title",
        "type",
        "is_read",
        "created_at",
        "get_message_preview",
    ]
    list_filter = ["type", "is_read", "created_at", "related_project"]
    search_fields = ["title", "message", "user__username"]
    readonly_fields = ["created_at"]
    actions = ["mark_as_read", "mark_as_unread"]

    def get_message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message

    get_message_preview.short_description = "Message Preview"

    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"{updated} notifications marked as read.")

    mark_as_read.short_description = "Mark selected notifications as read"

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f"{updated} notifications marked as unread.")

    mark_as_unread.short_description = "Mark selected notifications as unread"


# Certificate Admin Classes
@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = [
        "certificate_id",
        "user",
        "course",
        "full_name",
        "issue_date",
        "final_grade",
        "completion_percentage",
        "has_pdf",
    ]
    list_filter = ["issue_date", "course", "user"]
    search_fields = [
        "certificate_id",
        "user__username",
        "course__title",
        "full_name",
        "email",
    ]
    readonly_fields = ["certificate_id", "issue_date", "completion_date"]
    date_hierarchy = "issue_date"

    def has_pdf(self, obj):
        return bool(obj.pdf_file)

    has_pdf.boolean = True
    has_pdf.short_description = "PDF Generated"


@admin.register(CertificateRequest)
class CertificateRequestAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "course",
        "full_name",
        "status",
        "created_at",
        "processed_at",
    ]
    list_filter = ["status", "created_at", "course"]
    search_fields = [
        "user__username",
        "course__title",
        "full_name",
        "email",
    ]
    readonly_fields = ["created_at"]
    actions = ["mark_as_completed", "mark_as_failed"]

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status="completed", processed_at=timezone.now())
        self.message_user(
            request, f"{updated} certificate requests marked as completed."
        )

    mark_as_completed.short_description = "Mark selected as completed"

    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status="failed", processed_at=timezone.now())
        self.message_user(request, f"{updated} certificate requests marked as failed.")

    mark_as_failed.short_description = "Mark selected as failed"


# Points and Rewards Admin Classes
@admin.register(UserPoints)
class UserPointsAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "total_points",
        "available_points",
        "redeemed_points",
        "last_updated",
    ]
    list_filter = ["last_updated"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["last_updated"]
    ordering = ["-available_points"]


class PointTransactionInline(admin.TabularInline):
    model = PointTransaction
    extra = 0
    readonly_fields = [
        "transaction_type",
        "points",
        "reason",
        "balance_after",
        "created_at",
    ]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PointTransaction)
class PointTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "points",
        "transaction_type",
        "reason",
        "balance_after",
        "created_at",
    ]
    list_filter = ["transaction_type", "created_at"]
    search_fields = ["user__username", "reason"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "reward_type",
        "points_required",
        "cash_value",
        "is_active",
        "quantity_available",
        "redemption_count",
    ]
    list_filter = ["reward_type", "is_active"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["activate_rewards", "deactivate_rewards"]

    def redemption_count(self, obj):
        return obj.redemptions.count()

    redemption_count.short_description = "Times Redeemed"

    def activate_rewards(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} rewards activated.")

    activate_rewards.short_description = "Activate selected rewards"

    def deactivate_rewards(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} rewards deactivated.")

    deactivate_rewards.short_description = "Deactivate selected rewards"


@admin.register(RewardRedemption)
class RewardRedemptionAdmin(admin.ModelAdmin):
    list_display = [
        "redemption_code",
        "user",
        "reward",
        "points_used",
        "status",
        "requested_at",
        "processed_at",
    ]
    list_filter = ["status", "requested_at", "reward__reward_type"]
    search_fields = [
        "user__username",
        "reward__name",
        "redemption_code",
    ]
    readonly_fields = ["redemption_code", "requested_at"]
    actions = [
        "mark_as_processing",
        "mark_as_completed",
        "mark_as_cancelled",
        "mark_as_failed",
    ]

    def mark_as_processing(self, request, queryset):
        updated = queryset.update(status="processing")
        self.message_user(request, f"{updated} redemptions marked as processing.")

    mark_as_processing.short_description = "Mark selected as processing"

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status="completed", processed_at=timezone.now())
        self.message_user(request, f"{updated} redemptions marked as completed.")

    mark_as_completed.short_description = "Mark selected as completed"

    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status="cancelled")
        self.message_user(request, f"{updated} redemptions marked as cancelled.")

    mark_as_cancelled.short_description = "Mark selected as cancelled"

    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status="failed")
        self.message_user(request, f"{updated} redemptions marked as failed.")

    mark_as_failed.short_description = "Mark selected as failed"


# Customize admin site header and title
admin.site.site_header = "Course Platform Administration"
admin.site.site_title = "Course Platform Admin"
admin.site.index_title = "Welcome to Course Platform Administration"
