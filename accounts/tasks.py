"""
accounts/tasks.py
Celery tasks for async email sending
"""
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, time_limit=30)
def send_verification_email_task(self, user_email, uid, token):
    """
    Async task to send verification email via Celery
    Retries up to 3 times with 5 second delay if it fails
    Times out after 30 seconds
    """
    try:
        from .email_utils import send_verification_email
        
        result = send_verification_email(user_email, uid, token)
        
        if result:
            logger.info(f"Verification email sent successfully to {user_email}")
            return {"status": "success", "email": user_email}
        else:
            raise Exception("send_verification_email returned False")
            
    except Exception as exc:
        logger.error(f"Failed to send verification email to {user_email}: {str(exc)}")
        
        # Retry with exponential backoff in 5 seconds
        raise self.retry(exc=exc, countdown=5)


@shared_task(bind=True, max_retries=3, time_limit=30)
def send_password_reset_email_task(self, user_email, uid, token):
    """
    Async task to send password reset email
    """
    try:
        from .email_utils import send_password_reset_email
        
        result = send_password_reset_email(user_email, uid, token)
        
        if result:
            logger.info(f"Password reset email sent successfully to {user_email}")
            return {"status": "success", "email": user_email}
        else:
            raise Exception("send_password_reset_email returned False")
            
    except Exception as exc:
        logger.error(f"Failed to send password reset email to {user_email}: {str(exc)}")
        raise self.retry(exc=exc, countdown=5)
