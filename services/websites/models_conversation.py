import uuid
from django.db import models
from django.apps import apps

# Lazy import to avoid circular dependency
# WebsiteOrder is imported when needed using apps.get_model()


class ConversationMessage(models.Model):
    """Store conversation history between user and AI for website generation."""

    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "WebsiteOrder",
        on_delete=models.CASCADE,
        related_name="conversation_messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    code_context = models.TextField(
        blank=True, null=True
    )  # Store code state at this point
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["order", "created_at"]),
        ]

    def __str__(self):
        return f"{self.role} - {self.content[:50]}..."


class CodeRevision(models.Model):
    """Store code versions for rollback capability."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "WebsiteOrder", on_delete=models.CASCADE, related_name="code_revisions"
    )
    version_number = models.PositiveIntegerField()
    code_content = models.TextField()
    change_description = models.TextField()  # What the AI said it changed
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        unique_together = ["order", "version_number"]

    def __str__(self):
        return f"v{self.version_number} - {self.order.id}"
