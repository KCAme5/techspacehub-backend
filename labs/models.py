from django.db import models
from django.conf import settings
from django.utils import timezone
from courses.models import Course


class Lab(models.Model):
    CATEGORY_CHOICES = [
        ("ai", "Artificial Intelligence"),
        ("ml", "Machine Learning"),
        ("programming", "Programming"),
        ("cybersecurity", "Cybersecurity"),
    ]

    DIFFICULTY_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    ]

    ENVIRONMENT_CHOICES = [
        ("vscode", "VSCode Online"),
        ("python", "Python Sandbox"),
        ("linux", "Linux Terminal"),
        ("ai", "AI Notebook"),
        ("web", "Web Security Lab"),
        ("network", "Network Simulation"),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="lab_labs",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField()
    difficulty = models.CharField(
        max_length=50, choices=DIFFICULTY_CHOICES, default="beginner"
    )
    environment_type = models.CharField(
        max_length=50, choices=ENVIRONMENT_CHOICES, default="vscode"
    )
    is_free = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    duration_days = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    """def available_for_user(self, user):
        sub = Subscription.objects.filter(
            user=user, course=self.course, is_active=True
        ).first()
        if not sub:
            return False
        return sub.plan.can_access_labs
"""
