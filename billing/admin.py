"""
from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "week",
        "amount",
        "method",
        "status",
        "transaction_id",
        "created_at",
    )
    list_filter = ("status", "method", "created_at")
    search_fields = ("user__email", "week__title", "transaction_id")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    list_per_page = 20

    fieldsets = (
        (
            "Payment Details",
            {"fields": ("user", "week", "amount", "currency", "method")},
        ),
        ("Transaction Info", {"fields": ("transaction_id", "status")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
"""

from django.contrib import admin
from django.utils.html import format_html
from django.core.mail import send_mail
from django.conf import settings
from courses.models import Enrollment
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "week",
        "amount",
        "method",
        "status",
        "mpesa_receipt",
        "created_at",
        "manual_actions",
    )
    list_filter = ("status", "method", "created_at")
    search_fields = ("user__email", "week__title", "transaction_id", "mpesa_receipt")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    list_per_page = 20

    actions = ["mark_as_success", "mark_as_failed"]

    fieldsets = (
        (
            "Payment Details",
            {"fields": ("user", "week", "amount", "currency", "method", "plan")},
        ),
        ("Transaction Info", {"fields": ("transaction_id", "mpesa_receipt", "status")}),
        ("Manual Payment Info", {"fields": ("admin_notes",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def manual_actions(self, obj):
        if obj.method == "manual_mpesa" and obj.status == "pending":
            return format_html(
                '<a class="button" href="{}" style="background-color: #4CAF50; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">Approve</a>',
                f"approve/{obj.id}/",
            )
        return "-"

    manual_actions.short_description = "Actions"

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "approve/<int:payment_id>/",
                self.approve_manual_payment,
                name="billing_payment_approve",
            ),
        ]
        return custom_urls + urls

    def approve_manual_payment(self, request, payment_id):
        """Approve manual payment and enroll user"""
        try:
            payment = Payment.objects.get(id=payment_id)
            if payment.method == "manual_mpesa" and payment.status == "pending":
                # Update payment status
                payment.status = "success"
                payment.save()

                # Create or update enrollment
                enrollment, created = Enrollment.objects.get_or_create(
                    user=payment.user,
                    week=payment.week,
                    defaults={"plan": payment.plan, "is_active": True},
                )

                if not created:
                    enrollment.plan = payment.plan
                    enrollment.is_active = True
                    enrollment.save()

                # Send success email
                self.send_approval_email(payment, enrollment)

                self.message_user(
                    request,
                    f"Payment approved and user enrolled successfully! Email sent to {payment.user.email}",
                )
            else:
                self.message_user(request, "Cannot approve this payment", level="ERROR")

        except Payment.DoesNotExist:
            self.message_user(request, "Payment not found", level="ERROR")

        return admin.utils.reverse("admin:billing_payment_changelist")

    def send_approval_email(self, payment, enrollment):
        """Send email notification for approved manual payment"""
        subject = f"Payment Confirmed - Access Granted for {payment.week}"

        site_name = getattr(settings, "SITE_NAME", "TechSpace")

        frontend_url = getattr(
            settings, "FRONTEND_URL", "https://cybercraft-frontend.vercel.app"
        )

        message = f"""
        Hello {payment.user.username},

        Your manual payment for {payment.week} has been confirmed!

         **Payment Details:**
        - Course: {payment.week.course.title}
        - Week: {payment.week.title} ({payment.week.level})
        - Plan: {payment.plan}
        - Amount: KES {payment.amount}
        - Payment Method: Manual M-Pesa

        **You now have full access** to the course materials for your selected plan.

        Start learning now: {frontend_url}/dashboard

        Need help? Reply to this email or contact us on WhatsApp.

        Happy learning!
        The {site_name} Team
        """

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[payment.user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Failed to send email: {e}")

    def mark_as_success(self, request, queryset):
        """Admin action to mark payments as success"""
        for payment in queryset:
            if payment.status != "success":
                payment.status = "success"
                payment.save()

                # Auto-enroll user
                enrollment, created = Enrollment.objects.get_or_create(
                    user=payment.user,
                    week=payment.week,
                    defaults={"plan": payment.plan, "is_active": True},
                )
                if not created:
                    enrollment.plan = payment.plan
                    enrollment.is_active = True
                    enrollment.save()

                # Send email
                self.send_approval_email(payment, enrollment)

        self.message_user(request, f"{queryset.count()} payments marked as successful")

    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status="failed")
        self.message_user(request, f"{updated} payments marked as failed")

    mark_as_success.short_description = "Mark selected as SUCCESS (enroll user + email)"
    mark_as_failed.short_description = "Mark selected as FAILED"
