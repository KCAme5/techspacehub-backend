#courses/models.py
from django.db import models
from django.utils.text import slugify
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils import timezone
import uuid


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

    DOMAIN_CHOICES = [
        ('cybersecurity', 'Cybersecurity'),
        ('programming',   'Programming'),
        ('ai_ml',         'AI & Machine Learning'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    thumbnail = models.URLField(blank=True)
    # Domain determines which lab environment learners see
    domain = models.CharField(
        max_length=20, choices=DOMAIN_CHOICES, default='cybersecurity',
        help_text='Determines the lab environment for all lessons in this course'
    )
    icon = models.CharField(max_length=10, default='💻')
    color = models.CharField(max_length=10, default='#e63946')
    is_published = models.BooleanField(default=False)
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
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_courses'
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
        return f"[{self.domain}] {self.title}"


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
    LAB_TYPE_CHOICES = [
        ("none", "None"),
        ("ide", "IDE (Code Editor)"),
        ("terminal", "Terminal (Linux/Kali)"),
        ("wasm", "WebAssembly (Browser Execution)"),
    ]

    LESSON_TYPE_CHOICES = [
        ('drill',   'Terminal/Code Drill'),
        ('reading', 'Reading + Theory'),
        ('video',   'Video'),
        ('lab',     'Full Lab'),
    ]

    week = models.ForeignKey(Week, on_delete=models.CASCADE, related_name="lessons", null=True, blank=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(blank=True)

    content = models.TextField(blank=True)
    video_url = models.URLField(blank=True)
    pdf_url = models.URLField(blank=True)
    code_sniplet = models.TextField(blank=True)
    duration = models.IntegerField(help_text="Lesson duration in minutes", default=0)
    order = models.PositiveIntegerField(default=0)
    is_preview = models.BooleanField(default=False)

    # Legacy lab fields
    lab_type = models.CharField(max_length=20, choices=LAB_TYPE_CHOICES, default="none")
    lab_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Configuration for the lab environment"
    )

    # --- Hub education-path fields ---
    # Link to a Module (optional — only set for hub lessons)
    module = models.ForeignKey(
        'courses.Module',
        on_delete=models.CASCADE,
        related_name='lessons',
        null=True, blank=True,
    )
    icon = models.CharField(max_length=10, default='📖')
    xp_reward = models.IntegerField(default=50)
    lesson_type = models.CharField(
        max_length=20, choices=LESSON_TYPE_CHOICES, default='drill'
    )
    theory_html = models.TextField(
        blank=True,
        help_text='HTML content — supports inline code highlighting'
    )
    has_lab = models.BooleanField(default=True)
    # Programming lab config
    lab_language = models.CharField(
        max_length=20, blank=True,
        choices=[
            ('python','Python'), ('javascript','JavaScript'),
            ('java','Java'), ('c','C'), ('cpp','C++'),
        ],
        help_text='Only used when course domain is programming'
    )
    starter_code = models.TextField(blank=True, help_text='Starter code shown in editor')
    # Jupyter lab config
    notebook_filename = models.CharField(
        max_length=200, blank=True,
        help_text='Filename of .ipynb in JupyterLite content dir. Only for ai_ml courses.'
    )
    # Terminal lab config
    terminal_commands = models.JSONField(
        default=dict, blank=True,
        help_text='Extra command:response pairs for the terminal simulation in this lesson'
    )
    is_published = models.BooleanField(default=False)

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


class Certificate(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="certificates"
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="certificates"
    )
    certificate_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    issue_date = models.DateTimeField(auto_now_add=True)
    pdf_file = models.FileField(upload_to="certificates/", null=True, blank=True)

    # Auto-calculated fields
    completion_date = models.DateTimeField(null=True, blank=True)
    final_grade = models.FloatField(null=True, blank=True)
    completion_percentage = models.FloatField(default=0)

    class Meta:
        unique_together = ["user", "course"]
        ordering = ["-issue_date"]

    def __str__(self):
        return f"Certificate for {self.full_name} - {self.course.title}"

    @property
    def is_completed(self):
        """Check if the course is completed for certificate generation"""
        try:
            weekly_progress = WeeklyProgress.objects.filter(
                user=self.user, week__course=self.course
            )

            if not weekly_progress.exists():
                return False

            total_weeks = Week.objects.filter(course=self.course).count()
            completed_weeks = weekly_progress.filter(week_completed=True).count()

            return completed_weeks == total_weeks
        except Exception:
            return False

    def calculate_final_grade(self):
        """Calculate final grade based on quizzes and projects"""
        try:
            quiz_submissions = WeeklyQuizSubmission.objects.filter(
                student=self.user, weekly_quiz__week__course=self.course
            )

            project_submissions = ProjectSubmission.objects.filter(
                student=self.user,
                weekly_project__week__course=self.course,
                status="approved",
            )

            quiz_scores = [sub.score for sub in quiz_submissions]
            project_scores = [sub.score for sub in project_submissions if sub.score]

            quiz_avg = sum(quiz_scores) / len(quiz_scores) if quiz_scores else 0
            project_avg = (
                sum(project_scores) / len(project_scores) if project_scores else 0
            )

            if quiz_scores and project_scores:
                final_grade = (quiz_avg * 0.6) + (project_avg * 0.4)
            elif quiz_scores:
                final_grade = quiz_avg
            elif project_scores:
                final_grade = project_avg
            else:
                final_grade = 0

            return round(final_grade, 2)
        except Exception:
            return None


class CertificateRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certificate_requests",
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="certificate_requests"
    )
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Certificate Request - {self.user.username} - {self.course.title}"


# Points and Rewards System
class UserPoints(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="points"
    )
    total_points = models.PositiveIntegerField(default=0)
    available_points = models.PositiveIntegerField(default=0)
    redeemed_points = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "User points"

    def __str__(self):
        return f"{self.user.username} - {self.available_points} points"

    def add_points(self, points, reason=""):
        """Add points to user balance"""
        self.total_points += points
        self.available_points += points
        self.save()

        # Create transaction record
        PointTransaction.objects.create(
            user=self.user,
            points=points,
            transaction_type="earn",
            reason=reason,
            balance_after=self.available_points,
        )

    def redeem_points(self, points, reason=""):
        """Redeem points from user balance"""
        if points > self.available_points:
            raise ValueError("Insufficient points")

        self.available_points -= points
        self.redeemed_points += points
        self.save()

        # Create transaction record
        PointTransaction.objects.create(
            user=self.user,
            points=-points,
            transaction_type="redeem",
            reason=reason,
            balance_after=self.available_points,
        )


class PointTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("earn", "Earned"),
        ("redeem", "Redeemed"),
        ("bonus", "Bonus"),
        ("penalty", "Penalty"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="point_transactions",
    )
    points = models.IntegerField()  # Positive for earn, negative for redeem
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    reason = models.CharField(max_length=255)
    balance_after = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Reference to related object (optional)
    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.SET_NULL, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        sign = "+" if self.points > 0 else ""
        return f"{self.user.username} - {sign}{self.points} points - {self.reason}"


class Reward(models.Model):
    REWARD_TYPES = [
        ("cash", "Cash"),
        ("voucher", "Gift Voucher"),
        ("course", "Free Course"),
        ("badge", "Badge"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField()
    reward_type = models.CharField(max_length=20, choices=REWARD_TYPES)
    points_required = models.PositiveIntegerField()
    cash_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cash value in USD",
    )
    is_active = models.BooleanField(default=True)
    quantity_available = models.PositiveIntegerField(
        null=True, blank=True, help_text="Null means unlimited"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["points_required"]

    def __str__(self):
        return f"{self.name} - {self.points_required} points"


class RewardRedemption(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reward_redemptions",
    )
    reward = models.ForeignKey(
        Reward, on_delete=models.CASCADE, related_name="redemptions"
    )
    points_used = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    redemption_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    # For cash rewards
    payout_method = models.CharField(
        max_length=100, blank=True, help_text="PayPal, Bank Transfer, etc."
    )
    payout_details = models.JSONField(
        null=True, blank=True, help_text="Payment account details"
    )

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.user.username} - {self.reward.name} - {self.status}"

    def save(self, *args, **kwargs):
        if self.status == "completed" and not self.processed_at:
            self.processed_at = timezone.now()
        super().save(*args, **kwargs)


# ============================================================
#  HUB EDUCATION PATH MODELS
#  Course → Level → Module → Lesson → Drill / Quiz
# ============================================================

class Level(models.Model):
    LEVEL_TYPE_CHOICES = [
        ('beginner',     'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced',     'Advanced'),
        ('expert',       'Expert'),
    ]
    course      = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='levels')
    name        = models.CharField(max_length=100)
    slug        = models.SlugField()
    level_type  = models.CharField(max_length=20, choices=LEVEL_TYPE_CHOICES)
    description = models.TextField()
    order       = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']
        unique_together = ['course', 'slug']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.course.title} — {self.name}"


