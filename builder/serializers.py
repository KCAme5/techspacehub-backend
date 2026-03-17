"""
builder/serializers.py
"""

from rest_framework import serializers
from .models import UserCredits, CreditPackage, CreditPayment, GenerationSession


class UserCreditsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCredits
        fields = [
            "credits",
            "total_purchased",
            "total_used",
            "is_free_tier",
            "is_empty",
            "is_low",
        ]
        # is_empty and is_low are @property so we expose them read-only

    is_empty = serializers.BooleanField(read_only=True)
    is_low = serializers.BooleanField(read_only=True)


class CreditPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditPackage
        fields = ["id", "name", "credits", "price_kes", "is_popular"]


class CreditPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditPayment
        fields = ["id", "amount", "credits", "status", "created_at", "completed_at"]


class GenerationSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationSession
        fields = [
            "id",
            "project_name",
            "prompt",
            "output_type",
            "style_preset",
            "files",
            "file_tree",
            "conversation",
            "version",
            "parent_session",
            "explanation",
            "status",
            "credits_used",
            "created_at",
            "updated_at",
        ]

    # Handle nested serialization for parent_session
    parent_session = serializers.UUIDField(read_only=True)
