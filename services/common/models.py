from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid

class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class ServiceOrder(TimestampedModel):
    SERVICE_TYPE_CHOICES = [
        ('audit', 'Cybersecurity Audit'),
        ('website', 'Website Development'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('paid', 'Paid'),
        ('consented', 'Consented'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('disputed', 'Disputed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="%(class)s_orders"
    )
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES)
    mode = models.CharField(max_length=50) # 'automated'/'manned' for audits, 'ai'/'manual' for websites
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    payment = models.ForeignKey(
        'billing.Payment', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="%(class)s_orders",
        to_field="id"
    )
    
    # Consent fields (DPA Compliance)
    consent_given = models.BooleanField(default=False)
    consent_timestamp = models.DateTimeField(null=True, blank=True)
    consent_ip = models.GenericIPAddressField(null=True, blank=True)
    
    notes = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True

class ServiceComment(TimestampedModel):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['created_at']

class ServiceStatusHistory(TimestampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    old_status = models.CharField(max_length=20, blank=True, null=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    comment = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Service status histories"
        ordering = ['-created_at']
