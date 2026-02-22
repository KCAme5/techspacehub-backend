from django.db import models
from services.common.models import ServiceRequest

class WebsiteOrder(ServiceRequest):
    plan_type = models.CharField(max_length=50)
    domain_name = models.CharField(max_length=255, blank=True, null=True)
    is_ai_generated = models.BooleanField(default=False)

class WebsiteBrief(models.Model):
    order = models.OneToOneField(WebsiteOrder, on_delete=models.CASCADE, related_name='brief')
    description = models.TextField()
    color_scheme = models.CharField(max_length=100, blank=True, null=True)
