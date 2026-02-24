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
    try:
        order = WebsiteOrder.objects.get(id=order_id)
        logger.info(f"Starting Local AI website generation for order {order_id}")
        
        channel_layer = get_channel_layer()
        room_group_name = f'order_{order.id}'

        # Notify UI that generation has started
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'generation_message',
                'msg_type': 'status',
                'message': 'AI Agent online. Compiling architecture...'
            }
        )

        BaseServiceLogic.update_status(order, 'in_progress', comment="AI is currently writing the code. You can watch the live stream in the AI Workspace.")
        
        # Instantiate our Local AI Client
        generator = OllamaWebsiteGenerator()
        html_chunks = []
        
        # Stream the response and push to websocket
        for chunk in generator.stream_response(order.project_brief):
            html_chunks.append(chunk)
            
            # Send token to WebSocket UI
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'generation_message',
                    'msg_type': 'token',
                    'message': chunk
                }
            )

        # 2. Store the generated website safely in the media directory
        html_content = "".join(html_chunks)
        
        # Clean up Markdown block hallucinations
        import re
        clean_html = re.sub(r"```html\n|```", "", html_content).strip()

        filename = f"index.html"
        file_path = f"ai_generated_projects/{order.id}/{filename}"
        
        # Save to the brief_files
        order.brief_files.save(file_path, ContentFile(clean_html.encode('utf-8')))
        
        preview_url = order.brief_files.url
        order.final_url = preview_url
        order.save()
        
        # Notify UI that it's complete, pass the iframe URL
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'generation_message',
                'msg_type': 'complete',
                'preview_url': preview_url
            }
        )

        # 3. Finalize
        BaseServiceLogic.update_status(order, 'completed', comment="AI website generation completed successfully!")
        logger.info(f"Successfully generated website for {order_id}")
        
    except WebsiteOrder.DoesNotExist:
        logger.error(f"WebsiteOrder {order_id} not found for AI task.")
    except Exception as e:
        logger.error(f"Error in Local AI generation task {order_id}: {str(e)}")
        try:
            order = WebsiteOrder.objects.get(id=order_id)
            BaseServiceLogic.update_status(order, 'in_progress', comment=f"AI Generation Failed: {str(e)}")
            
            # Notify UI of failure
            async_to_sync(get_channel_layer().group_send)(
                f'order_{order_id}',
                {
                    'type': 'generation_message',
                    'msg_type': 'status',
                    'message': f'CRITICAL ERROR: {str(e)}'
                }
            )
        except:
            pass
