"""
accounts/tasks.py
Celery tasks and dispatch helpers for email sending
"""
import logging
from threading import Thread

from celery import shared_task

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
    Queue email work without blocking the request thread.
    If Celery broker publishing fails, fall back to a direct SMTP send
    in the same background thread.
    """
    def runner():
        logger.info(
            "Background email dispatch starting task=%s target=%s",
            getattr(task_func, "name", repr(task_func)),
            args[0] if args else None,
        )
        try:
            task_func.delay(*args)
            logger.info(
                "Background email dispatch queued task=%s target=%s",
                getattr(task_func, "name", repr(task_func)),
                args[0] if args else None,
            )
        except Exception as exc:
            logger.warning(
                "Failed to queue email task %s; falling back to direct send. Error: %s",
                getattr(task_func, "name", repr(task_func)),
                exc,
            )
            try:
                fallback_func(*args)
                logger.info(
                    "Background email dispatch fallback send succeeded task=%s target=%s",
                    getattr(task_func, "name", repr(task_func)),
                    args[0] if args else None,
                )
            except Exception:
                logger.exception(
                    "Background email dispatch fallback send failed task=%s target=%s",
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
