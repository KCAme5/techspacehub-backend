from django.db import models
from django.conf import settings
from courses.models import Week, Enrollment
from django.utils import timezone
from datetime import timedelta
from accounts.models import Subscription
import logging

logger = logging.getLogger(__name__)

User = settings.AUTH_USER_MODEL


class Payment(models.Model):
    METHOD_CHOICES = [
        ("mpesa_stk", "M-Pesa STK Push (Lipana)"),
        ("mpesa", "M-Pesa (Legacy STK)"),
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
    method = models.CharField(max_length=15, choices=METHOD_CHOICES)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    mpesa_receipt = models.CharField(max_length=255, blank=True, null=True)
    admin_notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user} - {self.week} ({self.method}) [{self.status}]"

    def save(self, *args, **kwargs):
        # Check if status is being changed to 'success'
        if self.pk:
            try:
                old_status = Payment.objects.get(pk=self.pk).status
                if old_status != "success" and self.status == "success":
                    self.activate_subscription_and_enrollment()
            except Payment.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # For new payments that are immediately successful
        if not self.pk and self.status == "success":
            self.activate_subscription_and_enrollment()

    def activate_subscription_and_enrollment(self):
        """Activate subscription and enrollment when payment is successful"""
        try:
            logger.info(
                f"Activating subscription and enrollment for payment: {self.id}"
            )

            # 1. Create or update enrollment
            enrollment, created = Enrollment.objects.get_or_create(
                user=self.user,
                week=self.week,  # Make sure this matches your field name
                defaults={"plan": self.plan, "is_active": True},
            )

            if not created:
                # Update existing enrollment
                enrollment.plan = self.plan
                enrollment.is_active = True
                enrollment.save()
                logger.info(f"Updated existing enrollment: {enrollment.id}")
            else:
                logger.info(f"Created new enrollment: {enrollment.id}")

            # 2. Activate user subscription with LIFETIME ACCESS
            subscription, sub_created = Subscription.objects.get_or_create(
                user=self.user,
                defaults={
                    "plan": self.plan,
                    "is_active": True,
                },
            )

            if not sub_created:
                # Update existing subscription
                subscription.plan = self.plan
                subscription.is_active = True
                subscription.start_date = timezone.now()
                subscription.expiry_date = None  # No expiry for lifetime
                subscription.save()
                logger.info(f"Updated existing subscription: {subscription.id}")
            else:
                logger.info(f"Created new subscription: {subscription.id}")

            # 3. Process referral commission
            from accounts.views import process_referral_commission

            commission_result = process_referral_commission(self.user, self.amount)
            if commission_result:
                logger.info(f"Referral commission processed for payment: {self.id}")

            logger.info(
                f"SUCCESS: Subscription activated for manual payment: {self.id}"
            )

        except Exception as e:
            logger.error(
                f"ERROR activating subscription for manual payment {self.id}: {str(e)}",
                exc_info=True,
            )
