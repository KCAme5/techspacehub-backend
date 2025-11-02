from django.db import models
from django.conf import settings
from courses.models import Course
import uuid
from django.utils import timezone


class Resource(models.Model):
    CATEGORY_CHOICES = [
        ("python", "Python"),
        ("ethicalhacking", "Ethical Hacking"),
        ("programming", "Programming"),
        ("artificialintelligence", "Artificial Intelligence"),
        ("machinelearning", "Machine Learning"),
        ("networking", "Networking"),
        ("cybersecurity", "Cyber Security"),
        ("webdev", "Web Development"),
        ("general", "General Tech"),
    ]

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to="library/files/", blank=True, null=True)
    thumbnail = models.ImageField(
        upload_to="library/thumbnails/", blank=True, null=True
    )
    category = models.CharField(
        max_length=50, choices=CATEGORY_CHOICES, default="general"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        related_name="library_resources",
        null=True,
        blank=True,
        help_text="Course this resource belongs to (optional).",
    )
    author = models.CharField(max_length=255, blank=True, null=True)
    upload_date = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_public = models.BooleanField(
        default=False, help_text="Allow free/public access."
    )
    view_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title

    def available_for_user(self, user):
        """
        Determines whether this resource is accessible to a given user.
        Public resources are free; others depend on enrollment/subscription.
        """
        if self.is_public:
            return True

        if not self.course:
            return False

        # Example: you can later connect this to your subscription or enrollment model
        # sub = Subscription.objects.filter(
        #     user=user, course=self.course, is_active=True
        # ).first()
        # if not sub:
        #     return False
        # return sub.plan.can_access_library

        return False  # default fallback for now


class UserBookProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    book = models.ForeignKey(Resource, on_delete=models.CASCADE)
    is_open = models.BooleanField(default=False)
    last_page = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "book")

    def __str__(self):
        return f"{self.user.username} - {self.book.title}"


class ResourceViewLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(
        max_length=20,
        choices=[("viewed", "Viewed"), ("downloaded", "Downloaded")],
        default="viewed",
    )

    def __str__(self):
        return f"{self.user.username} {self.action} {self.resource.title}"


class FavoriteResource(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "resource")

    def __str__(self):
        return f"{self.user.username} ❤️ {self.resource.title}"
