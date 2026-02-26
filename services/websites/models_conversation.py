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


class ProjectFile(models.Model):
    """Store individual files for multi-file website projects."""

    FILE_TYPES = [
        ("html", "HTML"),
        ("css", "CSS"),
        ("js", "JavaScript"),
        ("jsx", "JSX/React"),
        ("ts", "TypeScript"),
        ("tsx", "TSX/React"),
        ("json", "JSON"),
        ("md", "Markdown"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "WebsiteOrder", on_delete=models.CASCADE, related_name="project_files"
    )
    filename = models.CharField(max_length=255)  # e.g., "index.html", "styles.css"
    file_type = models.CharField(max_length=10, choices=FILE_TYPES, default="html")
    content = models.TextField()
    is_entry_point = models.BooleanField(
        default=False
    )  # Main file (index.html or App.jsx)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_entry_point", "filename"]
        unique_together = ["order", "filename"]
        indexes = [
            models.Index(fields=["order", "file_type"]),
        ]

    def __str__(self):
        return (f"{self.filename} ({self.order.id})",)
