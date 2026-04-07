import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import requests

logger = logging.getLogger(__name__)


def _send_email(subject, plain_message, html_message, recipient_list):
    transport = getattr(settings, "EMAIL_TRANSPORT", "smtp").lower()

    if transport == "brevo_api":
        return _send_email_via_brevo_api(
            subject=subject,
            plain_message=plain_message,
            html_message=html_message,
            recipient_list=recipient_list,
        )

    logger.info(
        "_send_email using smtp transport recipients=%s host=%s port=%s backend=%s timeout=%s",
        recipient_list,
        settings.EMAIL_HOST,
        settings.EMAIL_PORT,
        settings.EMAIL_BACKEND,
        getattr(settings, "EMAIL_TIMEOUT", None),
    )
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
        html_message=html_message,
        fail_silently=False,
    )
    return True


def _send_email_via_brevo_api(subject, plain_message, html_message, recipient_list):
    api_key = getattr(settings, "BREVO_API_KEY", None)
    if not api_key:
        raise RuntimeError("BREVO_API_KEY is required when EMAIL_TRANSPORT=brevo_api")

    sender_email = settings.DEFAULT_FROM_EMAIL
    sender_name = getattr(settings, "SITE_NAME", "TechSpace")
    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "to": [{"email": email} for email in recipient_list],
        "subject": subject,
        "textContent": plain_message,
        "htmlContent": html_message,
    }
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }

    logger.info(
        "_send_email using brevo_api transport recipients=%s url=%s timeout=%s",
        recipient_list,
        settings.BREVO_API_URL,
        getattr(settings, "EMAIL_TIMEOUT", None),
    )
    response = requests.post(
        settings.BREVO_API_URL,
        json=payload,
        headers=headers,
        timeout=getattr(settings, "EMAIL_TIMEOUT", 10),
    )
    response.raise_for_status()
    logger.info("_send_email brevo_api response status=%s body=%s", response.status_code, response.text[:300])
    return True


