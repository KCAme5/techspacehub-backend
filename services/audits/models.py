from django.db import models
from services.common.models import ServiceRequest

class AuditRequest(ServiceRequest):
    target_url = models.URLField()
    audit_type = models.CharField(max_length=50, choices=[('automated', 'Automated'), ('manned', 'Manned')])
    agent = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_audits')

class ScanResult(models.Model):
    audit = models.ForeignKey(AuditRequest, on_delete=models.CASCADE, related_name='scan_results')
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
