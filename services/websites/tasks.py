from celery import shared_task
from .models import WebsiteOrder
from .ai.generators import WebsiteGenerator
from services.common.services import BaseServiceLogic
import logging

logger = logging.getLogger(__name__)

@shared_task
def generate_ai_website(order_id):
    try:
        order = WebsiteOrder.objects.get(id=order_id)
        logger.info(f"Starting AI website generation for order {order_id}")
        
        generator = WebsiteGenerator()
        prompt = generator.build_prompt(order.project_brief, order.selected_template_id)
        
        # 1. Call AI
        content = generator.generate(prompt)
        
        # 2. Deploy preview (placeholder)
        # In a real scenario, this would write to a static folder or simple Docker
        preview_url = f"https://previews.techspacehub.co.ke/{order.id}/"
        order.final_url = preview_url
        
        # 3. Finalize
        BaseServiceLogic.update_status(order, 'completed', comment="AI website preview generated and deployed.")
        
    except WebsiteOrder.DoesNotExist:
        logger.error(f"WebsiteOrder {order_id} not found for generation task.")
    except Exception as e:
        logger.error(f"Error in AI generation task {order_id}: {str(e)}")
