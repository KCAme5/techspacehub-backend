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
    """Grant 20 free credits when a new CLIENT user is created."""
    logger.info(
        f"Signal triggered for user {instance.username}, created={created}, role={getattr(instance, 'role', 'None')}"
    )

    if created:
        # Only grant credits to users with 'client' role
        user_role = getattr(instance, "role", None)
        if user_role != "client":
            logger.info(
                f"Skipping credits for user {instance.username} - role is '{user_role}', not 'client'"
            )
            return

        try:
            from builder.models import UserCredits

            credits_obj, created_new = UserCredits.objects.get_or_create(
                user=instance,
                defaults={
                    "credits": 20,
                    "total_purchased": 0,
                    "total_used": 0,
                    "is_free_tier": True,
                },
            )

            if created_new:
                logger.info(
                    f"Created credits for client user {instance.username}: 20 credits"
                )
            else:
                logger.warning(
                    f"Client user {instance.username} already had credits record"
                )

        except Exception as e:
            # Don't crash signup if builder app is not ready
            logger.error(
                f"Failed to create credits for client user {instance.username}: {e}"
            )
            pass