def send_verification_email(user_email, uid, token):
    """
    Send account verification email
    """
    try:
        logger.info(
            "send_verification_email start email=%s transport=%s host=%s port=%s backend=%s from=%s timeout=%s",
            user_email,
            getattr(settings, "EMAIL_TRANSPORT", "smtp"),
            settings.EMAIL_HOST,
            settings.EMAIL_PORT,
            settings.EMAIL_BACKEND,
            settings.DEFAULT_FROM_EMAIL,
            getattr(settings, "EMAIL_TIMEOUT", None),
        )
        verify_link = f"{settings.FRONTEND_URL}/verify-email/{uid}/{token}/"

        subject = "Verify Your TechSpace Hub Account"
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verify Your Email</title>
        </head>
        <body style="margin:0;padding:0;background:#f4f7fb;font-family:Segoe UI,Arial,sans-serif;color:#102033;">
            <div style="padding:32px 16px;">
                <div style="max-width:620px;margin:0 auto;background:#ffffff;border:1px solid #dbe4f0;border-radius:24px;overflow:hidden;box-shadow:0 18px 50px rgba(16,32,51,0.08);">
                    <div style="padding:32px 36px;background:linear-gradient(135deg,#0f3d5e 0%,#1f7a8c 55%,#bfd7ea 100%);color:#ffffff;">
                        <div style="font-size:12px;letter-spacing:0.18em;text-transform:uppercase;opacity:0.86;">TechSpace Hub</div>
                        <h1 style="margin:14px 0 10px;font-size:32px;line-height:1.15;">Verify your email</h1>
                        <p style="margin:0;font-size:15px;line-height:1.7;max-width:470px;color:rgba(255,255,255,0.92);">
                            Your account is ready. Confirm your email address to unlock your dashboard and start learning.
                        </p>
                    </div>
                    <div style="padding:36px;">
                        <div style="background:#eef6fb;border:1px solid #d5e9f4;border-radius:18px;padding:18px 20px;margin-bottom:24px;">
                            <div style="font-size:13px;color:#486278;text-transform:uppercase;letter-spacing:0.08em;">Email confirmation</div>
                            <div style="margin-top:8px;font-size:24px;font-weight:700;color:#102033;">One click and you are in</div>
                        </div>
                        <p style="margin:0 0 16px;font-size:15px;line-height:1.8;color:#31475f;">
                            Thanks for joining TechSpace Hub. Use the button below to verify your email address.
                        </p>
                        <div style="padding:10px 0 24px;">
                            <a href="{verify_link}" style="display:inline-block;background:#0f6c8b;color:#ffffff;text-decoration:none;font-weight:700;font-size:15px;padding:14px 26px;border-radius:999px;">
                                Verify Email Address
                            </a>
                        </div>
                        <div style="background:#fff6e7;border:1px solid #f1dfb2;border-radius:16px;padding:16px 18px;margin-bottom:22px;">
                            <div style="font-size:14px;font-weight:700;color:#7a5a00;margin-bottom:6px;">Important</div>
                            <div style="font-size:14px;line-height:1.7;color:#6f5a1b;">
                                This verification link expires in 24 hours.
                            </div>
                        </div>
                        <p style="margin:0;font-size:14px;line-height:1.8;color:#55697f;">
                            If you did not create this account, you can safely ignore this email.
                        </p>
                    </div>
                    <div style="padding:20px 36px 28px;border-top:1px solid #e7edf4;font-size:12px;line-height:1.8;color:#708399;">
                        <div>TechSpace Hub</div>
                        <div>techspacehub.co.ke</div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        plain_message = """Verify your TechSpace Hub email address.

Open the verification button in the email to activate your account.

This verification link expires in 24 hours.

If you did not create this account, you can safely ignore this email.

TechSpace Hub
techspacehub.co.ke
"""

        _send_email(subject, plain_message, html_message, [user_email])

        logger.info("send_verification_email success email=%s", user_email)
        return True

        subject = "Verify Your TechSpace Hub Account"

        # HTML email content
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #f9f9f9; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
                .content {{ padding: 30px; background: white; }}
                .button {{ background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to TechSpace Hub!</h1>
                </div>
                <div class="content">
                    <h2>Verify Your Email Address</h2>
                    <p>Thank you for registering with TechSpace Hub. To complete your registration and start learning, please verify your email address by clicking the button below:</p>
                    
                    <div style="text-align: center;">
                        <a href="{verify_link}" class="button" style="color: white; text-decoration: none; font-weight: bold;">
                            Verify Email Address
                        </a>
                    </div>
                    
                    <p>If the button doesn't work, copy and paste this link into your browser:</p>
                    <p style="background: #f4f4f4; padding: 15px; border-radius: 5px; word-break: break-all; font-family: monospace;">
                        {verify_link}
                    </p>
                    
                    <p><strong>This verification link will expire in 24 hours.</strong></p>
                    
                    <p>If you didn't create an account with TechSpace Hub, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 TechSpace Hub. All rights reserved.</p>
                    <p>techspacehub.co.ke</p>
                </div>
            </div>
        </body>
        </html>
        """

        plain_message = f"""
        Welcome to TechSpaceHub!
        
        Verify Your Email Address
        
        Thank you for registering with TechSpace Hub. To complete your registration, please verify your email address by visiting this link:
        
        {verify_link}
        
        This verification link will expire in 24 hours.
        
        If you didn't create an account with TechSpace Hub, please ignore this email.
        
        © 2025 TechSpaceHub
        techspacehub.co.ke
        """

        _send_email(subject, plain_message, html_message, [user_email])

        logger.info("send_verification_email success email=%s", user_email)
        return True

    except Exception as e:
        logger.error(f"Failed to send verification email to {user_email}: {str(e)}", exc_info=True)
        return False


def send_password_reset_email(user_email, uid, token):
    """
    Send password reset email
    """
    try:
        logger.info(
            "send_password_reset_email start email=%s transport=%s host=%s port=%s backend=%s from=%s timeout=%s",
            user_email,
            getattr(settings, "EMAIL_TRANSPORT", "smtp"),
            settings.EMAIL_HOST,
            settings.EMAIL_PORT,
            settings.EMAIL_BACKEND,
            settings.DEFAULT_FROM_EMAIL,
            getattr(settings, "EMAIL_TIMEOUT", None),
        )
        reset_link = f"{settings.FRONTEND_URL}/password-reset-confirm/{uid}/{token}/"

        subject = "Reset Your TechSpace Hub Password"
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reset Your Password</title>
        </head>
        <body style="margin:0;padding:0;background:#f4f7fb;font-family:Segoe UI,Arial,sans-serif;color:#102033;">
            <div style="padding:32px 16px;">
                <div style="max-width:620px;margin:0 auto;background:#ffffff;border:1px solid #ecdce7;border-radius:24px;overflow:hidden;box-shadow:0 18px 50px rgba(16,32,51,0.08);">
                    <div style="padding:32px 36px;background:linear-gradient(135deg,#6a1b4d 0%,#b83280 55%,#ffd1e8 100%);color:#ffffff;">
                        <div style="font-size:12px;letter-spacing:0.18em;text-transform:uppercase;opacity:0.86;">TechSpace Hub</div>
                        <h1 style="margin:14px 0 10px;font-size:32px;line-height:1.15;">Reset your password</h1>
                        <p style="margin:0;font-size:15px;line-height:1.7;max-width:470px;color:rgba(255,255,255,0.92);">
                            We received a request to reset the password for your account.
                        </p>
                    </div>
                    <div style="padding:36px;">
                        <div style="background:#fff1f7;border:1px solid #f5d3e4;border-radius:18px;padding:18px 20px;margin-bottom:24px;">
                            <div style="font-size:13px;color:#8e4d6f;text-transform:uppercase;letter-spacing:0.08em;">Account security</div>
                            <div style="margin-top:8px;font-size:24px;font-weight:700;color:#102033;">Choose a new password securely</div>
                        </div>
                        <p style="margin:0 0 16px;font-size:15px;line-height:1.8;color:#31475f;">
                            Use the button below to continue with your password reset request.
                        </p>
                        <div style="padding:10px 0 24px;">
                            <a href="{reset_link}" style="display:inline-block;background:#b83280;color:#ffffff;text-decoration:none;font-weight:700;font-size:15px;padding:14px 26px;border-radius:999px;">
                                Reset Password
                            </a>
                        </div>
                        <div style="background:#fff6e7;border:1px solid #f1dfb2;border-radius:16px;padding:16px 18px;margin-bottom:22px;">
                            <div style="font-size:14px;font-weight:700;color:#7a5a00;margin-bottom:6px;">Important</div>
                            <div style="font-size:14px;line-height:1.7;color:#6f5a1b;">
                                This password reset link expires in 1 hour.
                            </div>
                        </div>
                        <p style="margin:0;font-size:14px;line-height:1.8;color:#55697f;">
                            If you did not request this change, you can ignore this email and your current password will remain unchanged.
                        </p>
                    </div>
                    <div style="padding:20px 36px 28px;border-top:1px solid #f0e6ed;font-size:12px;line-height:1.8;color:#708399;">
                        <div>TechSpace Hub</div>
                        <div>techspacehub.co.ke</div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        plain_message = """Reset your TechSpace Hub password.

Open the reset button in the email to continue.

This password reset link expires in 1 hour.

If you did not request this change, you can ignore this email and your current password will remain unchanged.

TechSpace Hub
techspacehub.co.ke
"""

        _send_email(subject, plain_message, html_message, [user_email])

        logger.info("Password reset email sent successfully to %s", user_email)
        return True

        subject = "Reset Your TechSpace Hub Password"

        # HTML email content
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #f9f9f9; }}
                .header {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 30px; text-align: center; }}
                .content {{ padding: 30px; background: white; }}
                .button {{ background: #f5576c; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset Request</h1>
                </div>
                <div class="content">
                    <h2>Reset Your Password</h2>
                    <p>You're receiving this email because you requested a password reset for your TechSpace Hub account.</p>
                    
                    <div style="text-align: center;">
                        <a href="{reset_link}" class="button" style="color: white; text-decoration: none; font-weight: bold;">
                            Reset Password
                        </a>
                    </div>
                    
                    <p>If the button doesn't work, copy and paste this link into your browser:</p>
                    <p style="background: #f4f4f4; padding: 15px; border-radius: 5px; word-break: break-all; font-family: monospace;">
                        {reset_link}
                    </p>
                    
                    <p><strong>This password reset link will expire in 1 hour.</strong></p>
                    
                    <p>If you didn't request a password reset, please ignore this email and your password will remain unchanged.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 TechSpace Hub. All rights reserved.</p>
                    <p>techspacehub.co.ke</p>
                </div>
            </div>
        </body>
        </html>
        """

        plain_message = f"""
        Password Reset Request - TechSpaceHub
        
        You're receiving this email because you requested a password reset for your TechSpace Hub account.
        
        Reset your password by visiting this link:
        {reset_link}
        
        This password reset link will expire in 1 hour.
        
        If you didn't request a password reset, please ignore this email and your password will remain unchanged.
        
        © 2025 TechSpaceHub
        techspacehub.co.ke
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Password reset email sent successfully to {user_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send password reset email to {user_email}: {str(e)}")
        return False


def send_payment_confirmation_email(user_email, amount, week_title, payment_method):
    """
    Send payment confirmation email
    """
    try:
        subject = f"Payment Confirmation - {week_title}"

        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #f9f9f9; }}
                .header {{ background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 30px; text-align: center; }}
                .content {{ padding: 30px; background: white; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .success {{ color: #28a745; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Payment Confirmed!</h1>
                </div>
                <div class="content">
                    <h2>Thank You for Your Payment</h2>
                    <p class="success">Your payment has been successfully processed.</p>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <p><strong>Course:</strong> {week_title}</p>
                        <p><strong>Amount:</strong> KES {amount}</p>
                        <p><strong>Payment Method:</strong> {payment_method}</p>
                    </div>
                    
                    <p>You can now access your course materials immediately. Start learning and building your skills!</p>
                    
                    <p>If you have any questions, please contact our support team.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 TechSpace Hub. All rights reserved.</p>
                    <p>techspacehub.co.ke | support@techspacehub.co.ke</p>
                </div>
            </div>
        </body>
        </html>
        """

        plain_message = f"""
        Payment Confirmed!
        
        Thank you for your payment of KES {amount} for {week_title}.
        
        Your payment has been successfully processed via {payment_method}.
        
        You can now access your course materials immediately.
        
        If you have any questions, please contact our support team.
        
        © 2024 TechSpaceHub
        techspacehub.co.ke
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Payment confirmation email sent to {user_email}")
        return True

    except Exception as e:
        logger.error(
            f"Failed to send payment confirmation email to {user_email}: {str(e)}"
        )
        return False


def send_manual_payment_approval_email(payment, enrollment):
    """
    Send manual payment approval email
    """
    try:
        subject = f"Payment Confirmed - Access Granted for {payment.week}"

        # HTML email content
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #f9f9f9; }}
                .header {{ background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 30px; text-align: center; }}
                .content {{ padding: 30px; background: white; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .success {{ color: #28a745; font-weight: bold; }}
                .details {{ background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Payment Confirmed!</h1>
                </div>
                <div class="content">
                    <h2>Manual Payment Approved</h2>
                    <p class="success">Your manual M-Pesa payment has been confirmed and approved!</p>
                    
                    <div class="details">
                        <p><strong>Course:</strong> {payment.week.course.title if payment.week.course else 'N/A'}</p>
                        <p><strong>Week:</strong> {payment.week.title} ({getattr(payment.week, 'level', 'N/A')})</p>
                        <p><strong>Plan:</strong> {payment.plan}</p>
                        <p><strong>Amount:</strong> KES {payment.amount}</p>
                        <p><strong>Payment Method:</strong> Manual M-Pesa</p>
                    </div>
                    
                    <p><strong>You now have full access</strong> to the course materials for your selected plan.</p>
                    
                    <p>Start learning now by visiting your dashboard and begin your journey!</p>
                    
                    <p>If you have any questions, please contact our support team.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2025 TechSpaceHub. All rights reserved.</p>
                    <p>techspacehub.co.ke | support@techspacehub.co.ke</p>
                </div>
            </div>
        </body>
        </html>
        """

        plain_message = f"""
        Payment Confirmed - Access Granted for {payment.week}

        Hello {payment.user.username},

        Your manual payment for {payment.week} has been confirmed!

        Payment Details:
        - Course: {payment.week.course.title if payment.week.course else 'N/A'}
        - Module: {payment.week.title} ({getattr(payment.week, 'level', 'N/A')})
        - Plan: {payment.plan}
        - Amount: KES {payment.amount}
        - Payment Method: Manual M-Pesa

        You now have full access to the course materials for your selected plan.

        Start learning now: {settings.FRONTEND_URL}/dashboard

        Need help? Reply to this email or contact us on WhatsApp.

        Happy learning!
        The TechSpace Hub Team
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[payment.user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Manual payment approval email sent to {payment.user.email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send manual payment approval email: {str(e)}")
        return False
