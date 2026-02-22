from django.db import models
import uuid

class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class ServiceRequest(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='service_requests')
    status = models.CharField(max_length=20, default='pending')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True
