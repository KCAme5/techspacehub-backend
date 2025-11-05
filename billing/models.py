from django.db import models
from django.conf import settings
from courses.models import Week  # Changed from Course

User = settings.AUTH_USER_MODEL


class Payment(models.Model):
    METHOD_CHOICES = [
        ("mpesa", "M-Pesa"),
        ("stripe", "Stripe"),
        ("manual_mpesa", "Manual M-Pesa"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")
    week = models.ForeignKey(
        Week, on_delete=models.CASCADE, related_name="payments", blank=True, null=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    plan = models.CharField(max_length=10, default="BASIC")
    currency = models.CharField(max_length=10, default="KES")
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    mpesa_receipt = models.CharField(max_length=255, blank=True, null=True)
    admin_notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user} - {self.week} ({self.method}) [{self.status}]"
