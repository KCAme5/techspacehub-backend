# payments/models.py
from django.db import models
from django.conf import settings


class Payment(models.Model):
    STATUS_CHOICES  = [('pending','Pending'),('completed','Completed'),('failed','Failed')]
    PAY_FOR_CHOICES = [('single_module','Single Module'),('full_level','Full Level')]

    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name='hub_payments')
    module      = models.ForeignKey('courses.Module', on_delete=models.SET_NULL,
                                    null=True, blank=True)
    level       = models.ForeignKey('courses.Level', on_delete=models.SET_NULL,
                                    null=True, blank=True)
    payment_for = models.CharField(max_length=20, choices=PAY_FOR_CHOICES)
    amount      = models.DecimalField(max_digits=10, decimal_places=2)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at  = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Hub Payment'

    def __str__(self):
        return f"{self.user.username} — {self.payment_for} — {self.status}"


class MpesaTransaction(models.Model):
    """Safaricom M-Pesa STK push transaction record for hub payments."""
    payment              = models.OneToOneField(Payment, on_delete=models.CASCADE,
                                                related_name='mpesa_transaction')
    phone_number         = models.CharField(max_length=15)
    checkout_request_id  = models.CharField(max_length=100, unique=True)
    merchant_request_id  = models.CharField(max_length=100)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)
    result_code          = models.CharField(max_length=10, blank=True)
    result_description   = models.TextField(blank=True)
    raw_callback         = models.JSONField(null=True, blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'M-Pesa Transaction'

    def __str__(self):
        return f"MPesa {self.checkout_request_id} — {self.result_code or 'pending'}"
