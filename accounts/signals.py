"""
accounts/signals.py
Auto-grants 20 free credits to every new user on signup.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_credits(sender, instance, created, **kwargs):
    """Grant 20 free credits when a new user is created."""
    if created:
        try:
            from builder.models import UserCredits
            UserCredits.objects.get_or_create(
                user=instance,
                defaults={
                    'credits': 20,
                    'total_purchased': 0,
                    'total_used': 0,
                    'is_free_tier': True,
                }
            )
        except Exception:
            # Don't crash signup if builder app is not ready
            pass
