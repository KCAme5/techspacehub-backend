from django.core.mail import send_mail
from django.conf import settings


def send_verification_email(email, uid, token):
    verify_url = f"{settings.FRONTEND_URL}/verify-email/{uid}/{token}/"
    subject = "Verify your account"
    message = f"Please verify your account by clicking: {verify_url}"

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,  # e.g., "noreply@cybercraft.com"
        [email],
        fail_silently=False,
    )
