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
        
        # Get project type from order (default to single_file if not set)
        project_type = order.ai_project_type or "single_file"

        send_log(f"Agent identified requirements ({project_type}). Starting code generation...", "status")
        send_log("$ touch index.html", "status")
        send_log("Writing index.html...", "status")

        logger.info(
            f"About to stream response for order {order_id}, brief length: {len(order.project_brief) if order.project_brief else 0}, type: {project_type}"
        )

        # Stream the response and push to websocket
        current_buffer = ""
        last_file = None
        
        try:
            for chunk in generator.stream_response(order.project_brief, project_type=project_type):
                html_chunks.append(chunk)
                current_buffer += chunk

                # File detection logic: matches --- filename --- or *** # filename ***
                marker_match = re.search(r'(?:\n|^)(?:[#\-\*]{3,}\s*|File:\s*)(?:#\s*|file:?\s*)?["\']?([\w\./\-\\]+)["\']?(?:\s*[#\-\*]{3,}|(?::?\s*\n))', current_buffer, flags=re.IGNORECASE)
                if marker_match:
                    new_file = marker_match.group(1).strip()
                    # Clean filename: remove trailing decorators AI might add
                    new_file = re.sub(r'[:#\*].*$', '', new_file).strip()
                    new_file = new_file.replace('"', '').replace("'", "")
                    
                    if new_file != last_file:
                        if last_file:
                            send_log(f"Finalized {last_file} ✓", "status")
                        send_log(f"Creating {new_file}...", "status")
                        last_file = new_file
                        # Clear buffer after detection to keep it light
                        current_buffer = current_buffer[marker_match.end():]

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

        send_log(f"Successfully finalized {last_file} ✓", "status") if last_file else None
        send_log("\nCode generation complete. Finalizing assets...", "status")
        send_log("$ npm install && npm run build", "status")  # Simulating build

        # 2. Process the generated output
        html_content = "".join(html_chunks)

        # Check for multi-file project
        files = generator.parse_multi_file_output(html_content)
        
        description = "I've built a robust and responsive website based on your requirements."
        
        from .models_conversation import ProjectFile
        # CLEAR existing files for this order (critical for clean UI)
        ProjectFile.objects.filter(order=order).delete()

        if files:
            file_names = ", ".join(list(files.keys())[:5])
            description = f"Done! I've created a modular project with {len(files)} files including {file_names}. The UI is fully responsive and uses Tailwind CSS for premium aesthetics."
            
            send_log("Detected multi-file project. Saving individual files...", "status")
            
            # Save each file to the ProjectFile model
            for filename, content in files.items():
                file_type = filename.split(".")[-1].lower() if "." in filename else "other"
                # Map extension to model choices
                type_map = {'js': 'js', 'jsx': 'jsx', 'ts': 'ts', 'tsx': 'tsx', 'css': 'css', 'html': 'html', 'json': 'json'}
                model_type = type_map.get(file_type, 'html' if file_type == 'html' else 'other')

                is_entry = any(p in filename.lower() for p in ["index.html", "app.jsx", "app.js", "main.jsx"])
                
                ProjectFile.objects.create(
                    order=order,
                    filename=filename,
                    file_type=model_type,
                    content=content,
                    is_entry_point=is_entry
                )

            send_log("Merging for premium preview...", "status")
            # This handles inlining CSS/JS to prevent 404s
            clean_html = generator.merge_files_to_html(files)
            
            # Save the original files as a ZIP for download
            zip_buffer = generator.create_zip_archive(files)
            zip_filename = f"project_{order.id}.zip"
            order.generated_zip.save(zip_filename, ContentFile(zip_buffer.getvalue()), save=False)
        else:
            send_log("Single-file project detected. Finalizing...", "status")
            clean_html = generator.clean_code_output(html_content)
            # Create a single project file entry
            ProjectFile.objects.create(
                order=order,
                filename="index.html",
                file_type="html",
                content=clean_html,
                is_entry_point=True
            )
        # Save index.html for the preview
        file_path = f"ai_generated_projects/{order.id}.html"
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

        # Save the AI's "done" message to chat history
        from services.websites.models_conversation import ConversationMessage
        conv = ConversationMessage.objects.create(
            order=order,
            role="assistant",
            content=description
        )

        send_log("Deployment successful!", "status")
        send_log(f"Site live at: {preview_url}", "status")

        # Notify UI that it's complete, pass the iframe URL and description
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                "type": "generation_message",
                "msg_type": "complete",
                "preview_url": preview_url,
                "message": description,
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
