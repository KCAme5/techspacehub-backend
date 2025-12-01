#accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import uuid
from datetime import timedelta
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from courses.models import Enrollment


class User(AbstractUser):
    ROLE_CHOICES = (
        ("staff", "staff"),
        ("student", "student"),
        ("management", "management"),
    )

    PLAN_CHOICES = (
        ("FREE", "Free Plan"),
        ("BASIC", "Basic Plan"),
        ("PRO", "Pro Plan"),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="student")
    subscription_status = models.CharField(max_length=20, default="inactive")
    subscription_plan = models.CharField(
        max_length=20, choices=PLAN_CHOICES, default="FREE"
    )

    email = models.EmailField(unique=True)

    my_referral_code = models.CharField(
        max_length=50, unique=True, blank=True, null=True
    )
    referred_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users_referred",
    )

    # Security fields (lockout / failed attempts)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.my_referral_code:
            self.my_referral_code = str(uuid.uuid4())[:8]
        super().save(*args, **kwargs)

    def is_locked(self):
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False

    def reset_login_attempts(self):
        self.failed_login_attempts = 0
        self.last_failed_login = None
        self.locked_until = None
        self.save(
            update_fields=["failed_login_attempts", "last_failed_login", "locked_until"]
        )

    def has_lifetime_access(self, week):
        try:
            enrollment = self.enrollments.get(week=week)
            return enrollment.is_lifetime_access
        except Enrollment.DoesNotExist:
            return False

    def get_active_enrollments(self):
        return self.enrollments.filter(is_active=True)

    def __str__(self):
        return f"{self.username} ({self.role}) - {self.subscription_plan}"


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    referral_code = models.CharField(max_length=50, unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = str(uuid.uuid4())[:8]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} Profile"


class Subscription(models.Model):
    PLAN_CHOICES = (
        ("FREE", "Free Plan"),
        ("BASIC", "Basic Plan"),
        ("PRO", "Pro Plan"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="subscription",
        on_delete=models.CASCADE,
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="FREE")
    start_date = models.DateTimeField(auto_now_add=True, null=True)
    expiry_date = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.expiry_date and self.is_active:
            self.expiry_date = timezone.now() + timedelta(days=365 * 50)

        super().save(*args, **kwargs)

        if self.user:
            self.user.subscription_plan = self.plan
            self.user.subscription_status = "active" if self.is_active else "inactive"
            self.user.save(update_fields=["subscription_plan", "subscription_status"])

    def renew(self, duration_days=30):
        self.start_date = timezone.now()
        # self.expiry_date = self.start_date + timedelta(days=duration_days)
        self.is_active = True
        self.save()

    def deactivate(self):
        self.is_active = False
        self.save()

    def __str__(self):
        return f"{self.user.username} - {self.plan} ({'Active' if self.is_active else 'Inactive'})"


class LoginAttempt(models.Model):
    """
    Audit log for login attempts (successful or failed). Keep minimal PII.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    email = models.EmailField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"LoginAttempt(email={self.email}, success={self.success}, time={self.timestamp})"


# Add to accounts/models.py
class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet"
    )
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Wallet - ${self.balance}"


class Referral(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("paid", "Paid"),
    )

    referrer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="referrals_made"
    )
    referred_user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="referral_received"
    )
    referral_code_used = models.CharField(max_length=50)
    referral_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    commission_earned = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    commission_paid = models.BooleanField(default=False)

    class Meta:
        unique_together = ["referrer", "referred_user"]

    def __str__(self):
        return f"{self.referrer.username} -> {self.referred_user.username}"


class WalletTransaction(models.Model):
    TRANSACTION_TYPES = (
        ("referral", "Referral Commission"),
        ("withdrawal", "Withdrawal"),
        ("bonus", "Bonus"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="transactions"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    # For withdrawals
    withdrawal_method = models.CharField(max_length=50, blank=True, null=True)
    withdrawal_details = models.JSONField(
        blank=True, null=True
    )  # For M-Pesa phone, PayPal email,

    def __str__(self):
        return f"{self.wallet.user.username} - {self.transaction_type} - ${self.amount}"


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("rejected", "Rejected"),
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="withdrawal_requests"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=50)  # mpesa, paypal, etc.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    account_details = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - ${self.amount} - {self.status}"


@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.create(user=instance)
