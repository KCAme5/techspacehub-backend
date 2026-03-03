from celery import shared_task
from django.core.files.base import ContentFile
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings
from django.urls import reverse
import logging
import re
import os
from .models import WebsiteOrder
from services.common.services import BaseServiceLogic

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
        logger.info(f"Starting AI website generation for order {order_id}")

        send_log("Initializing AI Workspace...", "status")
        send_log("$ mkdir -p /app/workspace", "status")
        send_log("$ cd /app/workspace", "status")

        send_log("AI Agent online. Analyzing brief...", "status")

        BaseServiceLogic.update_status(
            order,
            "in_progress",
            comment="AI is currently writing the code. You can watch the live stream in the AI Workspace.",
        )

        from .ai.ai_utils import get_universal_generator
        generator = get_universal_generator()
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

        # 2. Process the generated output
        html_content = "".join(html_chunks)

        # Check if it's a multi-file JSON
        files = generator.parse_multi_file_output(html_content)
        
        if files:
            send_log("Detected multi-file project. Merging for preview...", "status")
            clean_html = generator.merge_files_to_html(files)
            
            # Save the original files as a ZIP for download
            zip_buffer = generator.create_zip_archive(files)
            zip_filename = f"project_{order.id}.zip"
            zip_path = f"ai_generated_projects/zips/{zip_filename}"
            order.generated_zip.save(zip_path, ContentFile(zip_buffer.getvalue()))
        else:
            send_log("Detected single-file project. Cleaning up code...", "status")
            clean_html = re.sub(r'```(?:html|jsx|javascript|js)?\n?|```', '', html_content, flags=re.IGNORECASE).strip()

        # Save index.html for the preview
        filename = f"index.html"
        file_path = f"ai_generated_projects/{order.id}/{filename}"
        send_log(f"Saving assets to permanent storage...", "status")

        # Save the preview HTML to brief_files (which views_serve.py uses)
        order.brief_files.save(file_path, ContentFile(clean_html.encode("utf-8")))

        # Use API endpoint to serve the HTML
        preview_url = reverse("website-preview", kwargs={"order_id": order.id})
        
        # Ensure we use an absolute URL if needed, or just let the frontend handle the relative path
        if hasattr(settings, 'BACKEND_URL') and settings.BACKEND_URL:
            if preview_url.startswith("/"):
                preview_url = f"{settings.BACKEND_URL.rstrip('/')}{preview_url}"
        
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
                order, "failed", comment=f"AI Generation Failed: {str(e)}"
            )

            # Notify UI of failure
            send_log(f"CRITICAL ERROR: {str(e)}", "status")
        except:
            pass
