from django.db import models
from django.conf import settings
from services.common.models import ServiceOrder

class AuditOrder(ServiceOrder):
    target_url_or_ip = models.CharField(max_length=255)
    scope_text = models.TextField(help_text="In scope and out of scope details")
    authenticated_scan = models.BooleanField(default=False)
    report_file = models.FileField(upload_to='reports/audits/', null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.service_type:
            self.service_type = 'audit'
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Audit Order"
        verbose_name_plural = "Audit Orders"

class ScanResult(models.Model):
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
        ('info', 'Info'),
    ]

    order = models.ForeignKey(AuditOrder, on_delete=models.CASCADE, related_name='scan_results')
    title = models.CharField(max_length=255)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    description = models.TextField()
    evidence_url = models.URLField(blank=True, null=True)
    fixed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-severity', 'created_at']

class AgentAssignment(models.Model):
    order = models.ForeignKey(AuditOrder, on_delete=models.CASCADE, related_name='assignments')
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='audit_assignments')
    claimed_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    payout_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ['order', 'agent']
