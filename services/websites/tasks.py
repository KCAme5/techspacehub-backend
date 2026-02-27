from celery import shared_task
from django.core.files.base import ContentFile
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import os
from .models import WebsiteOrder
from .ai.ollama_client import OllamaWebsiteGenerator
from services.common.services import BaseServiceLogic
import logging

logger = logging.getLogger(__name__)


@shared_task
def generate_ai_website(order_id):
    channel_layer = get_channel_layer()
    room_group_name = f"order_{order_id}"

    def send_log(msg, msg_type="status"):
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {"type": "generation_message", "msg_type": msg_type, "message": msg},
        )

    try:
        order = WebsiteOrder.objects.get(id=order_id)
        logger.info(f"Starting Local AI website generation for order {order_id}")

        send_log("Initializing AI Workspace...", "status")
        send_log("$ mkdir -p /app/workspace", "status")
        send_log("$ cd /app/workspace", "status")

        send_log("AI Agent online. Analyzing brief...", "status")

        BaseServiceLogic.update_status(
            order,
            "in_progress",
            comment="AI is currently writing the code. You can watch the live stream in the AI Workspace.",
        )

        # Instantiate our Local AI Client
        generator = OllamaWebsiteGenerator()
        html_chunks = []

        send_log("Agent identified requirements. Starting code generation...", "status")
        send_log("$ touch index.html", "status")
        send_log("Writing index.html...", "status")

        logger.info(
            f"About to stream response for order {order_id}, brief length: {len(order.project_brief) if order.project_brief else 0}"
        )

        # Stream the response and push to websocket
        try:
            for chunk in generator.stream_response(order.project_brief):
                html_chunks.append(chunk)

                # Send token to WebSocket UI
                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    {
                        "type": "generation_message",
                        "msg_type": "token",
                        "message": chunk,
                    },
                )
        except Exception as stream_error:
            logger.error(f"Stream error for order {order_id}: {str(stream_error)}")
            send_log(f"ERROR: Stream failed - {str(stream_error)}", "status")
            raise

        send_log("\nCode generation complete. Finalizing assets...", "status")
        send_log("$ npm install && npm run build", "status")  # Simulating build

        # 2. Store the generated website safely in the media directory
        html_content = "".join(html_chunks)

        # Clean up Markdown block hallucinations
        import re

        # Clean up any markdown blocks (html, jsx, js, etc.)
        clean_html = re.sub(r'```(?:html|jsx|javascript|js)?\n?|```', '', html_content, flags=re.IGNORECASE).strip()

        filename = f"index.html"
        file_path = f"ai_generated_projects/{order.id}/{filename}"

        send_log(f"Saving assets to permanent storage...", "status")

        # Save to the brief_files
        order.brief_files.save(file_path, ContentFile(clean_html.encode("utf-8")))

        # Use API endpoint to serve the HTML (Daphne doesn't serve media files)
        from django.urls import reverse

        preview_url = reverse("website-preview", kwargs={"order_id": order.id})
        # Make absolute URL
        from django.conf import settings

        if preview_url.startswith("/"):
            preview_url = f"{settings.BACKEND_URL}{preview_url}"
        order.final_url = preview_url
        order.save()

        send_log("Deployment successful!", "status")
        send_log(f"Site live at: {preview_url}", "status")

        # Notify UI that it's complete, pass the iframe URL
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                "type": "generation_message",
                "msg_type": "complete",
                "preview_url": preview_url,
                "message": "Generation complete!",
            },
        )

        # 3. Finalize
        BaseServiceLogic.update_status(
            order, "completed", comment="AI website generation completed successfully!"
        )
        logger.info(f"Successfully generated website for {order_id}")

    except WebsiteOrder.DoesNotExist:
        logger.error(f"WebsiteOrder {order_id} not found for AI task.")
    except Exception as e:
        logger.error(f"Error in Local AI generation task {order_id}: {str(e)}")
        try:
            order = WebsiteOrder.objects.get(id=order_id)
            BaseServiceLogic.update_status(
                order, "in_progress", comment=f"AI Generation Failed: {str(e)}"
            )

            # Notify UI of failure
            send_log(f"CRITICAL ERROR: {str(e)}", "status")
        except:
            pass
