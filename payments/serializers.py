# payments/serializers.py
from rest_framework import serializers
from .models import Payment, MpesaTransaction


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Payment
        fields = [
            'id', 'payment_for', 'module', 'level',
            'amount', 'status', 'created_at', 'completed_at'
        ]
        read_only_fields = ['status', 'created_at', 'completed_at']


class InitiatePaymentSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    payment_for  = serializers.ChoiceField(choices=['single_module', 'full_level'])
    module_id    = serializers.IntegerField(required=False, allow_null=True)
    level_id     = serializers.IntegerField(required=False, allow_null=True)
    amount       = serializers.DecimalField(max_digits=10, decimal_places=2)


class MpesaTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MpesaTransaction
        fields = [
            'id', 'payment', 'phone_number', 'checkout_request_id',
            'mpesa_receipt_number', 'result_code', 'result_description', 'created_at'
        ]
        read_only_fields = ['checkout_request_id', 'created_at']
