from django.contrib import admin
from django.utils.html import format_html
from django.conf import settings
from django.shortcuts import redirect
from courses.models import Enrollment
from .models import Payment

# Import our email utilities
from accounts.email_utils import (
    send_manual_payment_approval_email,
    send_payment_confirmation_email,
)


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
                '<a class="button" href="{}" style="background-color: #4CAF50; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; margin: 2px;">Approve</a>',
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
        """Approve manual payment - let the Payment model handle enrollment and subscription"""
        try:
            payment = Payment.objects.get(id=payment_id)
            if payment.method == "manual_mpesa" and payment.status == "pending":
                # Update payment status - this will trigger the model's save method
                # which will automatically handle enrollment and subscription activation
                payment.status = "success"
                payment.save()

                # Send success email
                try:
                    # Get the enrollment that was created by the Payment model
                    enrollment = Enrollment.objects.get(
                        user=payment.user, week=payment.week
                    )
                    email_sent = send_manual_payment_approval_email(payment, enrollment)
                    if email_sent:
                        self.message_user(
                            request,
                            f"Payment approved and confirmation email sent to {payment.user.email}",
                            level="SUCCESS",
                        )
                    else:
                        self.message_user(
                            request,
                            f"Payment approved but failed to send email to {payment.user.email}",
                            level="WARNING",
                        )
                except Enrollment.DoesNotExist:
                    self.message_user(
                        request,
                        f"Payment approved but enrollment not found",
                        level="WARNING",
                    )
                except Exception as e:
                    self.message_user(
                        request,
                        f"Payment approved but email failed: {str(e)}",
                        level="ERROR",
                    )
            else:
                self.message_user(
                    request,
                    "Can only approve pending manual M-Pesa payments",
                    level="ERROR",
                )

        except Payment.DoesNotExist:
            self.message_user(request, "Payment not found", level="ERROR")
        except Exception as e:
            self.message_user(request, f"Error: {str(e)}", level="ERROR")

        return redirect("admin:billing_payment_changelist")

    def mark_as_success(self, request, queryset):
        """Admin action to mark payments as success - let the Payment model handle the rest"""
        success_count = 0
        email_count = 0

        for payment in queryset:
            if payment.status != "success":
                # Just update the status - the Payment model's save method will handle everything else
                payment.status = "success"
                payment.save()

                # Send appropriate email based on payment method
                try:
                    if payment.method == "manual_mpesa":
                        # Get the enrollment that was created by the Payment model
                        enrollment = Enrollment.objects.get(
                            user=payment.user, week=payment.week
                        )
                        email_sent = send_manual_payment_approval_email(
                            payment, enrollment
                        )
                    else:
                        email_sent = send_payment_confirmation_email(
                            user_email=payment.user.email,
                            amount=payment.amount,
                            week_title=str(payment.week),
                            payment_method=payment.method,
                        )

                    if email_sent:
                        email_count += 1

                except Exception as e:
                    # Log but don't stop the process
                    print(f"Failed to send email for payment {payment.id}: {e}")

                success_count += 1

        message = f"{success_count} payments marked as successful"
        if email_count > 0:
            message += f" and {email_count} confirmation emails sent"

        self.message_user(request, message)

    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status="failed")
        self.message_user(request, f"{updated} payments marked as failed")

    mark_as_success.short_description = "Mark selected as SUCCESS (enroll user + email)"
    mark_as_failed.short_description = "Mark selected as FAILED"
