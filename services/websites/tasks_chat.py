from celery import shared_task
from django.core.files.base import ContentFile
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
import re

from .models import WebsiteOrder
from .models_conversation import ConversationMessage, CodeRevision
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

        # Clean up the output
        raw_html = "".join(html_chunks)
        clean_html = client.clean_code_output(raw_html)

        # Save revision before updating
        max_version = order.code_revisions.count() + 1
        CodeRevision.objects.create(
            order=order,
            version_number=max_version,
            code_content=current_code,
            change_description=user_message,
        )

        # Save new code
        file_path = f"ai_generated_projects/{order.id}/index.html"
        order.brief_files.save(file_path, ContentFile(clean_html.encode()))

        # Save AI response to conversation
        ai_response = f"I've updated the website based on your request: {user_message}"
        ConversationMessage.objects.create(
            order=order, role="assistant", content=ai_response, code_context=clean_html
        )

        # Send completion
        from django.conf import settings
        from django.urls import reverse

        preview_url = reverse("website-preview", kwargs={"order_id": order.id})
        if preview_url.startswith("/"):
            preview_url = f"{settings.BACKEND_URL}{preview_url}"

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
