"""from django.contrib import admin
from .models import Purchase, CourseEntitlement, LabCreditWallet, LabCreditTransaction


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "amount",
        "currency",
        "payment_method",
        "success",
        "created_at",
    )
    list_filter = ("success", "currency", "payment_method", "created_at")
    search_fields = ("user__username", "transaction_id")
    readonly_fields = ("created_at",)  # timestamps shouldn't be editable


@admin.register(CourseEntitlement)
class CourseEntitlementAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "course", "activated_at", "purchase")
    list_filter = ("activated_at", "course")
    search_fields = ("user__username", "course__title")
    readonly_fields = ("activated_at",)


@admin.register(LabCreditWallet)
class LabCreditWalletAdmin(admin.ModelAdmin):
    list_display = ("user", "credits")
    search_fields = ("user__username",)


@admin.register(LabCreditTransaction)
class LabCreditTransactionAdmin(admin.ModelAdmin):
    list_display = ("wallet", "amount", "created_at", "description", "purchase")
    list_filter = ("created_at",)
    search_fields = ("wallet__user__username", "description")
    readonly_fields = ("created_at",)
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
