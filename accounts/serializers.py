from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.exceptions import AuthenticationFailed, ValidationError
import uuid
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.utils.text import slugify
from django.utils import timezone
from .models import Wallet, WalletTransaction, WithdrawalRequest, Referral
from django.conf import settings
from .email_utils import send_verification_email, send_password_reset_email

import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    referral_code = serializers.CharField(required=False, allow_blank=True)
    full_name = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "referral_code", "full_name", "role"]

    def validate_email(self, value):
        value = value.strip().lower()
        validate_email(value)
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already in use.")
        return value

    def create(self, validated_data):
        full_name = validated_data.pop("full_name").strip()
        password = validated_data.pop("password")
        referral_code = validated_data.pop("referral_code", None)
        email = validated_data.get("email")

        # sanitize username: slugify and ensure uniqueness
        base_username = (
            slugify(full_name.replace(" ", "_")) or f"user_{uuid.uuid4().hex[:6]}"
        )
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        user = User(
            username=username, email=email, is_active=False
        )  # inactive until email verified
        user.set_password(password)
        user.role = validated_data.get("role", "student")
        user.subscription_status = "inactive"
        user.my_referral_code = str(uuid.uuid4())[:8]

        user.save()

        if referral_code:
            try:
                referrer = User.objects.get(my_referral_code=referral_code)
                user.referred_by = referrer
                user.save(update_fields=["referred_by"])

                Referral.objects.create(
                    referrer=referrer,
                    referred_user=user,
                    referral_code_used=referral_code,
                    status="pending",
                    commission_earned=0.00,
                    commission_paid=False,
                )

            except User.DoesNotExist:
                pass

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        try:
            send_verification_email(user.email, uid, token)
        except Exception as e:
            logger.warning(
                f"Failed to send verification email for {user.email}: {str(e)}"
            )
            # Don't fail registration if email sending fails

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email", "").strip().lower()
        password = data.get("password")

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            raise AuthenticationFailed("Invalid credentials")

        if not user_obj.is_active:
            raise AuthenticationFailed("Please verify your email before logging in.")

        if user_obj.is_locked():
            raise AuthenticationFailed("Account locked. Try again later.")

        user = authenticate(username=user_obj.username, password=password)
        if not user:
            raise AuthenticationFailed("Invalid credentials")

        if user.is_superuser:
            raise AuthenticationFailed("Action is restricted to students")

        return {"user": user}


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self, **kwargs):
        email = self.validated_data["email"].strip().lower()
        user = User.objects.filter(email=email).first()
        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            send_password_reset_email(user.email, uid, token)

        return {
            "message": "If an account with this email exists, you will receive a reset link."
        }


class SetNewPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=6)

    def validate(self, attrs):
        uidb64 = self.context.get("uidb64")
        token = self.context.get("token")

        try:
            from django.utils.http import urlsafe_base64_decode

            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except Exception:
            raise serializers.ValidationError("Invalid UID")

        if not default_token_generator.check_token(user, token):
            raise serializers.ValidationError("Invalid or expired token")

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        password = self.validated_data["password"]
        user = self.validated_data["user"]
        user.set_password(password)
        user.save()
        return user


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ["balance", "created_at", "updated_at"]


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = [
            "id",
            "amount",
            "transaction_type",
            "description",
            "status",
            "created_at",
        ]


class ReferralSerializer(serializers.ModelSerializer):
    referred_user_email = serializers.EmailField(
        source="referred_user.email", read_only=True
    )
    referred_user_name = serializers.CharField(
        source="referred_user.username", read_only=True
    )
    referred_user_status = serializers.CharField(
        source="referred_user.subscription_status", read_only=True
    )
    referred_user_joined = serializers.DateTimeField(
        source="referred_user.date_joined", read_only=True
    )

    class Meta:
        model = Referral
        fields = [
            "id",
            "referred_user_email",
            "referred_user_name",
            "referred_user_status",
            "referred_user_joined",
            "referral_date",
            "status",
            "commission_earned",
            "commission_paid",
        ]


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = WithdrawalRequest
        fields = [
            "id",
            "amount",
            "method",
            "status",
            "account_details",
            "created_at",
            "processed_at",
        ]
        read_only_fields = ["status", "created_at", "processed_at"]


class CreateWithdrawalRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)
    method = serializers.ChoiceField(
        choices=[("mpesa", "M-Pesa"), ("paypal", "PayPal")]
    )
    account_details = serializers.JSONField()

    def validate_amount(self, value):
        user = self.context["request"].user
        if value > user.wallet.balance:
            raise serializers.ValidationError("Insufficient wallet balance")
        return value

    def validate_account_details(self, value):
        method = self.initial_data.get("method")
        if method == "mpesa" and "phone" not in value:
            raise serializers.ValidationError("Phone number required for M-Pesa")
        if method == "paypal" and "email" not in value:
            raise serializers.ValidationError("Email required for PayPal")
        return value
