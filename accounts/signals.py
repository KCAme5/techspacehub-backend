"""
accounts/signals.py
Auto-grants 20 free credits to every new user on signup.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_credits(sender, instance, created, **kwargs):
    """Grant 20 free credits when a new user is created."""
    if created:
        try:
            from builder.services.credit_service import get_or_create_credits
            credits_obj, created_new = get_or_create_credits(instance)

            if created_new:
                logger.info(
                    f"Created credits for user {instance.username}: 20 credits"
                )
        except Exception as e:
            # Don't crash signup if builder app is not ready
            logger.error(
                f"Failed to create credits for user {instance.username}: {e}"
            )
            pass
