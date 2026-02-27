from django.db import models
from django.conf import settings
from services.common.models import ServiceOrder

__all__ = ["WebsiteOrder", "WebsiteRevision"]


class WebsiteOrder(ServiceOrder):
    project_brief = models.TextField()
    selected_template_id = models.CharField(max_length=100, blank=True, null=True)
    deadline = models.DateField(null=True, blank=True)
    revision_count = models.PositiveIntegerField(default=3)
    final_url = models.URLField(blank=True, null=True)
    brief_files = models.FileField(upload_to="briefs/websites/", null=True, blank=True)
    ai_project_type = models.CharField(
        max_length=20,
        choices=[
            ("single_file", "Single HTML File"),
            ("multi_file", "HTML/CSS/JS Separate"),
            ("react", "React Project"),
        ],
        default="single_file",
        help_text="Type of project structure for AI generation",
    )
    generated_zip = models.FileField(upload_to="ai_generated_projects/zips/", null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.service_type:
            self.service_type = "website"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Website Order"
        verbose_name_plural = "Website Orders"


class WebsiteRevision(models.Model):
    order = models.ForeignKey(
        WebsiteOrder, on_delete=models.CASCADE, related_name="revisions"
    )
    request_text = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("completed", "Completed")],
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
