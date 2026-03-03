from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from celery import chain
import logging

from .models import WebsiteOrder
from .models_conversation import ConversationMessage, CodeRevision, ProjectFile
from .tasks import generate_ai_website
from .tasks_chat import process_revision_request

logger = logging.getLogger(__name__)


class WebsiteAIChatViewSet(viewsets.ViewSet):
    """API endpoints for conversational AI website editing."""

    permission_classes = [IsAuthenticated]

    def _get_order(self, pk):
        """Get order and verify ownership."""
        order = get_object_or_404(WebsiteOrder, id=pk)
        if order.client != self.request.user:
            raise PermissionError("Not authorized")
        return order

    @action(detail=True, methods=["get"])
    def conversation_history(self, request, pk=None):
        """Get conversation history for an order."""
        try:
            order = self._get_order(pk)
            messages = order.conversation_messages.all()
            return Response(
                {
                    "messages": [
                        {
                            "id": str(msg.id),
                            "role": msg.role,
                            "content": msg.content,
                            "created_at": msg.created_at.isoformat(),
                        }
                        for msg in messages
                    ]
                }
            )
        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        """Send a message to the AI and get a revision."""
        try:
            order = self._get_order(pk)
            message = request.data.get("message", "").strip()

            if not message:
                return Response(
                    {"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Get current code from the order's file
            current_code = ""
            if order.brief_files:
                try:
                    with order.brief_files.open("r") as f:
                        current_code = f.read()
                except Exception as e:
                    logger.error(f"Error reading file: {e}")

            # Get conversation history
            history = list(order.conversation_messages.values("role", "content"))

            # Save user message
            ConversationMessage.objects.create(
                order=order, role="user", content=message, code_context=current_code
            )

            # Queue the revision task
            task = process_revision_request.delay(
                str(order.id), message, current_code, history
            )

            return Response(
                {
                    "task_id": task.id,
                    "status": "processing",
                    "message": "Revision request queued",
                }
            )

        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=["get"])
    def project_files(self, request, pk=None):
        """Get all project files for an order (multi-file support)."""
        try:
            order = self._get_order(pk)
            files = order.project_files.all()
            return Response(
                {
                    "files": [
                        {
                            "id": str(f.id),
                            "filename": f.filename,
                            "file_type": f.file_type,
                            "content": f.content,
                            "is_entry_point": f.is_entry_point,
                            "updated_at": f.updated_at.isoformat(),
                        }
                        for f in files
                    ],
                    "entry_file": (
                        files.filter(is_entry_point=True).first().filename
                        if files.filter(is_entry_point=True).exists()
                        else "index.html"
                    ),
                }
            )
        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=["post"])
    def save_project_file(self, request, pk=None):
        """Save/update a specific project file."""
        try:
            order = self._get_order(pk)
            filename = request.data.get("filename", "").strip()
            content = request.data.get("content", "").strip()

            if not filename or not content:
                return Response(
                    {"error": "filename and content are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            file_type = filename.split(".")[-1] if "." in filename else "other"
            is_entry = filename in ["index.html", "App.jsx", "App.tsx"]

            # Update or create
            file_obj, created = ProjectFile.objects.update_or_create(
                order=order,
                filename=filename,
                defaults={
                    "content": content,
                    "file_type": file_type,
                    "is_entry_point": is_entry,
                },
            )

            return Response(
                {"success": True, "created": created, "file_id": str(file_obj.id)}
            )

        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=["get"])
    def code_revisions(self, request, pk=None):
        """Get all code revisions for an order."""
        try:
            order = self._get_order(pk)
            revisions = order.code_revisions.all()[:10]  # Last 10
            return Response(
                {
                    "revisions": [
                        {
                            "id": str(rev.id),
                            "version": rev.version_number,
                            "description": rev.change_description,
                            "created_at": rev.created_at.isoformat(),
                        }
                        for rev in revisions
                    ]
                }
            )
        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=["post"])
    def rollback(self, request, pk=None):
        """Rollback to a specific revision."""
        try:
            order = self._get_order(pk)
            revision_id = request.data.get("revision_id")

            if not revision_id:
                return Response(
                    {"error": "revision_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            revision = get_object_or_404(CodeRevision, id=revision_id, order=order)

            # Save current as new revision before rollback
            if order.brief_files:
                try:
                    with order.brief_files.open("r") as f:
                        current_code = f.read()
                    max_version = order.code_revisions.count() + 1
                    CodeRevision.objects.create(
                        order=order,
                        version_number=max_version,
                        code_content=current_code,
                        change_description=f"Auto-save before rollback to v{revision.version_number}",
                    )
                except Exception as e:
                    logger.error(f"Error saving before rollback: {e}")

            # Rollback to selected revision
            from django.core.files.base import ContentFile

            file_path = f"ai_generated_projects/{order.id}/index.html"
            order.brief_files.save(
                file_path, ContentFile(revision.code_content.encode())
            )

            # Log the rollback
            ConversationMessage.objects.create(
                order=order,
                role="system",
                content=f"Rolled back to version {revision.version_number}",
            )

            return Response(
                {"success": True, "rolled_back_to": revision.version_number}
            )

        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=["post"])
    def update_code_directly(self, request, pk=None):
        """Allow user to directly edit code (from the code editor)."""
        try:
            order = self._get_order(pk)
            code = request.data.get("code", "").strip()

            if not code:
                return Response(
                    {"error": "code is required"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Save current version before update
            if order.brief_files:
                try:
                    with order.brief_files.open("r") as f:
                        old_code = f.read()
                    max_version = order.code_revisions.count() + 1
                    CodeRevision.objects.create(
                        order=order,
                        version_number=max_version,
                        code_content=old_code,
                        change_description="User manual edit",
                    )
                except Exception as e:
                    logger.error(f"Error saving before edit: {e}")

            # Save new code
            from django.core.files.base import ContentFile

            file_path = f"ai_generated_projects/{order.id}/index.html"
            order.brief_files.save(file_path, ContentFile(code.encode()))

            # Log the edit
            ConversationMessage.objects.create(
                order=order, role="system", content="User manually edited the code"
            )

            return Response({"success": True})

        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=["post"])
    def set_project_type(self, request, pk=None):
        """Set the project type (single_file, multi_file, react)."""
        try:
            order = self._get_order(pk)
            project_type = request.data.get("project_type", "single_file")

            # Store in order metadata
            order.ai_project_type = project_type
            order.save(update_fields=["ai_project_type"])

            return Response({"success": True, "project_type": project_type})
        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.error(f"Error setting project type: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
