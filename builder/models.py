"""
builder/models.py
Credit system for the AI Website Builder.
"""
from django.db import models
from django.conf import settings
import uuid


class UserCredits(models.Model):
    """One row per user — their AI builder credit balance."""
    user            = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_credits'
    )
    credits         = models.IntegerField(default=20)   # starts at 20 free
    total_purchased = models.IntegerField(default=0)
    total_used      = models.IntegerField(default=0)
    is_free_tier    = models.BooleanField(default=True)  # flips False after first purchase
    updated_at      = models.DateTimeField(auto_now=True)

    @property
    def is_empty(self):
        return self.credits <= 0

    @property
    def is_low(self):
        return 0 < self.credits <= 3

    def __str__(self):
        return f"{self.user.username} — {self.credits} credits"

    class Meta:
        verbose_name = "User Credits"
        verbose_name_plural = "User Credits"


class CreditPackage(models.Model):
    """Available credit packs shown in the purchase modal."""
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=50)   # e.g. "STARTER", "PRO", "POWER"
    credits     = models.IntegerField()              # credits to grant
    price_kes   = models.DecimalField(max_digits=10, decimal_places=2)  # KES
    is_popular  = models.BooleanField(default=False)  # shows "★ POPULAR" badge
    is_active   = models.BooleanField(default=True)
    sort_order  = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name} — {self.credits} credits @ KES {self.price_kes}"

    class Meta:
        ordering = ['sort_order']
        verbose_name = "Credit Package"
        verbose_name_plural = "Credit Packages"


class CreditPayment(models.Model):
    """Tracks each credit top-up attempt via M-Pesa."""
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('completed', 'Completed'),
        ('failed',    'Failed'),
    ]

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user                = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='credit_payments'
    )
    package             = models.ForeignKey(CreditPackage, on_delete=models.SET_NULL, null=True)
    amount              = models.DecimalField(max_digits=10, decimal_places=2)  # KES
    credits             = models.IntegerField()   # credits being purchased
    phone_number        = models.CharField(max_length=20, blank=True)
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    mpesa_checkout_id   = models.CharField(max_length=200, blank=True)
    mpesa_receipt       = models.CharField(max_length=100, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    completed_at        = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} — {self.credits} credits [{self.status}]"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Credit Payment"
        verbose_name_plural = "Credit Payments"
