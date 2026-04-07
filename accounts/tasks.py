"""
accounts/tasks.py
Celery tasks and dispatch helpers for email sending
"""
import logging
from threading import Thread

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, time_limit=30)
def send_verification_email_task(self, user_email, uid, token):
    """
    Async task to send verification email via Celery
    Retries up to 3 times with 5 second delay if it fails
    Times out after 30 seconds
    """
    try:
        logger.info(
            "send_verification_email_task started email=%s uid=%s retry=%s",
            user_email,
            uid,
            self.request.retries,
        )
        from .email_utils import send_verification_email
        
        result = send_verification_email(user_email, uid, token)
        
        if result:
            logger.info(f"Verification email sent successfully to {user_email}")
            return {"status": "success", "email": user_email}
        else:
            raise Exception("send_verification_email returned False")
            
    except Exception as exc:
        logger.error(f"Failed to send verification email to {user_email}: {str(exc)}", exc_info=True)
        
        # Retry with exponential backoff in 5 seconds
        raise self.retry(exc=exc, countdown=5)


@shared_task(bind=True, max_retries=3, time_limit=30)
def send_password_reset_email_task(self, user_email, uid, token):
    """
    Async task to send password reset email
    """
    try:
        logger.info(
            "send_password_reset_email_task started email=%s uid=%s retry=%s",
            user_email,
            uid,
            self.request.retries,
        )
        from .email_utils import send_password_reset_email
        
        result = send_password_reset_email(user_email, uid, token)
        
        if result:
            logger.info(f"Password reset email sent successfully to {user_email}")
            return {"status": "success", "email": user_email}
        else:
            raise Exception("send_password_reset_email returned False")
            
    except Exception as exc:
        logger.error(f"Failed to send password reset email to {user_email}: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=5)


def _dispatch_email_in_background(task_func, fallback_func, *args):
    """
    Dispatch email work without blocking the request thread.
    Default mode is a direct SMTP send on a background thread because it
    works even when no Celery worker is running. Celery mode can still be
    enabled explicitly through settings.
    """
    dispatch_mode = getattr(settings, "EMAIL_DISPATCH_MODE", "thread").lower()

    def runner():
        logger.info(
            "Background email dispatch starting mode=%s task=%s target=%s",
            dispatch_mode,
            getattr(task_func, "name", repr(task_func)),
            args[0] if args else None,
        )

        if dispatch_mode == "celery":
            try:
                task_func.delay(*args)
                logger.info(
                    "Background email dispatch queued task=%s target=%s",
                    getattr(task_func, "name", repr(task_func)),
                    args[0] if args else None,
                )
                return
            except Exception as exc:
                logger.warning(
                    "Failed to queue email task %s; falling back to direct send. Error: %s",
                    getattr(task_func, "name", repr(task_func)),
                    exc,
                )

        try:
            fallback_func(*args)
            logger.info(
                "Background email dispatch direct send succeeded task=%s target=%s",
                getattr(task_func, "name", repr(task_func)),
                args[0] if args else None,
            )
        except Exception:
            logger.exception(
                "Background email dispatch direct send failed task=%s target=%s",
                getattr(task_func, "name", repr(task_func)),
                args[0] if args else None,
            )

    Thread(target=runner, daemon=True).start()


def dispatch_verification_email(user_email, uid, token):
    from .email_utils import send_verification_email

    _dispatch_email_in_background(
        send_verification_email_task,
        send_verification_email,
        user_email,
        uid,
        token,
    )


def dispatch_password_reset_email(user_email, uid, token):
    from .email_utils import send_password_reset_email

    _dispatch_email_in_background(
        send_password_reset_email_task,
        send_password_reset_email,
        user_email,
        uid,
        token,
    )
