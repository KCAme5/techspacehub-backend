"""
builder/admin.py — Register models for the Django admin panel.
"""
from django.contrib import admin
from .models import UserCredits, CreditPackage, CreditPayment


@admin.register(UserCredits)
class UserCreditsAdmin(admin.ModelAdmin):
    list_display  = ('user', 'credits', 'total_purchased', 'total_used', 'is_free_tier', 'updated_at')
    search_fields = ('user__username', 'user__email')
    list_filter   = ('is_free_tier',)
    readonly_fields = ('updated_at',)


@admin.register(CreditPackage)
class CreditPackageAdmin(admin.ModelAdmin):
    list_display  = ('name', 'credits', 'price_kes', 'is_popular', 'is_active', 'sort_order')
    list_editable = ('is_active', 'is_popular', 'sort_order')


@admin.register(CreditPayment)
class CreditPaymentAdmin(admin.ModelAdmin):
    list_display  = ('user', 'credits', 'amount', 'status', 'mpesa_checkout_id', 'created_at')
    list_filter   = ('status',)
    search_fields = ('user__username', 'mpesa_checkout_id', 'mpesa_receipt')
    readonly_fields = ('created_at', 'completed_at')
