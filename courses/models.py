from django.db import models
from django.utils.text import slugify
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Course(models.Model):
    LEVEL_CHOICES = (
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    )

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    thumbnail = models.URLField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="courses",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="taught_courses",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Week(models.Model):
    LEVEL_CHOICES = (
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    )

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="weeks")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    week_number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_free = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["level", "week_number"]
        unique_together = ["course", "level", "week_number"]

    def __str__(self):
        return f"{self.course.title} - {self.level.title()} - Week {self.week_number}: {self.title}"


class Lesson(models.Model):
    week = models.ForeignKey(Week, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=200)
    slug = models.SlugField()
    content = models.TextField(blank=True)
    video_url = models.URLField(blank=True)
    pdf_url = models.URLField(blank=True)
    code_sniplet = models.TextField(blank=True)
    duration = models.IntegerField(help_text="Lesson duration in minutes", default=0)
    order = models.PositiveIntegerField(default=0)
    is_preview = models.BooleanField(default=False)

    class Meta:
        ordering = ["order"]
        unique_together = ["week", "slug"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.week} - {self.title}"


class WeeklyQuiz(models.Model):
    week = models.OneToOneField(
        Week, on_delete=models.CASCADE, related_name="weekly_quiz"
    )
    title = models.CharField(max_length=200, default="Weekly Quiz")
    description = models.TextField(blank=True)
    time_limit = models.PositiveIntegerField(
        default=60, help_text="Time limit in minutes for the weekly quiz"
    )
    passing_score = models.PositiveIntegerField(
        default=70, help_text="Passing score percentage"
    )
    total_questions = models.PositiveIntegerField(
        default=30, help_text="Total number of questions in the weekly quiz"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Weekly Quizzes"

    def __str__(self):
        return f"{self.week} - Weekly Quiz"


class WeeklyProject(models.Model):
    week = models.OneToOneField(
        Week, on_delete=models.CASCADE, related_name="weekly_project"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    objectives = models.TextField(help_text="Learning objectives for this project")
    requirements = models.TextField(help_text="Project requirements and deliverables")
    resources = models.TextField(
        blank=True, help_text="Recommended resources and tools"
    )
    difficulty = models.CharField(
        max_length=20,
        choices=(
            ("easy", "Easy"),
            ("medium", "Medium"),
            ("hard", "Hard"),
        ),
        default="medium",
    )
    estimated_hours = models.PositiveIntegerField(
        default=4, help_text="Estimated time to complete in hours"
    )
    submission_instructions = models.TextField(help_text="How to submit the project")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.week} - Project"


class QuizQuestion(models.Model):
    QUESTION_TYPES = [
        ("multiple_choice", "Multiple Choice"),
        ("single_choice", "Single Choice"),
        ("text", "Text Answer"),
        ("code", "Code Answer"),
    ]

    weekly_quiz = models.ForeignKey(
        WeeklyQuiz,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    points = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    explanation = models.TextField(
        blank=True, help_text="Explanation shown after answering"
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.weekly_quiz.title} - {self.question_text[:50]}"


class WeeklyQuizSubmission(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_quiz_submissions",
    )
    weekly_quiz = models.ForeignKey(
        WeeklyQuiz,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    score = models.FloatField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    time_taken = models.PositiveIntegerField(
        default=0, help_text="Time taken in seconds"
    )
    passed = models.BooleanField(default=False)
    attempt_number = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.student.username} - {self.weekly_quiz.title} - {self.score}% - Attempt {self.attempt_number}"

    def save(self, *args, **kwargs):
        if not self.pk:
            last_attempt = (
                WeeklyQuizSubmission.objects.filter(
                    student=self.student, weekly_quiz=self.weekly_quiz
                )
                .order_by("-attempt_number")
                .first()
            )

            if last_attempt:
                self.attempt_number = last_attempt.attempt_number + 1
            else:
                self.attempt_number = 1
        super().save(*args, **kwargs)


class ProjectSubmission(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("needs_revision", "Needs Revision"),
        ("rejected", "Rejected"),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_submissions",
    )
    weekly_project = models.ForeignKey(
        WeeklyProject,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    submission_url = models.URLField(
        help_text="URL to the project repository or demo",
        blank=True,
        null=True,
        max_length=500,
    )
    submission_file = models.FileField(
        upload_to="project_submissions/%Y/%m/%d/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=["zip"])],
    )
    description = models.TextField(
        help_text="Student's description of their project", blank=True, null=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_feedback = models.TextField(blank=True)
    score = models.PositiveIntegerField(
        null=True, blank=True, help_text="Score out of 100"
    )

    class Meta:
        unique_together = ["student", "weekly_project"]
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.student.username} - {self.weekly_project.title}"


class ProjectFeedback(models.Model):
    submission = models.ForeignKey(
        ProjectSubmission, on_delete=models.CASCADE, related_name="feedbacks"
    )
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="given_feedbacks",
    )
    feedback = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=(
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("needs_improvement", "Needs Improvement"),
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(
        max_length=20,
        choices=(
            ("info", "Info"),
            ("success", "Success"),
            ("warning", "Warning"),
            ("error", "Error"),
        ),
        default="info",
    )
    related_project = models.ForeignKey(
        WeeklyProject, on_delete=models.CASCADE, null=True, blank=True
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class QuestionChoice(models.Model):
    question = models.ForeignKey(
        QuizQuestion, on_delete=models.CASCADE, related_name="choices"
    )
    choice_text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.question.question_text[:30]} - {self.choice_text[:30]}"


class StudentAnswer(models.Model):
    submission = models.ForeignKey(
        WeeklyQuizSubmission, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    answer_text = models.TextField(blank=True, null=True)
    selected_choices = models.ManyToManyField(QuestionChoice, blank=True)
    is_correct = models.BooleanField(default=False)
    points_earned = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ["submission", "question"]

    def __str__(self):
        return f"{self.submission} - {self.question.question_text[:30]}"


PLAN_CHOICES = [
    ("FREE", "Free"),
    ("BASIC", "Basic"),
    ("PRO", "Pro"),
]


class Enrollment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments"
    )
    week = models.ForeignKey(Week, on_delete=models.CASCADE, related_name="enrollments")
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES, default="FREE")
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    progress = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    last_accessed = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "week"]
        ordering = ["-enrolled_at"]

    def __str__(self):
        return f"{self.user} - {self.week}"

    def save(self, *args, **kwargs):

        if self.plan in ["BASIC", "PRO"]:
            self.is_active = True
        super().save(*args, **kwargs)

    @property
    def is_lifetime_access(self):
        """Check if this enrollment has lifetime access"""
        return self.plan in ["BASIC", "PRO"] and self.is_active


class Progress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="progress"
    )
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="progress"
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    last_viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "lesson"]

    def __str__(self):
        return f"{self.user} - {self.lesson.title}"


class WeeklyProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_progress",
    )
    week = models.ForeignKey(
        Week, on_delete=models.CASCADE, related_name="weekly_progress"
    )
    lessons_completed = models.PositiveIntegerField(default=0)
    total_lessons = models.PositiveIntegerField(default=0)
    quiz_completed = models.BooleanField(default=False)
    project_completed = models.BooleanField(default=False)
    week_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["user", "week"]
        verbose_name_plural = "Weekly progress"

    def __str__(self):
        return f"{self.user} - {self.week} - Progress"

    def save(self, *args, **kwargs):
        # Auto-set total_lessons if not set
        if not self.total_lessons:
            self.total_lessons = self.week.lessons.count()

        # Auto-update completion status if all lessons are done
        if (
            self.lessons_completed == self.total_lessons
            and self.total_lessons > 0
            and self.quiz_completed
            and self.project_completed
            and not self.week_completed
        ):

            self.week_completed = True
            if not self.completed_at:
                self.completed_at = timezone.now()

        super().save(*args, **kwargs)

    @property
    def completion_percentage(self):
        if self.total_lessons == 0:
            return 0
        return (self.lessons_completed / self.total_lessons) * 100


class Plan(models.Model):
    PLAN_CHOICES = [
        ("free", "Free"),
        ("basic", "Basic"),
        ("pro", "Pro"),
    ]

    name = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration_days = models.PositiveIntegerField(default=30)

    # Access controls for lessons
    unlocked_lessons_count = models.PositiveIntegerField(
        default=2,
        help_text="Number of lessons unlocked for this plan (free plan typically unlocks first 2 lessons)",
    )

    # Additional features
    can_access_quizzes = models.BooleanField(default=False)
    can_access_projects = models.BooleanField(default=False)
    can_access_certificates = models.BooleanField(default=False)
    can_access_live_classes = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_name_display()

    def is_free_plan(self):
        return self.name == "free"
