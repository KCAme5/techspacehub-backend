from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.http import JsonResponse
from django.db import connection
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    PasswordResetRequestSerializer,
    SetNewPasswordSerializer,
    WalletSerializer,
    WalletTransactionSerializer,
    ReferralSerializer,
    WithdrawalRequestSerializer,
    CreateWithdrawalRequestSerializer,
)
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str
from django.conf import settings
from rest_framework.throttling import ScopedRateThrottle
from .models import LoginAttempt, Wallet, Referral, WalletTransaction, WithdrawalRequest
from django.utils import timezone
from datetime import timedelta
from .utils import send_verification_email
from decimal import Decimal
import logging
from django.db.models import Sum
from django.shortcuts import redirect
from urllib.parse import urlencode
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.contrib.auth import login
from .email_utils import send_verification_email
from .activity_log import log_activity, log_authentication, log_financial


def health_check(request):
    """Health check endpoint for Coolify/Docker"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "healthy", "database": "connected"}, status=200)
    except Exception as e:
        return JsonResponse({"status": "unhealthy", "error": str(e)}, status=503)


logger = logging.getLogger(__name__)
User = get_user_model()


LOCK_THRESHOLD = 5  # attempts
LOCK_TIME_MINUTES = 15  # lock duration

logger = logging.getLogger("accounts")


# In accounts/views.py - UPDATE THE GOOGLE CALLBACK FUNCTION
def google_callback_fixed(request):
    # Check if user is already authenticated via social account
    if request.user.is_authenticated:
        logger.info(f"User already authenticated: {request.user}")
        return generate_redirect_with_tokens(request.user)

    # Try to get the social account from session
    social_login = getattr(request, "sociallogin", None)
    if social_login and social_login.user.is_authenticated:
        logger.info(f"Social login user: {social_login.user}")
        login(request, social_login.user)
        return generate_redirect_with_tokens(social_login.user)

    # Last resort: check for any authenticated user
    if request.user.is_authenticated:
        return generate_redirect_with_tokens(request.user)

    logger.error("No user authenticated in callback")
    return redirect(f"{settings.FRONTEND_URL}/login?error=auth_failed")


def generate_redirect_with_tokens(user):
    """Helper function to generate redirect URL with JWT tokens"""
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    params = urlencode({"access": access_token, "refresh": refresh_token})
    frontend_url = f"{settings.FRONTEND_URL}/oauth2/redirect?{params}"

    return redirect(frontend_url)


@login_required
def google_login_redirect(request):
    user = request.user

    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    # Build frontend URL with tokens
    params = urlencode({"access": access_token, "refresh": refresh_token})
    frontend_url = f"{settings.FRONTEND_URL}/oauth2/redirect?{params}"

    return redirect(frontend_url)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    return Response(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": getattr(user, "role", "student"),
        }
    )


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_scope = "signup"
    throttle_classes = [ScopedRateThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"frontend_url": settings.FRONTEND_URL}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Log registration
        log_authentication(
            user=user,
            action="register",
            request=request,
            success=True,
            details={"email": user.email, "role": user.role},
        )

        return Response(
            {
                "message": "Registration successful. Check your email to verify your account."
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"
    throttle_classes = [ScopedRateThrottle]

    def _get_client_ip(self, request):
        ip = request.META.get("HTTP_X_FORWARDED_FOR")
        if ip:
            ip = ip.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # Log request details
        ip = self._get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:512]

        # Reset failed attempts on success
        user.reset_login_attempts()

        # Create login attempt (success)
        LoginAttempt.objects.create(
            user=user,
            email=user.email,
            ip_address=ip,
            user_agent=user_agent,
            success=True,
        )

        # Log successful login to activity log
        log_authentication(
            user=user,
            action="login_success",
            request=request,
            success=True,
            details={"role": user.role},
        )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "role": user.role,
                "subscription_status": user.subscription_status,
                "referral_code": user.my_referral_code,
            },
            status=status.HTTP_200_OK,
        )

    def handle_exception(self, exc):
        request = self.request
        email = request.data.get("email")
        ip = self._get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:512]

        user = None
        if email:
            user = User.objects.filter(email=email).first()

        # Record failed attempt
        LoginAttempt.objects.create(
            user=user,
            email=email,
            ip_address=ip,
            user_agent=user_agent,
            success=False,
            failure_reason=str(exc),  # Now using TextField, no truncation needed
        )

        # Log failed login to activity log
        log_authentication(
            user=user,
            action="login_failed",
            request=request,
            success=False,
            details={"email": email, "reason": str(exc)[:200]},
        )

        # Increment failed attempts if user exists
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            user.last_failed_login = timezone.now()
            if user.failed_login_attempts >= LOCK_THRESHOLD:
                user.locked_until = timezone.now() + timedelta(
                    minutes=LOCK_TIME_MINUTES
                )
            user.save(
                update_fields=[
                    "failed_login_attempts",
                    "last_failed_login",
                    "locked_until",
                ]
            )

        return super().handle_exception(exc)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except Exception:
            return Response(
                {"detail": "Invalid verification link"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if default_token_generator.check_token(user, token):
            user.is_active = True
            user.save(update_fields=["is_active"])
            return Response(
                {"message": "Email verified. You can now log in."},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"detail": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST
        )


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "If an account with this email exists, you will receive a reset link."
            },
            status=status.HTTP_200_OK,
        )


class SetNewPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        serializer = SetNewPasswordSerializer(
            data=request.data, context={"uidb64": uidb64, "token": token}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Password reset successful"},
            status=status.HTTP_200_OK,
        )


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "full_name": user.username,
                "email": user.email,
                "role": user.role,
                "subscription_status": user.subscription_status,
                "referral_code": user.my_referral_code,
            }
        )


class ResendVerificationView(APIView):
    def post(self, request):
        email = request.data.get("email")
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                return Response({"detail": "Account already verified."}, status=400)

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            email_sent = send_verification_email(user.email, uid, token)

            if email_sent:
                return Response({"detail": "Verification email resent."}, status=200)
            else:
                return Response(
                    {"detail": "Failed to send verification email."}, status=500
                )
        except User.DoesNotExist:
            return Response({"detail": "No user found with this email."}, status=404)


class WalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        serializer = WalletSerializer(wallet)
        return Response(serializer.data)


class WalletTransactionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        transactions = wallet.transactions.all().order_by("-created_at")
        serializer = WalletTransactionSerializer(transactions, many=True)
        return Response(serializer.data)


class ReferralStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        total_referrals = user.referrals_made.count()
        pending_referrals = user.referrals_made.filter(status="pending").count()
        completed_referrals = user.referrals_made.filter(status="completed").count()
        total_earnings = (
            user.referrals_made.aggregate(total=Sum("commission_earned"))["total"] or 0
        )

        return Response(
            {
                "total_referrals": total_referrals,
                "pending_referrals": pending_referrals,
                "completed_referrals": completed_referrals,
                "total_earnings": total_earnings,
                "referral_code": user.my_referral_code,
                "referral_link": f"{settings.FRONTEND_URL}/register?ref={user.my_referral_code}",
            }
        )


class ReferralListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        referrals = request.user.referrals_made.all().order_by("-referral_date")
        serializer = ReferralSerializer(referrals, many=True)
        return Response(serializer.data)


class WithdrawalRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        withdrawals = request.user.withdrawal_requests.all().order_by("-created_at")
        serializer = WithdrawalRequestSerializer(withdrawals, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CreateWithdrawalRequestSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        wallet, created = Wallet.objects.get_or_create(user=request.user)

        # Create withdrawal request
        withdrawal = WithdrawalRequest.objects.create(
            user=request.user,
            amount=serializer.validated_data["amount"],
            method=serializer.validated_data["method"],
            account_details=serializer.validated_data["account_details"],
        )

        # Deduct from wallet (but don't process immediately - admin will process)
        wallet = request.user.wallet
        wallet.balance -= withdrawal.amount
        wallet.save()

        # Record transaction
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=-withdrawal.amount,
            transaction_type="withdrawal",
            description=f"Withdrawal request #{withdrawal.id}",
            status="pending",
        )

        return Response(
            WithdrawalRequestSerializer(withdrawal).data, status=status.HTTP_201_CREATED
        )


def process_referral_commission(referred_user, payment_amount):
    """
    Process referral commission when a referred user makes a payment
    """
    logger.info(f"=== STARTING REFERRAL COMMISSION PROCESS ===")
    logger.info(f"Referred user: {referred_user.id} - {referred_user.email}")
    logger.info(f"Payment amount: {payment_amount}")

    try:
        # Check if user was referred by someone
        if not referred_user.referred_by:
            logger.info(f"User {referred_user.id} was not referred by anyone")
            return False

        referrer = referred_user.referred_by
        logger.info(f"Referrer found: {referrer.id} - {referrer.email}")

        # Try to get the referral record
        try:
            referral = Referral.objects.get(referred_user=referred_user)
            logger.info(f"Referral record found: {referral.id}")
        except Referral.DoesNotExist:
            logger.error(f"No referral record found for user: {referred_user.id}")
            # Create referral record if it doesn't exist
            referral = Referral.objects.create(
                referrer=referrer,
                referred_user=referred_user,
                referral_code_used=referrer.my_referral_code,
                status="pending",
            )
            logger.info(f"Created new referral record: {referral.id}")

        # Prevent duplicate processing
        if referral.status == "completed" and referral.commission_paid:
            logger.info(
                f"Referral commission already processed for user: {referred_user.id}"
            )
            return True

        # Calculate commission
        commission_rate = Decimal("0.17")
        commission = payment_amount * commission_rate
        logger.info(f"Commission calculated: ${commission}")

        # Update referral record
        referral.status = "completed"
        referral.commission_earned = commission
        referral.commission_paid = True
        referral.save()
        logger.info(f"Referral record updated")

        # Credit referrer's wallet (get or create if doesn't exist)
        referrer_wallet, created = Wallet.objects.get_or_create(user=referrer)
        old_balance = referrer_wallet.balance
        referrer_wallet.balance += commission
        referrer_wallet.save()
        logger.info(f"Wallet updated: ${old_balance} -> ${referrer_wallet.balance}")

        # Record transaction
        WalletTransaction.objects.create(
            wallet=referrer_wallet,
            amount=commission,
            transaction_type="referral",
            description=f"Referral commission from {referred_user.email}",
            status="completed",
        )
        logger.info(f"Transaction recorded")

        logger.info(f"=== REFERRAL COMMISSION COMPLETED ===")
        logger.info(
            f"Referral commission processed: {referrer.email} earned ${commission} from {referred_user.email}"
        )
        return True

    except Exception as e:
        logger.error(f"Error processing referral commission: {str(e)}", exc_info=True)
        return False


class UserPreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Return default preferences for now
        default_preferences = {
            "notifications": {
                "course_updates": True,
                "assignment_reminders": True,
                "marketing_emails": False,
            },
            "learning_preferences": {
                "video_speed": "1.0",
                "auto_play": False,
                "download_quality": "medium",
            },
        }
        return Response(default_preferences)

    def put(self, request):
        user_preferences = request.data
        return Response(user_preferences, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not old_password or not new_password:
            return Response(
                {"error": "Both old and new password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        if not user.check_password(old_password):
            return Response(
                {"error": "Old password is incorrect"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Enhanced password validation
        if len(new_password) < 8:
            return Response(
                {"error": "New password must be at least 8 characters long"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check password strength
        has_upper = any(c.isupper() for c in new_password)
        has_lower = any(c.islower() for c in new_password)
        has_digit = any(c.isdigit() for c in new_password)

        if not (has_upper and has_lower and has_digit):
            return Response(
                {"error": "Password must contain uppercase, lowercase, and numbers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        # Log password change
        log_activity(
            user=user,
            action="password_change",
            request=request,
            severity="info",
            details={"changed_by": "user"},
        )

        return Response(
            {"message": "Password updated successfully"}, status=status.HTTP_200_OK
        )


class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user
        data = request.data

        allowed_fields = ["first_name", "last_name", "email", "bio"]

        for field in allowed_fields:
            if field in data:
                setattr(user, field, data[field])

        if "email" in data and data["email"] != user.email:
            if User.objects.filter(email=data["email"]).exclude(id=user.id).exists():
                return Response(
                    {"error": "Email already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            user.save()
            return Response(
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "bio": getattr(user, "bio", ""),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": "Failed to update profile"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class DebugReferralView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get referral stats
        referrals_made = user.referrals_made.all()
        referred_by = user.referred_by

        data = {
            "user_id": user.id,
            "user_email": user.email,
            "referral_code": user.my_referral_code,
            "referred_by": referred_by.email if referred_by else None,
            "referrals_made_count": referrals_made.count(),
            "referrals_made": [
                {
                    "referred_user": ref.referred_user.email,
                    "status": ref.status,
                    "commission_earned": ref.commission_earned,
                    "commission_paid": ref.commission_paid,
                }
                for ref in referrals_made
            ],
            "wallet_balance": user.wallet.balance if hasattr(user, "wallet") else 0,
            "wallet_transactions": list(
                user.wallet.transactions.values() if hasattr(user, "wallet") else []
            ),
        }

        return Response(data)
