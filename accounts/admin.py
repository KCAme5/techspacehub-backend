from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    Profile,
    Subscription,
    Wallet,
    Referral,
    WalletTransaction,
    WithdrawalRequest,
)
from django.utils import timezone


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Profile"
    fk_name = "user"


class SubscriptionInline(admin.StackedInline):
    model = Subscription
    can_delete = False
    verbose_name_plural = "Subscription"
    fk_name = "user"


class WalletInline(admin.StackedInline):
    model = Wallet
    can_delete = False
    verbose_name_plural = "Wallet"
    fk_name = "user"


class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            None,
            {
                "fields": (
                    "role",
                    "subscription_status",
                    "my_referral_code",
                    "referred_by",
                )
            },
        ),
    )
    inlines = [ProfileInline, SubscriptionInline, WalletInline]

    list_display = (
        "username",
        "email",
        "role",
        "subscription_status",
        "my_referral_code",
        "referred_by",
        "is_staff",
        "is_superuser",
    )
    search_fields = ("username", "email", "my_referral_code")
    list_filter = ("role", "subscription_status", "is_staff", "is_superuser")


class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    list_filter = ("created_at",)
    readonly_fields = ("created_at", "updated_at")


class ReferralAdmin(admin.ModelAdmin):
    list_display = (
        "referrer",
        "referred_user",
        "referral_code_used",
        "status",
        "commission_earned",
        "commission_paid",
        "referral_date",
    )
    search_fields = (
        "referrer__username",
        "referrer__email",
        "referred_user__username",
        "referred_user__email",
    )
    list_filter = ("status", "commission_paid", "referral_date")
    readonly_fields = ("referral_date",)


class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("wallet", "amount", "transaction_type", "status", "created_at")
    search_fields = ("wallet__user__username", "wallet__user__email")
    list_filter = ("transaction_type", "status", "created_at")
    readonly_fields = ("created_at",)


class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "method", "status", "created_at", "processed_at")
    search_fields = ("user__username", "user__email")
    list_filter = ("method", "status", "created_at")
    readonly_fields = ("created_at",)

    actions = ["approve_withdrawals", "reject_withdrawals"]

    def approve_withdrawals(self, request, queryset):
        for withdrawal in queryset:
            withdrawal.status = "approved"
            withdrawal.processed_at = timezone.now()
            withdrawal.save()

            # Create wallet transaction for the withdrawal
            WalletTransaction.objects.create(
                wallet=withdrawal.user.wallet,
                amount=-withdrawal.amount,
                transaction_type="withdrawal",
                description=f"Withdrawal processed - {withdrawal.method}",
                status="completed",
            )
        self.message_user(
            request, f"{queryset.count()} withdrawals approved successfully."
        )

    def reject_withdrawals(self, request, queryset):
        for withdrawal in queryset:
            withdrawal.status = "rejected"
            withdrawal.processed_at = timezone.now()
            withdrawal.save()

            # Refund the amount back to wallet
            wallet = withdrawal.user.wallet
            wallet.balance += withdrawal.amount
            wallet.save()
        self.message_user(
            request, f"{queryset.count()} withdrawals rejected and amounts refunded."
        )


# Register everything
admin.site.register(User, UserAdmin)
admin.site.register(Profile)
admin.site.register(Subscription)
admin.site.register(Wallet, WalletAdmin)
admin.site.register(Referral, ReferralAdmin)
admin.site.register(WalletTransaction, WalletTransactionAdmin)
admin.site.register(WithdrawalRequest, WithdrawalRequestAdmin)
