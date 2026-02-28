from celery import shared_task
from django.core.files.base import ContentFile
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
import re

from .models import WebsiteOrder
from .models_conversation import ConversationMessage, CodeRevision, ProjectFile
from .ai.conversation_client import ConversationalAIClient

logger = logging.getLogger(__name__)


@shared_task
def process_revision_request(
    order_id, user_message, current_code, conversation_history
):
    """
    Process a revision request from the user.
    Streams updates via WebSocket and saves the result.
    """
    channel_layer = get_channel_layer()
    room_group_name = f"order_{order_id}"

    def send_status(msg):
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {"type": "generation_message", "msg_type": "status", "message": msg},
        )

    def send_code_chunk(chunk):
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {"type": "generation_message", "msg_type": "code_update", "message": chunk},
        )

    try:
        order = WebsiteOrder.objects.get(id=order_id)

        send_status(f"Processing revision request: {user_message[:50]}...")

        # Initialize AI client
        client = ConversationalAIClient()

        # Stream the revision
        html_chunks = []
        for chunk in client.revise_website(
            current_code, user_message, conversation_history
        ):
            html_chunks.append(chunk)
            send_code_chunk(chunk)

        # Clean up and parse the output
        raw_html = "".join(html_chunks)

        # Try to parse as multi-file project
        files = client.parse_multi_file_output(raw_html)

        if len(files) > 1:
            # Multi-file project detected
            send_status(f"Saving {len(files)} files...")

            # Clear old project files for this order
            ProjectFile.objects.filter(order=order).delete()

            # Save each file
            for filename, content in files.items():
                file_type = filename.split(".")[-1] if "." in filename else "other"
                is_entry = filename in ["index.html", "App.jsx", "App.tsx"]

                ProjectFile.objects.create(
                    order=order,
                    filename=filename,
                    file_type=file_type,
                    content=content,
                    is_entry_point=is_entry,
                )

            # Merge for preview
            clean_html = client.merge_files_to_html(files)
        else:
            # Single file (backward compatibility)
            clean_html = client.clean_code_output(raw_html)
            # Clear any old project files
            ProjectFile.objects.filter(order=order).delete()
            # Create a single project file entry
            ProjectFile.objects.create(
                order=order,
                filename="index.html",
                file_type="html",
                content=clean_html,
                is_entry_point=True,
            )

        # Save revision before updating
        max_version = order.code_revisions.count() + 1
        CodeRevision.objects.create(
            order=order,
            version_number=max_version,
            code_content=current_code,
            change_description=user_message,
        )

        # Save new code (merged version for preview)
        file_path = f"ai_generated_projects/{order.id}/index.html"
        order.brief_files.save(file_path, ContentFile(clean_html.encode()))

        # Save AI response to conversation
        ai_response = f"I've updated the website based on your request: {user_message}"
        ConversationMessage.objects.create(
            order=order, role="assistant", content=ai_response, code_context=clean_html
        )

        if preview_url.startswith("/"):
            if hasattr(settings, 'BACKEND_URL') and settings.BACKEND_URL:
                preview_url = f"{settings.BACKEND_URL.rstrip('/')}{preview_url}"

        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                "type": "generation_message",
                "msg_type": "revision_complete",
                "preview_url": preview_url,
                "message": "Revision complete!",
            },
        )

        send_status("Revision applied successfully!")
        logger.info(f"Revision completed for order {order_id}")

    except WebsiteOrder.DoesNotExist:
        logger.error(f"Order {order_id} not found")
    except Exception as e:
        logger.error(f"Error processing revision: {str(e)}")
        send_status(f"Error: {str(e)}")

        # Save error to conversation
        try:
            order = WebsiteOrder.objects.get(id=order_id)
            ConversationMessage.objects.create(
                order=order,
                role="system",
                content=f"Error processing request: {str(e)}",
            )
        except:
            pass
