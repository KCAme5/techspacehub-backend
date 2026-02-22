from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from .models import ServiceStatusHistory
import logging

logger = logging.getLogger(__name__)

class BaseServiceLogic:
    @staticmethod
    def update_status(order, new_status, user=None, comment=""):
        old_status = order.status
        order.status = new_status
        order.save()
        
        content_type = ContentType.objects.get_for_model(order)
        ServiceStatusHistory.objects.create(
            content_type=content_type,
            object_id=order.id,
            old_status=old_status,
            new_status=new_status,
            changed_by=user,
            comment=comment
        )
        logger.info(f"Order {order.id} status updated from {old_status} to {new_status}")

    @staticmethod
    def mark_consent_given(order, ip):
        order.consent_given = True
        order.consent_timestamp = timezone.now()
        order.consent_ip = ip
        order.status = 'consented'
        order.save()
        
        # Log status change
        BaseServiceLogic.update_status(order, 'consented', comment="Client provided digital consent.")

    @staticmethod
    def calculate_platform_fee(order):
        # Placeholder: 20% platform fee
        return order.total_price * 0.2

    @staticmethod
    def release_payment_to_agent(order, agent):
        # This will trigger billing payout logic later
        pass
