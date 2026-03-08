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
        ("client", "client"),
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

    # ─── Hub gamification fields ──────────────────────────────────────────
    total_xp    = models.IntegerField(default=0)
    streak_days = models.IntegerField(default=1)
    rank        = models.CharField(max_length=50, default='NEWBIE')

    RANKS = [
        (0,    'NEWBIE'),
        (100,  'SCRIPT KIDDIE'),
        (300,  'APPRENTICE'),
        (600,  'HACKER'),
        (1000, 'PRO HACKER'),
        (1500, 'ELITE'),
        (2500, 'LEGEND'),
        (4000, 'GHOST'),
    ]

    def update_rank(self):
        """Recalculate and save rank based on total_xp."""
        for threshold, name in reversed(self.RANKS):
            if self.total_xp >= threshold:
                self.rank = name
                break
        self.save(update_fields=['rank', 'total_xp'])

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
    failure_reason = models.TextField(null=True, blank=True)  # Changed to TextField for full error logging

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),  # Performance optimization
        ]

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


class ActivityLog(models.Model):
    """
    Comprehensive audit log for all platform activities.
    Tracks user actions, system events, and security-related activities.
    """
    
    ACTION_CHOICES = [
        # Authentication
        ("login_success", "Login Success"),
        ("login_failed", "Login Failed"),
        ("logout", "Logout"),
        ("register", "Registration"),
        ("password_change", "Password Change"),
        ("password_reset", "Password Reset"),
        ("oauth_login", "OAuth Login"),
        
        # User Management
        ("user_created", "User Created"),
        ("user_updated", "User Updated"),
        ("user_deleted", "User Deleted"),
        ("user_verified", "User Verified"),
        ("user_suspended", "User Suspended"),
        
        # Course Management
        ("course_created", "Course Created"),
        ("course_updated", "Course Updated"),
        ("course_deleted", "Course Deleted"),
        ("course_published", "Course Published"),
        ("enrollment_created", "Enrollment Created"),
        
        # Financial
        ("payment_success", "Payment Success"),
        ("payment_failed", "Payment Failed"),
        ("withdrawal_requested", "Withdrawal Requested"),
        ("withdrawal_approved", "Withdrawal Approved"),
        ("withdrawal_rejected", "Withdrawal Rejected"),
        ("refund_processed", "Refund Processed"),
        
        # Content
        ("content_created", "Content Created"),
        ("content_updated", "Content Updated"),
        ("content_deleted", "Content Deleted"),
        ("quiz_submitted", "Quiz Submitted"),
        ("project_submitted", "Project Submitted"),
        
        # Security
        ("suspicious_activity", "Suspicious Activity"),
        ("rate_limit_exceeded", "Rate Limit Exceeded"),
        ("unauthorized_access", "Unauthorized Access Attempt"),
        
        # Other
        ("other", "Other"),
    ]
    
    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("critical", "Critical"),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict, blank=True)  # Flexible metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, default="info"
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["action"]),
            models.Index(fields=["severity"]),
            models.Index(fields=["user", "-timestamp"]),
        ]
    
    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        return f"{user_str} - {self.get_action_display()} ({self.timestamp})"
    
    @classmethod
    def cleanup_old_logs(cls, days=90):
        """Delete logs older than specified days (data retention policy)"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count = cls.objects.filter(timestamp__lt=cutoff_date).delete()[0]
        return deleted_count
