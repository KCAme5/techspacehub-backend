import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_verification_email(user_email, uid, token):
    """
    Send account verification email
    """
    try:
        verify_link = f"{settings.FRONTEND_URL}/verify-email/{uid}/{token}/"

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

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Verification email sent successfully to {user_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send verification email to {user_email}: {str(e)}")
        return False


def send_password_reset_email(user_email, uid, token):
    """
    Send password reset email
    """
    try:
        reset_link = f"{settings.FRONTEND_URL}/password-reset-confirm/{uid}/{token}/"

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
