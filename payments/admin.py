# payments/admin.py
from django.contrib import admin
from .models import Payment, MpesaTransaction


class MpesaTransactionInline(admin.StackedInline):
    model       = MpesaTransaction
    extra       = 0
    readonly_fields = [
        'checkout_request_id', 'merchant_request_id',
        'mpesa_receipt_number', 'result_code', 'result_description',
        'raw_callback', 'created_at'
    ]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'payment_for', 'module', 'level', 'amount', 'status', 'created_at']
    list_filter   = ['status', 'payment_for', 'created_at']
    search_fields = ['user__username', 'module__title', 'level__name']
    readonly_fields = ['created_at', 'completed_at']
    inlines       = [MpesaTransactionInline]
    date_hierarchy = 'created_at'


@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display  = ['checkout_request_id', 'payment', 'phone_number', 'result_code', 'mpesa_receipt_number', 'created_at']
    list_filter   = ['result_code', 'created_at']
    search_fields = ['checkout_request_id', 'phone_number', 'mpesa_receipt_number']
    readonly_fields = ['checkout_request_id', 'merchant_request_id', 'created_at', 'raw_callback']