class Module(models.Model):
    level       = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='modules')
    title       = models.CharField(max_length=200)
    description = models.TextField()
    order       = models.PositiveIntegerField(default=0)
    icon        = models.CharField(max_length=10, default='📦')
    color       = models.CharField(max_length=10, default='#48cae4')
    xp_reward   = models.IntegerField(default=50)
    is_published = models.BooleanField(default=False)
    # Pricing — staff sets per module
    # FREE RULE: module.order <= 2
    # PAID RULE: module.order > 2 → requires UserModuleAccess
    single_module_price = models.DecimalField(max_digits=8, decimal_places=2, default=299.00)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.level} — {self.title}"


class Drill(models.Model):
    """A terminal/code drill task within a hub Lesson."""
    lesson  = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='drills')
    order   = models.PositiveIntegerField(default=0)
    prompt  = models.CharField(max_length=100, default='$')
    task    = models.TextField()
    hint    = models.TextField()

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Drill {self.order}: {self.task[:50]}"


class DrillAnswer(models.Model):
    """Accepted answers for a Drill — never exposed to learner API."""
    drill             = models.ForeignKey(Drill, on_delete=models.CASCADE, related_name='answers')
    answer            = models.CharField(max_length=500)
    is_case_sensitive = models.BooleanField(default=False)

    def __str__(self):
        return f"Answer for Drill {self.drill_id}: {self.answer[:40]}"


class Quiz(models.Model):
    """A single-question quiz attached to a hub Lesson (one per lesson)."""
    lesson      = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='quiz')
    question    = models.TextField()
    explanation = models.TextField()

    def __str__(self):
        return f"Quiz for: {self.lesson.title}"


class QuizOption(models.Model):
    """Answer options for a Quiz (A/B/C/D)."""
    quiz       = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='options')
    label      = models.CharField(max_length=1)   # A, B, C, D
    text       = models.TextField()
    is_correct = models.BooleanField(default=False)
    order      = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.label}: {self.text[:40]}"
