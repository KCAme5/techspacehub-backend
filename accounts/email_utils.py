import os
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, From, To, Subject, PlainTextContent, HtmlContent
from django.conf import settings

logger = logging.getLogger(__name__)


def send_email(to_email, subject, html_content, plain_text_content=None):
    """
    Send email using SendGrid
    """
    try:
        # Get configuration from settings
        sendgrid_api_key = getattr(settings, "SENDGRID_API_KEY", None)
        from_email = getattr(
            settings, "DEFAULT_FROM_EMAIL", "noreply@techspacehub.co.ke"
        )

        if not sendgrid_api_key:
            logger.error("SendGrid API key not configured")
            return False

        # Create message
        message = Mail(
            from_email=From(from_email, "TechSpace Hub"),
            to_emails=To(to_email),
            subject=Subject(subject),
            html_content=HtmlContent(html_content),
        )

        # Add plain text content if provided
        if plain_text_content:
            message.plain_text_content = PlainTextContent(plain_text_content)

        # Send email
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)

        logger.info(f"Email sent to {to_email}. Status: {response.status_code}")
        return response.status_code in [200, 202]

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False


def send_verification_email(email, uid, token):
    """
    Send account verification email
    """
    frontend_url = getattr(settings, "FRONTEND_URL", "https://techspacehub.co.ke")
    verify_link = f"{frontend_url}/verify-email/{uid}/{token}/"

    subject = "Verify Your TechSpace Hub Account"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to TechSpace Hub!</h1>
            </div>
            <div class="content">
                <h2>Verify Your Email Address</h2>
                <p>Thank you for registering with TechSpace Hub. To complete your registration, please verify your email address by clicking the button below:</p>
                
                <div style="text-align: center;">
                    <a href="{verify_link}" class="button" style="color: white; text-decoration: none;">
                        Verify Email Address
                    </a>
                </div>
                
                <p>If the button doesn't work, copy and paste this link into your browser:</p>
                <p style="word-break: break-all; background: #eee; padding: 10px; border-radius: 5px; font-size: 12px;">
                    {verify_link}
                </p>
                
                <p>This verification link will expire in 24 hours.</p>
                
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

    plain_text_content = f"""
    Verify Your TechSpace Hub Account
    
    Thank you for registering with TechSpace Hub. To complete your registration, please verify your email address by visiting this link:
    
    {verify_link}
    
    This verification link will expire in 24 hours.
    
    If you didn't create an account with TechSpace Hub, please ignore this email.
    
    © 2024 TechSpace Hub
    techspacehub.co.ke
    """

    return send_email(email, subject, html_content, plain_text_content)


def send_password_reset_email(email, uid, token):
    """
    Send password reset email
    """
    frontend_url = getattr(settings, "FRONTEND_URL", "https://techspacehub.co.ke")
    reset_link = f"{frontend_url}/password-reset-confirm/{uid}/{token}/"

    subject = "Reset Your TechSpace Hub Password"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ background: #f5576c; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
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
                    <a href="{reset_link}" class="button" style="color: white; text-decoration: none;">
                        Reset Password
                    </a>
                </div>
                
                <p>If the button doesn't work, copy and paste this link into your browser:</p>
                <p style="word-break: break-all; background: #eee; padding: 10px; border-radius: 5px; font-size: 12px;">
                    {reset_link}
                </p>
                
                <p>This password reset link will expire in 1 hour.</p>
                
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

    plain_text_content = f"""
    Password Reset Request
    
    You're receiving this email because you requested a password reset for your TechSpace Hub account.
    
    Reset your password by visiting this link:
    {reset_link}
    
    This password reset link will expire in 1 hour.
    
    If you didn't request a password reset, please ignore this email and your password will remain unchanged.
    
    © 2025 TechSpace Hub
    techspacehub.co.ke
    """

    return send_email(email, subject, html_content, plain_text_content)
