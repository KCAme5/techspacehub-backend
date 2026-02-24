from celery import shared_task
from django.core.files.base import ContentFile
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
        
        # Instantiate our Local AI Client
        generator = OllamaWebsiteGenerator()
        
        # 1. Call Local AI (Blocks - Takes a couple minutes on CPU)
        BaseServiceLogic.update_status(order, 'in_progress', comment="AI is currently writing the code. This may take up to 5 minutes.")
        html_content = generator.generate_website(order.project_brief, order.selected_template_id)
        
        # 2. Store the generated website safely in the media directory
        filename = f"index.html"
        file_path = f"ai_generated_projects/{order.id}/{filename}"
        
        # Save to the brief_files (or a dedicated FileField if preferrable)
        order.brief_files.save(file_path, ContentFile(html_content.encode('utf-8')))
        
        # Set the live preview URL (Assumes Media files are served/routed securely or Nginx mapped)
        preview_url = order.brief_files.url
        order.final_url = preview_url
        order.save()
        
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
        except:
            pass
